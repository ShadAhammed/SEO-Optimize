"""Overview page — M10 executive dashboard."""

from __future__ import annotations

import streamlit as st

from app.models.page import PageData, ScoreStatus
from app.models.project import ProjectConfig
from app.ui.components.ai_insights import render_ai_consensus_table, render_competitor_gaps
from app.ui.components.score_display import (
    render_score_gauge,
    render_six_axis_chart,
    score_badge,
    status_pill,
)
from app.utils.friendly_text import format_priority_actions


def render_overview_page(page: PageData, project: ProjectConfig) -> None:
    """Render the overview dashboard for one page."""
    st.markdown(f"## Overview — {_short_url(page.url)}")

    col_score, col_top = st.columns([1, 2])
    with col_score:
        render_score_gauge(int(page.scores.total))
    with col_top:
        priority_actions = _priority_actions_text(page)
        if priority_actions:
            st.markdown("**Top Priority Actions**")
            st.markdown(priority_actions)
        else:
            st.markdown("**Status**")
            if page.ai_complete:
                st.success("AI analysis complete")
            elif page.extraction_complete:
                st.warning("Awaiting AI analysis")
            else:
                st.error("Not yet analysed")

    # ── AI Collaboration Status ──────────────────────────────────────────────
    if page.ai_complete and page.ai_analysis:
        _render_ai_status_banner(page)

    # ── Competitor gaps (what competitors have that you don't) ───────────────
    if project.competitor_urls:
        st.markdown("---")
        render_competitor_gaps(project, page)

    # ── Claude vs DeepSeek agree / disagree table ────────────────────────────
    if page.ai_complete:
        st.markdown("---")
        render_ai_consensus_table(page)

    st.markdown("---")
    st.markdown("### Score Breakdown")
    render_six_axis_chart(page.scores)

    # ── Axis breakdown table ─────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    axes = [
        ("Local SEO", page.scores.local_seo, 30),
        ("Content Quality", page.scores.content_quality, 25),
        ("Technical SEO", page.scores.technical_seo, 15),
        ("Conversion Signals", page.scores.conversion_signals, 15),
        ("On-Page Metadata", page.scores.on_page_metadata, 10),
        ("Competitor Gap", page.scores.competitor_gap, 5),
    ]
    for i, (label, val, max_v) in enumerate(axes):
        col = col_a if i % 2 == 0 else col_b
        with col:
            pct = val / max_v if max_v else 0
            status = "ok" if pct >= 0.7 else ("warn" if pct >= 0.45 else "critical")
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;"
                f"align-items:center;padding:4px 0;border-bottom:1px solid #F1F5F9;'>"
                f"<span style='font-size:0.85rem;'>{label}</span>"
                f"<span>{_axis_badge(val, max_v, status)}</span></div>",
                unsafe_allow_html=True,
            )

    # ── Critical issues list ─────────────────────────────────────────────────
    st.markdown("---")
    ext = page.extracted
    fail_fields = _get_fail_fields(ext)
    warn_fields = _get_warn_fields(ext)

    if fail_fields:
        st.markdown(f"### 🔴 Critical Issues ({len(fail_fields)})")
        for field, note in fail_fields:
            st.markdown(
                f"<div style='background:#FEF2F2;border-left:3px solid #DC2626;"
                f"padding:8px 12px;border-radius:4px;margin-bottom:6px;font-size:0.85rem;'>"
                f"<strong>{field}</strong> — {note}</div>",
                unsafe_allow_html=True,
            )

    if warn_fields:
        st.markdown(f"### 🟡 Warnings ({len(warn_fields)})")
        for field, note in warn_fields:
            st.markdown(
                f"<div style='background:#FFFBEB;border-left:3px solid #D97706;"
                f"padding:8px 12px;border-radius:4px;margin-bottom:6px;font-size:0.85rem;'>"
                f"<strong>{field}</strong> — {note}</div>",
                unsafe_allow_html=True,
            )

    if not fail_fields and not warn_fields and page.extraction_complete:
        st.success("No critical issues or warnings detected on this page.")


def _axis_badge(value: float, max_v: float, status: str) -> str:
    colors = {
        "ok": ("#D1FAE5", "#065F46"),
        "warn": ("#FEF3C7", "#92400E"),
        "critical": ("#FEE2E2", "#991B1B"),
    }
    bg, fg = colors.get(status, ("#F3F4F6", "#374151"))
    return (
        f"<span style='background:{bg};color:{fg};padding:2px 8px;"
        f"border-radius:9999px;font-weight:700;font-size:0.75rem;'>"
        f"{value:.0f}/{max_v}</span>"
    )


def _get_fail_fields(ext) -> list[tuple[str, str]]:
    result = []
    field_labels = {
        "meta_title": "Meta Title",
        "meta_description": "Meta Description",
        "h1": "H1 Tag",
        "h2_structure": "H2 Structure",
        "word_count": "Word Count",
        "images_with_alt": "Image Alt Text",
        "phone_above_fold": "Phone (Above Fold)",
        "schema_markup": "Schema Markup",
        "canonical_tag": "Canonical Tag",
        "mobile_viewport": "Mobile Viewport",
        "nap_on_page": "NAP on Page",
        "internal_links": "Internal Links",
        "page_load_time": "Page Load Time",
        "https": "HTTPS",
    }
    for attr, label in field_labels.items():
        field = getattr(ext, attr, None)
        if field and field.status == ScoreStatus.FAIL:
            result.append((label, field.note or "Needs attention"))
    return result


def _get_warn_fields(ext) -> list[tuple[str, str]]:
    result = []
    field_labels = {
        "meta_title": "Meta Title",
        "meta_description": "Meta Description",
        "h1": "H1 Tag",
        "h2_structure": "H2 Structure",
        "word_count": "Word Count",
        "images_with_alt": "Image Alt Text",
        "phone_above_fold": "Phone (Above Fold)",
        "schema_markup": "Schema Markup",
        "canonical_tag": "Canonical Tag",
        "nap_on_page": "NAP on Page",
        "internal_links": "Internal Links",
        "page_load_time": "Page Load Time",
    }
    for attr, label in field_labels.items():
        field = getattr(ext, attr, None)
        if field and field.status == ScoreStatus.WARN:
            result.append((label, field.note or "Improvement available"))
    return result


def _priority_actions_text(page: PageData) -> str:
    """Show plain-language bullets even for older cached AI results."""
    annotations = page.ai_analysis.get("annotations", [])
    if annotations:
        from types import SimpleNamespace

        objects = [SimpleNamespace(**ann) for ann in annotations]
        return format_priority_actions(objects)
    return page.ai_analysis.get("top_priority_action", "")


def _short_url(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    path = p.path.strip("/")
    return f"{p.netloc}/{path}" if path else p.netloc


def _render_ai_status_banner(page: PageData) -> None:
    """Show a concise AI collaboration summary — which models ran and what each found."""
    ai = page.ai_analysis or {}
    annotations = ai.get("annotations", [])
    gemini_reviews = ai.get("gemini_reviews", [])
    rec_cards = ai.get("recommendation_cards", [])

    # Count agreement levels from recommendation cards
    full_agreement = sum(
        1 for c in rec_cards if c.get("agreement_level") == "full_agreement"
    )
    strengthened = sum(
        1 for c in rec_cards if c.get("agreement_level") == "strengthened"
    )
    claude_only = sum(
        1 for c in rec_cards if c.get("agreement_level") == "claude_only"
    )
    deepseek_only = sum(
        1 for c in rec_cards if c.get("agreement_level") == "gemini_only"
    )
    disagreements = sum(
        1 for c in rec_cards if c.get("agreement_level") == "disagreement"
    )

    has_reviewer = len(gemini_reviews) > 0 or (full_agreement + strengthened + deepseek_only) > 0
    claude_count = len(annotations)
    total_cards = len(rec_cards)

    if has_reviewer:
        reviewer_label = "DeepSeek"
        st.markdown(
            f"<div style='background:linear-gradient(135deg,#EFF6FF,#F0FDF4);"
            f"border:1px solid #BFDBFE;border-radius:8px;padding:12px 16px;"
            f"margin:8px 0 16px 0;'>"
            f"<div style='font-weight:700;font-size:0.9rem;color:#1E40AF;margin-bottom:8px;'>"
            f"🤝 Claude + {reviewer_label} — Dual-AI Consensus Active</div>"
            f"<div style='display:flex;gap:16px;flex-wrap:wrap;font-size:0.8rem;color:#374151;'>"
            f"<span>📊 <strong>{claude_count}</strong> Claude findings</span>"
            f"<span>🔍 <strong>{len(gemini_reviews)}</strong> {reviewer_label} reviews</span>"
            f"<span>✅ <strong>{full_agreement}</strong> both agreed</span>"
            f"<span>⬆️ <strong>{strengthened}</strong> upgraded by {reviewer_label}</span>"
            f"{'<span>⚡ <strong>' + str(deepseek_only) + '</strong> ' + reviewer_label + '-only findings</span>' if deepseek_only else ''}"
            f"{'<span>⚖️ <strong>' + str(disagreements) + '</strong> disputed</span>' if disagreements else ''}"
            f"<span>📋 <strong>{total_cards}</strong> total recommendations</span>"
            f"</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div style='background:#FFFBEB;border:1px solid #FDE68A;"
            f"border-radius:8px;padding:12px 16px;margin:8px 0 16px 0;'>"
            f"<div style='font-weight:700;font-size:0.9rem;color:#92400E;margin-bottom:4px;'>"
            f"⚠️ Claude Only — DeepSeek Reviewer Not Active</div>"
            f"<div style='font-size:0.8rem;color:#78350F;'>"
            f"Add <code>DEEPSEEK_API_KEY</code> to your .env file to enable dual-AI consensus. "
            f"Claude found <strong>{claude_count}</strong> issues.</div></div>",
            unsafe_allow_html=True,
        )
