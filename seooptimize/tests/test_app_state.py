"""Tests for app session-state helpers (non-Streamlit logic)."""

from __future__ import annotations

from app.models.project import BusinessCategory, ProjectConfig
from app.ui.app_state import default_export_lang


def test_default_export_lang_english() -> None:
    project = ProjectConfig(
        business_name="Test",
        website_url="https://example.com",
        business_category=BusinessCategory.CLEARANCE,
        target_city="Berlin",
        language="en",
    )
    assert default_export_lang(project) == "en"


def test_default_export_lang_german() -> None:
    project = ProjectConfig(
        business_name="Test",
        website_url="https://example.com",
        business_category=BusinessCategory.CLEARANCE,
        target_city="Berlin",
        language="de",
    )
    assert default_export_lang(project) == "de"


def test_default_export_lang_no_project() -> None:
    assert default_export_lang(None) == "en"
