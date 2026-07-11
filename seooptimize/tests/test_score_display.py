"""Tests for score display components."""

from app.models.page import SixAxisScore
from app.ui.components.score_display import _bar_color, render_six_axis_chart


def test_bar_color_thresholds():
    assert _bar_color(80) == "#16A34A"
    assert _bar_color(50) == "#D97706"
    assert _bar_color(20) == "#DC2626"


def test_render_six_axis_chart_does_not_use_altair(monkeypatch):
    """Score breakdown must not depend on Altair condition API."""
    import app.ui.components.score_display as module

    assert "altair" not in module.__file__
    source = open(module.__file__, encoding="utf-8").read()
    assert "alt.condition" not in source
    assert "altair" not in source

    captured: list[str] = []

    def fake_markdown(html: str, *, unsafe_allow_html: bool = False) -> None:
        captured.append(html)

    monkeypatch.setattr(module.st, "markdown", fake_markdown)

    scores = SixAxisScore(
        local_seo=10,
        content_quality=12,
        technical_seo=8,
        conversion_signals=6,
        on_page_metadata=4,
        competitor_gap=1,
    )
    render_six_axis_chart(scores)

    assert captured
    assert "Local SEO" in captured[0]
    assert "Content Quality" in captured[0]
