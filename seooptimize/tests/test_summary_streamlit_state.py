"""Streamlit integration tests for summary/export sidebar state flow."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from app.models.page import PageData
from app.models.project import BusinessCategory, ProjectConfig
from app.ui.components.sidebar import SITE_SUMMARY_ID


def _project() -> ProjectConfig:
    return ProjectConfig(
        business_name="State Test",
        website_url="https://example.com",
        business_category=BusinessCategory.CLEARANCE,
        target_city="Berlin",
        language="en",
    )


def _page(url: str = "https://example.com/kontakt") -> PageData:
    page = PageData(url=url)
    page.extraction_complete = True
    page.ai_complete = True
    page.ai_analysis = {"recommendation_cards": []}
    return page


def test_summary_view_renders_without_session_state_exception() -> None:
    """Regression test for report_lang widget/session-state collision."""
    at = AppTest.from_file("app/main.py")
    at.session_state["view"] = "analysis"
    at.session_state["project"] = _project()
    at.session_state["pages"] = [_page()]
    at.session_state["selected_url"] = SITE_SUMMARY_ID
    at.session_state["show_competitor_intel"] = False
    at.session_state["analysis_running"] = False

    at.run(timeout=60)
    assert len(at.exception) == 0

    # Sidebar export language radio should exist and keep app-owned key in sync.
    assert at.session_state["export_lang"] in ("en", "de")


def test_summary_view_tolerates_legacy_report_lang_key() -> None:
    """Old sessions may still contain report_lang; app must render safely."""
    at = AppTest.from_file("app/main.py")
    at.session_state["view"] = "analysis"
    at.session_state["project"] = _project()
    at.session_state["pages"] = [_page()]
    at.session_state["selected_url"] = SITE_SUMMARY_ID
    at.session_state["analysis_running"] = False
    at.session_state["report_lang"] = "de"  # legacy key from prior implementation

    at.run(timeout=60)
    assert len(at.exception) == 0
    assert at.session_state["export_lang"] in ("en", "de")


def test_regular_page_view_renders_tabs_without_name_error() -> None:
    """Regression: main page tabs must resolve render_details_page symbol."""
    at = AppTest.from_file("app/main.py")
    at.session_state["view"] = "analysis"
    at.session_state["project"] = _project()
    at.session_state["pages"] = [_page("https://example.com/")]
    at.session_state["selected_url"] = "https://example.com/"
    at.session_state["show_competitor_intel"] = False
    at.session_state["analysis_running"] = False

    at.run(timeout=60)
    assert len(at.exception) == 0
