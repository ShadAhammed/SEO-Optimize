"""Claude Sonnet provider — Module H.

Primary SEO consultant. Receives structured JSON, returns annotation JSON.
"""

from __future__ import annotations

import json
from typing import Any

import anthropic
from anthropic import AsyncAnthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.models.annotations import ClaudeAnalysis, Annotation, Impact, Priority

logger = get_logger(__name__)


class ClaudeProvider:
    """Anthropic Claude API wrapper for SEO analysis (Module H).

    Sends structured page JSON → receives structured annotation JSON.
    Never sends raw HTML.
    """

    def __init__(self, api_key: str, model: str, max_retries: int = 3) -> None:
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file."
            )
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_retries = max_retries

    @retry(
        retry=retry_if_exception_type((anthropic.APITimeoutError, anthropic.RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def analyse(
        self,
        prompt: str,
        page_url: str = "",
        section_id: str = "",
    ) -> ClaudeAnalysis:
        """Send prompt to Claude and parse the structured JSON response."""
        import time
        logger.info(
            "Claude request: model=%s page=%s section=%s prompt_chars=%d",
            self._model,
            page_url or "(unknown)",
            section_id or "page",
            len(prompt),
        )
        t0 = time.monotonic()

        message = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        raw_text = message.content[0].text.strip()
        logger.info(
            "Claude response: model=%s page=%s section=%s response_chars=%d elapsed_ms=%d",
            self._model,
            page_url or "(unknown)",
            section_id or "page",
            len(raw_text),
            elapsed_ms,
        )

        return self._parse_response(raw_text)

    @retry(
        retry=retry_if_exception_type((anthropic.APITimeoutError, anthropic.RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def validate_additions(
        self,
        additional_annotations: list[dict[str, Any]],
        original_annotations: list[dict[str, Any]],
        business_name: str,
        page_url: str,
    ) -> list[bool]:
        """Validate reviewer-only findings: return True for each that Claude confirms.

        Called when DeepSeek or Gemini raises an issue that Claude did not flag.
        Claude acts as gatekeeper — only validated findings enter the final report.

        Args:
            additional_annotations: New findings from a reviewer (DeepSeek / Gemini).
            original_annotations: Claude's own annotations for this section.
            business_name: Business context for the prompt.
            page_url: URL being analysed.

        Returns:
            List of booleans, one per entry in additional_annotations.
        """
        if not additional_annotations:
            return []

        orig_labels = [a.get("label", "") for a in original_annotations]
        findings_json = json.dumps(
            [
                {
                    "index": i,
                    "label": ann.get("label", ""),
                    "issue": ann.get("issue", ""),
                    "selector": ann.get("selector", ""),
                    "priority": ann.get("priority", "warning"),
                }
                for i, ann in enumerate(additional_annotations)
            ],
            ensure_ascii=False,
            indent=2,
        )

        prompt = (
            f"You are reviewing SEO findings for {business_name} ({page_url}).\n\n"
            f"You already flagged these issues: {json.dumps(orig_labels, ensure_ascii=False)}\n\n"
            f"An independent AI reviewer found these ADDITIONAL issues that you did NOT flag:\n"
            f"{findings_json}\n\n"
            f"For each finding, decide: is this a genuine, actionable SEO issue worth including?\n"
            f"Respond with JSON only:\n"
            f'{{ "validated": [true/false, ...] }}\n'
            f"One boolean per finding, in the same order. true = include, false = discard."
        )

        logger.info(
            "Claude validation request: page=%s additions=%d",
            page_url,
            len(additional_annotations),
        )

        message = await self._client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

        try:
            data = json.loads(raw)
            validated = data.get("validated", [])
            result = [bool(v) for v in validated]
            # Pad or truncate to match input length
            while len(result) < len(additional_annotations):
                result.append(False)
            return result[: len(additional_annotations)]
        except Exception as exc:
            logger.warning("Claude validation parse failed: %s — defaulting all False", exc)
            return [False] * len(additional_annotations)

    def analyse_sync(self, prompt: str) -> ClaudeAnalysis:
        """Synchronous wrapper for use outside async contexts."""
        import asyncio
        return asyncio.run(self.analyse(prompt))

    def _parse_response(self, raw_text: str) -> ClaudeAnalysis:
        """Parse Claude's JSON response into a ClaudeAnalysis object."""
        # Strip markdown code fences if present
        clean = raw_text
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as exc:
            logger.error("Claude returned invalid JSON: %s\nRaw: %s", exc, raw_text[:500])
            # Return a minimal safe fallback
            return ClaudeAnalysis(
                page_score=0,
                annotations=[],
                top_priority_action="AI response could not be parsed — check logs.",
                raw_response=raw_text,
            )

        annotations = []
        for ann_data in data.get("annotations", []):
            try:
                ann = Annotation(
                    selector=ann_data.get("selector", "body"),
                    label=ann_data.get("label", "Issue")[:40],
                    priority=Priority(ann_data.get("priority", "warning")),
                    issue=ann_data.get("issue", ""),
                    why_it_matters=ann_data.get("why_it_matters", ""),
                    suggested_fix=ann_data.get("suggested_fix", ""),
                    impact=Impact(ann_data.get("impact", "medium")),
                    confidence=float(ann_data.get("confidence", 0.5)),
                )
                annotations.append(ann)
            except Exception as exc:
                logger.warning("Skipping invalid annotation: %s", exc)

        return ClaudeAnalysis(
            page_score=int(data.get("page_score", 0)),
            annotations=annotations,
            top_priority_action=data.get("top_priority_action", ""),
            raw_response=raw_text,
        )
