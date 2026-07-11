"""Tests for customer-facing text helpers."""

from types import SimpleNamespace

from app.utils.friendly_text import format_priority_actions, humanize_selector


class TestHumanizeSelector:
    def test_h1(self):
        assert humanize_selector("h1") == "Main headline"

    def test_meta_description(self):
        assert humanize_selector("meta[name='description']") == "Search result description"


class TestFormatPriorityActions:
    def test_builds_bullet_points(self):
        annotations = [
            SimpleNamespace(
                selector="h1",
                issue="The main headline does not mention Siegen.",
                suggested_fix="Entrümpelung Siegen – Fischer Entrümpelungen",
                label="Missing city",
                priority="critical",
                impact="high",
                confidence=0.9,
            ),
            SimpleNamespace(
                selector="meta[name='description']",
                issue="The Google description is too short.",
                suggested_fix="Professionelle Entrümpelung in Siegen...",
                label="Short meta",
                priority="warning",
                impact="medium",
                confidence=0.8,
            ),
        ]

        result = format_priority_actions(annotations)

        assert "- **Main headline:**" in result
        assert "- **Search result description:**" in result
        assert "h1" not in result
