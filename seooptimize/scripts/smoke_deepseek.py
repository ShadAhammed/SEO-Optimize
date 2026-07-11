"""Live smoke test — confirms DeepSeek API is reachable with configured .env key."""

from __future__ import annotations

import asyncio
import sys

from app.ai.deepseek import DEEPSEEK_BASE_URL, DeepSeekProvider
from app.config.settings import Settings


async def main() -> int:
    settings = Settings()
    print("=== DeepSeek Live Smoke Test ===")
    print(f"API base: {DEEPSEEK_BASE_URL}")
    print(f"Model: {settings.deepseek_model}")
    print(f"Key loaded: {settings.has_deepseek_key}")

    if not settings.has_deepseek_key:
        print("FAIL: DEEPSEEK_API_KEY not set in .env")
        return 1

    provider = DeepSeekProvider(settings.deepseek_api_key, settings.deepseek_model)
    prompt = (
        "Return ONLY valid JSON with this exact structure:\n"
        '{"reviews":[{"selector":"h1","gemini_verdict":"agree",'
        '"gemini_note":"Smoke test OK","competitor_evidence":{},'
        '"revised_suggestion":""}],"additional_annotations":[]}'
    )

    try:
        result = await provider.review(prompt)
    except Exception as exc:
        print(f"FAIL: DeepSeek API call failed: {exc}")
        return 1

    print(f"Reviews returned: {len(result.reviews)}")
    if result.reviews:
        r = result.reviews[0]
        print(f"Verdict: {r.gemini_verdict.value}")
        print(f"Note: {r.gemini_note}")
    print("STATUS: DeepSeek API integration CONFIRMED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
