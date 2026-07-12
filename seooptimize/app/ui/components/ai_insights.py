"""Competitor comparison table and AI findings panel for Overview / Recommendations."""

from __future__ import annotations

import html

import streamlit as st

from app.models.page import PageData
from app.models.project import ProjectConfig

_FEATURE_LABELS: dict[str, str] = {
    "faq_section": "FAQ Section",
    "whatsapp": "WhatsApp Button",
    "reviews": "Review / Rating Signals",
    "schema": "Structured Data (Schema)",
    "word_count": "Content Depth (words)",
    "meta_description": "Meta Description",
    "h1": "H1 Headline",
    "content_structure": "H2 Section Structure",
}

# Competitor feature keys that map to current_site boolean fields
_FEATURE_TO_CURRENT: dict[str, tuple[str, str | None]] = {
    # (current_site key, optional fallback)
    "faq_section":       ("has_faq", None),
    "whatsapp":          ("has_whatsapp", None),
    "reviews":           ("has_reviews", None),
    "schema":            ("schema_status", "pass"),
    "content_structure": ("h2_count", None),
    "word_count":        (None, None),
    "meta_description":  (None, None),
    "h1":                (None, None),
}

_PRIORITY_COLORS = {
    "critical":  ("#FEE2E2", "#991B1B"),
    "warning":   ("#FEF3C7", "#92400E"),
    "quick_win": ("#D1FAE5", "#065F46"),
    "ok":        ("#F1F5F9", "#475569"),
}


def _fischer_has(feature: str, current: dict) -> bool | None:
    """Return True/False/None (None = unknown) for whether Fischer has a feature."""
    mapping = _FEATURE_TO_CURRENT.get(feature)
    if not mapping:
        return None
    key, pass_val = mapping
    if not key:
        return None
    val = current.get(key)
    if val is None:
        return None
    if pass_val is not None:
        return val == pass_val
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val > 0
    return None


def _bool_cell(value: bool | None, *, good: str = "✅ Yes", bad: str = "❌ No") -> str:
    if value is True:
        return f"<span style='color:#065F46;font-weight:600;'>{good}</span>"
    if value is False:
        return f"<span style='color:#991B1B;font-weight:600;'>{bad}</span>"
    return "<span style='color:#94A3B8;'>—</span>"


def render_competitor_gaps(project: ProjectConfig, page: PageData) -> None:
    """Show a Feature / Competitors / Fischer comparison table."""
    if not project.competitor_urls:
        return

    n_comp = len(project.competitor_urls)
    st.markdown("### 🏁 Competitor Comparison")
    st.caption(
        f"**{html.escape(project.business_name)}** vs "
        f"**{n_comp} competitor(s)**"
    )

    if not page.ai_complete:
        st.info("Open this page to run AI analysis — the comparison table appears after analysis.")
        with st.expander("Configured competitors"):
            for url in project.competitor_urls:
                st.markdown(f"- {url}")
        return

    ai = page.ai_analysis or {}
    summary = ai.get("competitor_summary") or {}
    gap_counts: dict[str, int] = summary.get("competitor_gap_counts") or {}
    examples: dict[str, list] = summary.get("examples") or {}
    current: dict = summary.get("current_site") or {}

    if not gap_counts and not current:
        st.warning(
            "No competitor data yet. This can happen with cached analysis from before "
            "competitors were added — click **Force AI refresh** in the sidebar."
        )
        with st.expander("Configured competitors"):
            for url in project.competitor_urls:
                st.markdown(f"- {url}")
        return

    # Build rows: union of known features (from gap_counts) + always-shown fields
    all_features: list[str] = list({
        *gap_counts.keys(),
        "faq_section", "whatsapp", "reviews", "schema", "content_structure",
    })
    # Sort: most-competitors-have first, then alphabetical
    all_features.sort(key=lambda f: (-gap_counts.get(f, 0), f))

    rows_html = ""
    for feature in all_features:
        label = _FEATURE_LABELS.get(feature, feature.replace("_", " ").title())
        count = gap_counts.get(feature, 0)
        fischer_val = _fischer_has(feature, current)

        # Competitors cell: "N / M competitors ✅" or "—"
        if count > 0:
            comp_cell = (
                f"<span style='color:#065F46;font-weight:600;'>"
                f"✅ {count} / {n_comp}</span>"
            )
            ex_list = examples.get(feature, [])
            if ex_list:
                comp_cell += (
                    f"<br><span style='font-size:0.75rem;color:#64748B;'>"
                    f"e.g. {html.escape(str(ex_list[0])[:60])}</span>"
                )
        else:
            comp_cell = "<span style='color:#94A3B8;'>0 / " + str(n_comp) + "</span>"

        # Fischer cell
        if fischer_val is True:
            fischer_cell = "<span style='color:#065F46;font-weight:600;'>✅ Yes</span>"
            row_bg = "#FFFFFF"
        elif fischer_val is False:
            fischer_cell = "<span style='color:#991B1B;font-weight:600;'>❌ Missing</span>"
            row_bg = "#FFF7F7" if count > 0 else "#FFFFFF"
        else:
            fischer_cell = "<span style='color:#94A3B8;'>—</span>"
            row_bg = "#FFFFFF"

        rows_html += (
            f"<tr style='background:{row_bg};border-bottom:1px solid #E2E8F0;'>"
            f"<td style='padding:10px 12px;font-size:0.84rem;font-weight:600;"
            f"color:#1E293B;'>{html.escape(label)}</td>"
            f"<td style='padding:10px 12px;font-size:0.84rem;'>{comp_cell}</td>"
            f"<td style='padding:10px 12px;font-size:0.84rem;'>{fischer_cell}</td>"
            f"</tr>"
        )

    table_html = (
        "<div style='overflow-x:auto;margin-top:8px;'>"
        "<table style='width:100%;border-collapse:collapse;background:#FFFFFF;"
        "border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.06);'>"
        "<thead><tr style='background:#1E293B;color:#F1F5F9;'>"
        "<th style='padding:10px 12px;text-align:left;font-size:0.78rem;"
        "font-weight:700;letter-spacing:0.04em;'>Feature</th>"
        "<th style='padding:10px 12px;text-align:left;font-size:0.78rem;"
        f"font-weight:700;letter-spacing:0.04em;'>Competitors ({n_comp})</th>"
        f"<th style='padding:10px 12px;text-align:left;font-size:0.78rem;"
        f"font-weight:700;letter-spacing:0.04em;'>{html.escape(project.business_name)}</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

    # Per-competitor raw detail (collapsed)
    raw_gaps = ai.get("competitor_gaps") or []
    if raw_gaps:
        with st.expander("Per-competitor details"):
            for comp in raw_gaps:
                domain = comp.get("domain") or comp.get("url", "Competitor")
                features = comp.get("positive_features") or {}
                if not features:
                    continue
                st.markdown(f"**{html.escape(str(domain))}**")
                for feat, detail in features.items():
                    lbl = _FEATURE_LABELS.get(feat, feat.replace("_", " ").title())
                    st.markdown(f"- {lbl}: {detail}")


def render_ai_consensus_table(page: PageData) -> None:
    """Show confirmed AI findings (warnings + errors agreed by all active models)."""
    if not page.ai_complete:
        return

    ai = page.ai_analysis or {}
    rec_cards = ai.get("recommendation_cards") or []

    st.markdown("### 🤝 Confirmed AI Findings")

    # Filter to only actionable cards (critical / warning / quick_win)
    actionable = [
        c for c in rec_cards
        if c.get("priority") in ("critical", "warning", "quick_win")
    ]

    if not actionable:
        st.info("No warnings or errors confirmed across all active AI models.")
        return

    n_reviewers = len([
        1 for k in ("reviewer_active", "gemini_reviewer_active")
        if ai.get(k)
    ])
    reviewer_label = ai.get("reviewer_label") or "AI reviewers"
    st.caption(
        f"The table below shows only findings confirmed by Claude"
        + (f" and {reviewer_label}" if n_reviewers else "")
        + ". Items disagreed upon are filtered out."
    )

    rows_html = ""
    priority_order = {"critical": 0, "warning": 1, "quick_win": 2}
    actionable.sort(key=lambda c: priority_order.get(c.get("priority", "warning"), 9))

    for card in actionable:
        priority = card.get("priority", "warning")
        label = html.escape(card.get("label") or card.get("problem", "")[:60])
        problem = html.escape((card.get("problem") or "")[:120])
        bg, fg = _PRIORITY_COLORS.get(priority, ("#F1F5F9", "#475569"))
        icon = {"critical": "🔴", "warning": "🟡", "quick_win": "🟢"}.get(priority, "•")
        priority_badge = (
            f"<span style='background:{bg};color:{fg};padding:2px 8px;"
            f"border-radius:9999px;font-size:0.72rem;font-weight:700;white-space:nowrap;'>"
            f"{icon} {priority.replace('_', ' ').title()}</span>"
        )

        comp_evidence = card.get("competitor_evidence") or {}
        comp_html = "<br>".join(
            f"<span style='font-size:0.74rem;'><strong>{html.escape(k)}:</strong> "
            f"{html.escape(str(v)[:80])}</span>"
            for k, v in list(comp_evidence.items())[:3]
        ) or "—"

        rows_html += (
            f"<tr style='border-bottom:1px solid #E2E8F0;'>"
            f"<td style='padding:10px 12px;font-weight:600;font-size:0.83rem;"
            f"color:#1E293B;vertical-align:top;'>{label}</td>"
            f"<td style='padding:10px 8px;text-align:center;vertical-align:top;'>"
            f"{priority_badge}</td>"
            f"<td style='padding:10px 12px;font-size:0.80rem;color:#475569;"
            f"vertical-align:top;'>{problem}</td>"
            f"<td style='padding:10px 12px;font-size:0.80rem;color:#64748B;"
            f"vertical-align:top;'>{comp_html}</td>"
            f"</tr>"
        )

    table = (
        "<div style='overflow-x:auto;margin-top:8px;'>"
        "<table style='width:100%;border-collapse:collapse;background:#FFFFFF;"
        "border-radius:8px;overflow:hidden;'>"
        "<thead><tr style='background:#1E293B;color:#F1F5F9;'>"
        "<th style='padding:10px 12px;text-align:left;font-size:0.78rem;'>Finding</th>"
        "<th style='padding:10px 8px;text-align:center;font-size:0.78rem;'>Severity</th>"
        "<th style='padding:10px 12px;text-align:left;font-size:0.78rem;'>Problem</th>"
        "<th style='padding:10px 12px;text-align:left;font-size:0.78rem;'>Competitor evidence</th>"
        "</tr></thead><tbody>"
        + rows_html
        + "</tbody></table></div>"
    )
    st.markdown(table, unsafe_allow_html=True)
    st.caption(
        "Full fix suggestions are on the **💡 Recommendations** tab."
    )


