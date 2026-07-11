"""DeepSeek provider — Module I reviewer.

Independent critic and competitor intelligence analyst. Validates Claude's
annotations and adds competitor evidence (positive gaps only).

DeepSeek exposes an OpenAI-compatible API at https://api.deepseek.com/v1.
Supports both deepseek-chat (standard) and deepseek-reasoner (chain-of-thought).
"""

from __future__ import annotations

import json
import re
import time

from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.models.annotations import (
    Annotation,
    GeminiAnalysis,
    GeminiReview,
    GeminiVerdict,
    Impact,
    Priority,
)

logger = get_logger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# Models that use chain-of-thought and do not support response_format / temperature
_REASONING_MODELS = {"deepseek-reasoner"}


def _is_reasoning_model(model: str) -> bool:
    return model.lower() in _REASONING_MODELS or "reasoner" in model.lower()


class DeepSeekProvider:
    """DeepSeek API wrapper for SEO review (Module I).

    Reuses GeminiAnalysis / GeminiReview models so the consensus engine
    (Module J) requires no changes.
    """

    def __init__(self, api_key: str, model: str, max_retries: int = 3) -> None:
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set. Add it to your .env file.")
        self._client = AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
        self._model = model
        self._max_retries = max_retries
        self._reasoning = _is_reasoning_model(model)
        logger.info(
            "DeepSeek provider initialised: model=%s reasoning_mode=%s",
            model,
            self._reasoning,
        )

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def review(self, prompt: str) -> GeminiAnalysis:
        """Send prompt to DeepSeek and parse the structured JSON response."""
        raw_text = await self._request(prompt, model=self._model)
        parsed = self._parse_response(raw_text)

        # Reasoner often returns malformed/empty content for strict JSON tasks.
        # Fallback to deepseek-chat for deterministic reviewer output.
        if self._reasoning and not parsed.reviews and not parsed.additional_annotations:
            fallback_model = "deepseek-chat"
            logger.warning(
                "DeepSeek reasoner returned no structured reviews; retrying with %s",
                fallback_model,
            )
            strict_prompt = (
                prompt
                + "\n\nCRITICAL: Return ONLY a valid JSON object with keys "
                  "\"reviews\" and \"additional_annotations\"."
            )
            fallback_raw = await self._request(strict_prompt, model=fallback_model)
            fallback_parsed = self._parse_response(fallback_raw)
            if fallback_parsed.reviews or fallback_parsed.additional_annotations:
                return fallback_parsed
            logger.warning("DeepSeek fallback also returned no structured reviews")

        return parsed

    async def _request(self, prompt: str, model: str) -> str:
        """Single DeepSeek API request with model-specific parameters."""
        reasoning_mode = _is_reasoning_model(model)
        logger.info(
            "Sending review request to DeepSeek (model=%s, prompt_chars=%d)",
            model,
            len(prompt),
        )
        t0 = time.monotonic()
        kwargs: dict = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
        }
        if not reasoning_mode:
            kwargs["temperature"] = 0.2
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._client.chat.completions.create(**kwargs)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        raw_text = response.choices[0].message.content or ""
        logger.info(
            "DeepSeek response received: model=%s response_chars=%d elapsed_ms=%d",
            model,
            len(raw_text),
            elapsed_ms,
        )
        return raw_text

    def _parse_response(self, raw_text: str) -> GeminiAnalysis:
        """Parse DeepSeek's JSON response into a GeminiAnalysis object.

        Handles:
        - Plain JSON
        - JSON wrapped in ```json ... ``` fences
        - deepseek-reasoner <think>...</think> prefix followed by JSON
        """
        clean = raw_text.strip()

        # Strip <think>...</think> reasoning block (deepseek-reasoner)
        clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()

        # Strip markdown fences
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1]).strip() if len(lines) > 2 else clean

        # Find the first JSON object in the text
        brace_start = clean.find("{")
        if brace_start > 0:
            clean = clean[brace_start:]
        brace_end = clean.rfind("}")
        if brace_end > 0:
            clean = clean[: brace_end + 1]

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as exc:
            logger.error(
                "DeepSeek returned invalid JSON: %s\nRaw (first 800 chars): %s",
                exc,
                raw_text[:800],
            )
            return GeminiAnalysis(reviews=[], additional_annotations=[], raw_response=raw_text)

        reviews = []
        for r in data.get("reviews", []):
            try:
                review = GeminiReview(
                    selector=r.get("selector", "body"),
                    gemini_verdict=GeminiVerdict(r.get("gemini_verdict", "agree")),
                    gemini_note=r.get("gemini_note", ""),
                    competitor_evidence=r.get("competitor_evidence") or {},
                    revised_suggestion=r.get("revised_suggestion", ""),
                )
                reviews.append(review)
            except Exception as exc:
                logger.warning("Skipping invalid DeepSeek review entry: %s", exc)

        additional = []
        for ann_data in data.get("additional_annotations", []):
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
                additional.append(ann)
            except Exception as exc:
                logger.warning("Skipping invalid DeepSeek additional annotation: %s", exc)

        logger.info(
            "DeepSeek parsed: %d reviews, %d additional annotations",
            len(reviews),
            len(additional),
        )
        return GeminiAnalysis(
            reviews=reviews,
            additional_annotations=additional,
            raw_response=raw_text,
        )
