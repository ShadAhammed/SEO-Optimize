"""Reusable score display components."""

from __future__ import annotations

import streamlit as st

from app.config.theme import SCORE_CRITICAL, SCORE_OK, SCORE_WARNING
from app.models.page import ScoreStatus, SixAxisScore


def score_badge(value: int, max_value: int = 100) -> str:
    """Return an HTML badge string for a score."""
    pct = value / max_value if max_value else 0
    if pct >= 0.7:
        bg, fg = "#D1FAE5", "#065F46"
    elif pct >= 0.45:
        bg, fg = "#FEF3C7", "#92400E"
    else:
        bg, fg = "#FEE2E2", "#991B1B"
    return (
        f"<span style='background:{bg};color:{fg};padding:2px 8px;"
        f"border-radius:9999px;font-weight:700;font-size:0.8rem;'>"
        f"{value}/{max_value}</span>"
    )


def status_pill(status: ScoreStatus) -> str:
    """Return an HTML pill for pass/warn/fail."""
    configs = {
        ScoreStatus.PASS: ("#D1FAE5", "#065F46", "✓ Pass"),
        ScoreStatus.WARN: ("#FEF3C7", "#92400E", "⚠ Warn"),
        ScoreStatus.FAIL: ("#FEE2E2", "#991B1B", "✗ Fail"),
        ScoreStatus.NA:   ("#F3F4F6", "#374151", "— N/A"),
    }
    bg, fg, label = configs.get(status, ("#F3F4F6", "#374151", "—"))
    return (
        f"<span style='background:{bg};color:{fg};padding:2px 10px;"
        f"border-radius:9999px;font-weight:600;font-size:0.75rem;'>{label}</span>"
    )


def _bar_color(percentage: float) -> str:
    if percentage >= 70:
        return "#16A34A"
    if percentage >= 45:
        return "#D97706"
    return "#DC2626"


def render_six_axis_chart(scores: SixAxisScore) -> None:
    """Render a horizontal bar chart of the six scoring axes.

    Uses native Streamlit/HTML bars instead of Altair to avoid chart API
    incompatibilities across Altair/Streamlit versions.
    """
    axis_data = [
        ("Local SEO", scores.local_seo, 30),
        ("Content Quality", scores.content_quality, 25),
        ("Technical SEO", scores.technical_seo, 15),
        ("Conversion Signals", scores.conversion_signals, 15),
        ("On-Page Metadata", scores.on_page_metadata, 10),
        ("Competitor Gap", scores.competitor_gap, 5),
    ]

    rows: list[str] = []
    for label, score, maximum in axis_data:
        percentage = (score / maximum * 100) if maximum else 0
        color = _bar_color(percentage)
        width = max(2, min(100, percentage))
        rows.append(
            "<div style='margin-bottom:10px;'>"
            f"<div style='display:flex;justify-content:space-between;"
            f"font-size:0.82rem;margin-bottom:4px;'>"
            f"<span style='font-weight:600;'>{label}</span>"
            f"<span style='color:#64748B;'>{score:.0f}/{maximum}</span>"
            "</div>"
            "<div style='background:#F1F5F9;border-radius:6px;height:12px;overflow:hidden;'>"
            f"<div style='width:{width:.1f}%;background:{color};height:100%;"
            f"border-radius:6px;'></div>"
            "</div>"
            "</div>"
        )

    st.markdown("".join(rows), unsafe_allow_html=True)


def render_score_gauge(score: int) -> None:
    """Render a large site score with a progress bar."""
    if score >= 70:
        color = SCORE_OK
        label = "Good"
    elif score >= 45:
        color = SCORE_WARNING
        label = "Needs Work"
    else:
        color = SCORE_CRITICAL
        label = "Critical"

    st.markdown(
        f"""
        <div style="text-align:center;padding:1rem 0;">
            <div style="font-size:0.85rem;color:#64748B;margin-bottom:0.25rem;">
                Overall Site Score
            </div>
            <div style="font-size:3.5rem;font-weight:800;color:{color};line-height:1;">
                {score}
            </div>
            <div style="font-size:0.9rem;color:{color};font-weight:600;">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(score / 100)
