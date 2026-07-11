"""Gemini 2.5 Flash provider — Module I.

Independent critic and competitor lens. Validates Claude's annotations and
adds competitor evidence (positive gaps only — SEOArch.md §6 rules).
"""

from __future__ import annotations

import json
from typing import Any

import google.genai as genai
from google.genai import types
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


class GeminiProvider:
    """Google Gemini API wrapper for competitor-lens review (Module I).

    Gemini's role is NOT to repeat Claude's work — it validates, strengthens,
    or rejects each finding and adds competitor evidence.
    """

    def __init__(self, api_key: str, model: str, max_retries: int = 3) -> None:
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY is not set. Add it to your .env file."
            )
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_retries = max_retries

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def review(self, prompt: str) -> GeminiAnalysis:
        """Send prompt to Gemini and parse the structured JSON response.

        Args:
            prompt: Complete prompt from prompts.build_gemini_prompt().

        Returns:
            GeminiAnalysis with reviews and additional annotations.
        """
        logger.info("Sending review request to Gemini (%s)", self._model)

        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=4096,
                temperature=0.2,  # Low temperature for structured JSON
            ),
        )

        raw_text = response.text.strip() if response.text else ""
        logger.debug("Gemini raw response length: %d chars", len(raw_text))

        return self._parse_response(raw_text)

    def review_sync(self, prompt: str) -> GeminiAnalysis:
        """Synchronous wrapper."""
        import asyncio
        return asyncio.run(self.review(prompt))

    def _parse_response(self, raw_text: str) -> GeminiAnalysis:
        """Parse Gemini's JSON response into a GeminiAnalysis object."""
        clean = raw_text
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as exc:
            logger.error("Gemini returned invalid JSON: %s\nRaw: %s", exc, raw_text[:500])
            return GeminiAnalysis(reviews=[], additional_annotations=[], raw_response=raw_text)

        reviews = []
        for r in data.get("reviews", []):
            try:
                review = GeminiReview(
                    selector=r.get("selector", "body"),
                    gemini_verdict=GeminiVerdict(r.get("gemini_verdict", "agree")),
                    gemini_note=r.get("gemini_note", ""),
                    competitor_evidence=r.get("competitor_evidence", {}),
                    revised_suggestion=r.get("revised_suggestion", ""),
                )
                reviews.append(review)
            except Exception as exc:
                logger.warning("Skipping invalid Gemini review: %s", exc)

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
                logger.warning("Skipping invalid additional annotation: %s", exc)

        return GeminiAnalysis(
            reviews=reviews,
            additional_annotations=additional,
            raw_response=raw_text,
        )
