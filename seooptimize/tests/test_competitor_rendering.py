"""Tests for competitor rendering and mapped gap extraction."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.analysis.competitor import CompetitorIntelligence
from app.config.settings import Settings
from app.models.project import BusinessCategory, ProjectConfig
from app.rendering.playwright_engine import RenderResult
from app.services.analysis_service import AnalysisService


@pytest.mark.asyncio
async def test_analysis_service_renders_competitors_with_app_renderer() -> None:
    """Competitor URLs must go through RenderingEngine, not only hidden crawl."""
    project = ProjectConfig(
        business_name="Fischer",
        website_url="https://fischer-entruempelungen.de/",
        business_category=BusinessCategory.CLEARANCE,
        target_city="Siegen",
        competitor_urls=["https://competitor.example"],
    )
    service = AnalysisService(project, Settings(cache_enabled=False))

    render = RenderResult(
        url="https://competitor.example",
        html=(
            "<html><head><title>Entrümpelung Siegen Profi</title></head>"
            "<body><h1>Entrümpelung Siegen mit Sofort-Termin</h1>"
            "<section id='faq'>FAQ</section>"
            "<a href='tel:+491234'>Call</a>"
            "<script type='application/ld+json'>{}</script>"
            "</body></html>"
        ),
        screenshot_path="cache/competitor_desktop.png",
        mobile_screenshot_path="cache/competitor_mobile.png",
        load_time_ms=321,
    )

    mock_renderer = MagicMock()
    mock_renderer.render_pages = AsyncMock(return_value=[render])
    service._renderer = mock_renderer

    mock_cache = MagicMock()
    mock_cache.get_competitor_sources.return_value = []
    service._cache = mock_cache

    sources = await service._render_competitor_sources()

    mock_renderer.render_pages.assert_awaited_once_with(
        ["https://competitor.example"],
        on_progress=None,
    )
    mock_cache.put_competitor_sources.assert_called_once()
    assert len(sources) == 1
    assert sources[0]["url"] == "https://competitor.example"
    assert sources[0]["rendered"] is True
    assert sources[0]["has_faq"] is True
    assert sources[0]["has_schema"] is True
    assert sources[0]["screenshot_path"] == "cache/competitor_desktop.png"


@pytest.mark.asyncio
async def test_competitor_gather_prefers_prerendered_sources() -> None:
    """Pre-rendered competitors must be used and fallback rendering skipped."""
    settings = Settings(cache_enabled=False)
    competitor = CompetitorIntelligence(settings)

    rendered_sources = [
        {
            "url": "https://competitor.example",
            "domain": "competitor.example",
            "title": "Entrümpelung Siegen",
            "h1": "Entrümpelung Siegen mit kostenlosem Vor-Ort-Termin",
            "meta_description": "Entrümpelung in Siegen mit Sofort-Termin und Festpreis.",
            "h2_count": 7,
            "has_whatsapp": True,
            "has_reviews": True,
            "has_schema": True,
            "has_faq": True,
            "word_count": 1200,
        }
    ]
    client_data = {
        "faq_items": [],
        "local_seo": {
            "has_whatsapp": False,
            "has_review_signals": False,
        },
        "seo_fields": {
            "h1": {"value": "Fischer"},
            "schema_markup": {"status": "fail"},
            "word_count": {"value": 500},
            "meta_description": {"status": "warn"},
            "h2_count": {"value": 2},
        },
    }

    with patch.object(
        competitor, "render_and_extract", new_callable=AsyncMock
    ) as fallback:
        gaps = await competitor.gather(
            ["https://competitor.example"],
            client_data,
            rendered_competitors=rendered_sources,
        )

    fallback.assert_not_awaited()
    assert len(gaps) == 1
    features = gaps[0]["positive_features"]
    assert "faq_section" in features
    assert "whatsapp" in features
    assert "reviews" in features
    assert "schema" in features
    assert "content_structure" in features
