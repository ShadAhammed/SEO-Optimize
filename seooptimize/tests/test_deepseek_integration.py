"""Integration tests confirming DeepSeek is wired into the AI pipeline."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.deepseek import DEEPSEEK_BASE_URL, DeepSeekProvider
from app.ai.prompts import build_gemini_prompt
from app.config.settings import Settings
from app.models.annotations import ClaudeAnalysis, Annotation, Impact, Priority
from app.models.page import PageData
from app.models.project import BusinessCategory, ProjectConfig


MOCK_DEEPSEEK_RESPONSE = json.dumps({
    "reviews": [
        {
            "selector": "h1",
            "gemini_verdict": "agree",
            "gemini_note": "Confirmed — H1 lacks local keyword.",
            "competitor_evidence": {
                "competitor.example": "Entrümpelung Siegen – Profi Service"
            },
            "revised_suggestion": "",
        }
    ],
    "additional_annotations": [],
})


@pytest.fixture
def mock_openai_response() -> MagicMock:
    choice = MagicMock()
    choice.message.content = MOCK_DEEPSEEK_RESPONSE
    response = MagicMock()
    response.choices = [choice]
    return response


class TestDeepSeekProvider:
    @pytest.mark.asyncio
    async def test_review_calls_deepseek_api(self, mock_openai_response: MagicMock) -> None:
        """DeepSeek provider must call the OpenAI-compatible DeepSeek endpoint."""
        with patch("app.ai.deepseek.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_cls.return_value = mock_client

            provider = DeepSeekProvider("sk-test-key", "deepseek-chat")
            prompt = "Review this SEO finding..."
            result = await provider.review(prompt)

            mock_client_cls.assert_called_once_with(
                api_key="sk-test-key",
                base_url=DEEPSEEK_BASE_URL,
            )
            mock_client.chat.completions.create.assert_awaited_once()
            call_kwargs = mock_client.chat.completions.create.await_args.kwargs
            assert call_kwargs["model"] == "deepseek-chat"
            assert call_kwargs["messages"][0]["content"] == prompt
            assert call_kwargs["response_format"] == {"type": "json_object"}

            assert len(result.reviews) == 1
            assert result.reviews[0].gemini_verdict.value == "agree"
            assert result.reviews[0].competitor_evidence["competitor.example"]


class TestAnalysisServiceDeepSeek:
    @pytest.mark.asyncio
    async def test_run_ai_for_page_uses_deepseek_reviewer(self) -> None:
        """AnalysisService must instantiate DeepSeek and call review after Claude."""
        from app.services.analysis_service import AnalysisService

        project = ProjectConfig(
            business_name="Fischer",
            website_url="https://fischer-entruempelungen.de/",
            business_category=BusinessCategory.CLEARANCE,
            target_city="Siegen",
            competitor_urls=["https://competitor.example"],
        )
        page = PageData(url="https://fischer-entruempelungen.de/")
        page.extraction_complete = True
        page.ai_complete = False

        claude_result = ClaudeAnalysis(
            page_score=45,
            annotations=[
                Annotation(
                    selector="h1",
                    label="H1 Missing City",
                    priority=Priority.CRITICAL,
                    issue="H1 has no city name",
                    why_it_matters="Local ranking signal missing",
                    suggested_fix="Entrümpelung Siegen – Fischer",
                    impact=Impact.HIGH,
                    confidence=0.9,
                )
            ],
            top_priority_action="Fix H1",
        )

        settings = Settings(
            anthropic_api_key="sk-ant-test",
            deepseek_api_key="sk-deepseek-test",
            deepseek_model="deepseek-chat",
            cache_enabled=False,
        )

        service = AnalysisService(project, settings)

        with (
            patch.object(service, "_cache") as mock_cache,
            patch("app.services.analysis_service.build_section_payloads") as mock_sections,
            patch("app.services.analysis_service.build_structured_page_data") as mock_structured,
            patch("app.services.analysis_service.ClaudeProvider") as mock_claude_cls,
            patch("app.services.analysis_service.DeepSeekProvider") as mock_deepseek_cls,
            patch.object(service._competitor, "gather", new_callable=AsyncMock) as mock_gather,
        ):
            mock_sections.return_value = {"hero": {"h1": {"status": "fail"}}}
            mock_structured.return_value = {"seo_fields": {}, "local_seo": {}}
            mock_cache.section_hash.return_value = "hash123"
            mock_cache.get_section.return_value = None
            mock_gather.return_value = []

            mock_claude = MagicMock()
            mock_claude.analyse = AsyncMock(return_value=claude_result)
            mock_claude_cls.return_value = mock_claude

            mock_deepseek = MagicMock()
            from app.models.annotations import GeminiAnalysis, GeminiReview, GeminiVerdict

            mock_deepseek.review = AsyncMock(
                return_value=GeminiAnalysis(
                    reviews=[
                        GeminiReview(
                            selector="h1",
                            gemini_verdict=GeminiVerdict.AGREE,
                            gemini_note="DeepSeek agrees with Claude.",
                            competitor_evidence={"rival.de": "Strong H1 with Siegen"},
                        )
                    ]
                )
            )
            mock_deepseek_cls.return_value = mock_deepseek

            await service.run_ai_for_page(page)

            mock_deepseek_cls.assert_called_once_with(
                "sk-deepseek-test",
                "deepseek-chat",
                settings.ai_max_retries,
            )
            mock_deepseek.review.assert_awaited()
            assert page.ai_complete is True
            assert len(page.ai_analysis.get("gemini_reviews", [])) == 1
            assert page.ai_analysis.get("reviewer_active") is True
            assert page.ai_analysis.get("reviewer_label") == "DeepSeek"

    @pytest.mark.asyncio
    async def test_stale_cache_without_reviewer_is_invalidated(self) -> None:
        """Cached Claude-only sections must re-run when DeepSeek is configured."""
        from app.services.analysis_service import AnalysisService

        project = ProjectConfig(
            business_name="Fischer",
            website_url="https://fischer-entruempelungen.de/",
            business_category=BusinessCategory.CLEARANCE,
            target_city="Siegen",
        )
        page = PageData(url="https://fischer-entruempelungen.de/")
        page.extraction_complete = True

        settings = Settings(
            anthropic_api_key="sk-ant-test",
            deepseek_api_key="sk-deepseek-test",
            deepseek_model="deepseek-chat",
            cache_enabled=True,
        )

        service = AnalysisService(project, settings)
        mock_cache = MagicMock()
        service._cache = mock_cache

        stale_cached = {
            "content_hash": "samehash",
            "competitor_version": "",
            "reviewer_version": "",  # old cache before DeepSeek
            "ai_response": {
                "claude": {
                    "page_score": 50,
                    "annotations": [{"selector": "h1", "label": "X", "priority": "critical",
                                     "issue": "i", "why_it_matters": "w",
                                     "suggested_fix": "f", "impact": "high", "confidence": 0.9}],
                    "top_priority_action": "Fix",
                },
                "gemini": {},  # no DeepSeek output
            },
        }

        with (
            patch("app.services.analysis_service.build_section_payloads") as mock_sections,
            patch("app.services.analysis_service.build_structured_page_data") as mock_structured,
            patch("app.services.analysis_service.ClaudeProvider") as mock_claude_cls,
            patch("app.services.analysis_service.DeepSeekProvider") as mock_deepseek_cls,
        ):
            mock_sections.return_value = {"hero": {"h1": {"status": "fail"}}}
            mock_structured.return_value = {}
            mock_cache.section_hash.return_value = "samehash"
            mock_cache.get_section.return_value = stale_cached

            claude_result = ClaudeAnalysis(
                page_score=50,
                annotations=[
                    Annotation(
                        selector="h1", label="X", priority=Priority.CRITICAL,
                        issue="i", why_it_matters="w", suggested_fix="f",
                        impact=Impact.HIGH, confidence=0.9,
                    )
                ],
                top_priority_action="Fix",
            )
            mock_claude = MagicMock()
            mock_claude.analyse = AsyncMock(return_value=claude_result)
            mock_claude_cls.return_value = mock_claude

            from app.models.annotations import GeminiAnalysis, GeminiReview, GeminiVerdict
            mock_deepseek = MagicMock()
            mock_deepseek.review = AsyncMock(
                return_value=GeminiAnalysis(
                    reviews=[GeminiReview(
                        selector="h1", gemini_verdict=GeminiVerdict.AGREE,
                        gemini_note="ok",
                    )]
                )
            )
            mock_deepseek_cls.return_value = mock_deepseek

            await service.run_ai_for_page(page)

            # Must NOT use stale cache — DeepSeek must be called
            mock_deepseek.review.assert_awaited_once()


class TestSettingsDeepSeek:
    def test_deepseek_key_detected_from_env(self) -> None:
        settings = Settings(
            deepseek_api_key="sk-test",
            deepseek_model="deepseek-reasoner",
        )
        assert settings.has_deepseek_key is True
        assert settings.has_reviewer_key is True
        assert "DeepSeek" in settings.reviewer_label

    def test_gemini_prompt_usable_by_deepseek(self) -> None:
        prompt = build_gemini_prompt(
            business_name="Fischer",
            city="Siegen",
            page_url="https://example.com",
            claude_annotations=[{"selector": "h1", "issue": "missing city"}],
            competitor_data={"competitor_gap_counts": {"faq_section": 2}},
        )
        assert "CLAUDE ANNOTATIONS" in prompt
        assert "COMPETITOR SUMMARY" in prompt
