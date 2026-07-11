"""Tests for consolidated report data collector."""

from __future__ import annotations

from app.exports.report_data import collect_consolidated_issues, is_kontakt_url, tier_counts
from app.models.page import FieldScore, PageData, ScoreStatus
from app.models.project import BusinessCategory, ProjectConfig
from app.utils.fix_classifier import classify_field


def test_is_kontakt_url() -> None:
    assert is_kontakt_url("https://example.com/kontakt")
    assert is_kontakt_url("https://example.com/de/kontakt/")
    assert not is_kontakt_url("https://example.com/leistungen")


def test_classify_field_meta_is_basic() -> None:
    assert classify_field("meta_title") == "Basic"
    assert classify_field("page_load_time") == "All"


def test_collect_includes_extraction_failures() -> None:
    page = PageData(url="https://example.com/kontakt")
    page.extraction_complete = True
    page.extracted.meta_title = FieldScore(
        status=ScoreStatus.FAIL,
        note="Title too short",
    )
    page.ai_analysis = {"recommendation_cards": []}

    project = ProjectConfig(
        business_name="Test Co",
        website_url="https://example.com",
        business_category=BusinessCategory.CLEARANCE,
        target_city="Berlin",
        competitor_urls=["https://competitor.example"],
    )
    issues = collect_consolidated_issues([page], project, lang="en")
    assert any(i.source == "extraction" for i in issues)
    assert any("Title" in i.label or "Meta" in i.label for i in issues)


def test_tier_counts() -> None:
    from app.exports.report_data import ConsolidatedIssue

    issues = [
        ConsolidatedIssue(label="A", selector="h1", priority="warning", tier="Basic"),
        ConsolidatedIssue(label="B", selector="schema", priority="critical", tier="Advanced"),
    ]
    counts = tier_counts(issues)
    assert counts["Basic"] == 1
    assert counts["Advanced"] == 1
