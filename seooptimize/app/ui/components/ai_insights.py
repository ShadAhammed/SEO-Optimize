"""Competitor gap and AI consensus panels for Overview / Recommendations."""

from __future__ import annotations

import html

import streamlit as st

from app.models.page import PageData
from app.models.project import ProjectConfig

_FEATURE_LABELS = {
    "faq_section": "FAQ section",
    "whatsapp": "WhatsApp contact button",
    "reviews": "Review / rating signals",
    "schema": "Structured data (Schema.org)",
    "word_count": "Content depth (word count)",
    "meta_description": "Meta description",
    "h1": "H1 headline",
    "content_structure": "Content structure (H2 sections)",
}

_VERDICT_LABELS = {
    "agree": ("✅ Agrees", "#D1FAE5", "#065F46"),
    "strengthen": ("⬆️ Upgraded severity", "#DBEAFE", "#1E40AF"),
    "reject": ("❌ Disagrees", "#FEE2E2", "#991B1B"),
    "add": ("➕ Adds finding", "#EDE9FE", "#5B21B6"),
}

_AGREEMENT_LABELS = {
    "full_agreement": ("🤝 Both agree", "#D1FAE5", "#065F46"),
    "strengthened": ("⬆️ DeepSeek upgraded", "#DBEAFE", "#1E40AF"),
    "disagreement": ("⚖️ Disputed", "#FEF3C7", "#92400E"),
    "claude_only": ("🔵 Claude only", "#F1F5F9", "#475569"),
    "gemini_only": ("⚡ DeepSeek only", "#EDE9FE", "#5B21B6"),
    "partial": ("🔵 Partial review", "#F1F5F9", "#475569"),
}


def render_competitor_gaps(project: ProjectConfig, page: PageData) -> None:
    """Show what competitors have that this site lacks."""
    if not project.competitor_urls:
        return

    st.markdown("### 🏁 Competitor Gaps")
    st.caption(
        f"Comparing **{project.business_name}** against "
        f"{len(project.competitor_urls)} competitor site(s)."
    )

    if not page.ai_complete:
        st.info("Open this page to run AI analysis — competitor gaps appear here after analysis.")
        with st.expander("Configured competitors"):
            for url in project.competitor_urls:
                st.markdown(f"- {url}")
        return

    ai = page.ai_analysis or {}
    summary = ai.get("competitor_summary") or {}
    gap_counts = summary.get("competitor_gap_counts") or {}
    examples = summary.get("examples") or {}
    current = summary.get("current_site") or {}

    if not gap_counts:
        st.warning(
            "No competitor advantages detected yet, or analysis used cached data from "
            "before competitors were added. Switch to another page and back to refresh."
        )
        with st.expander("Configured competitors"):
            for url in project.competitor_urls:
                st.markdown(f"- {url}")
        return

    # Side-by-side: your site vs competitors
    col_you, col_them = st.columns(2)
    with col_you:
        st.markdown("**Your site (Fischer)**")
        _site_status_row("FAQ section", current.get("has_faq"))
        _site_status_row("Review signals", current.get("has_reviews"))
        _site_status_row("WhatsApp button", current.get("has_whatsapp"))
        schema = current.get("schema_status", "na")
        _site_status_row("Schema markup", schema == "pass", f"Status: {schema}")
        st.markdown(
            f"<div style='font-size:0.85rem;padding:4px 0;'>"
            f"H2 headings: <strong>{current.get('h2_count', 0)}</strong></div>",
            unsafe_allow_html=True,
        )

    with col_them:
        st.markdown("**What competitors have that you don't**")
        for feature, count in sorted(gap_counts.items(), key=lambda x: -x[1]):
            label = _FEATURE_LABELS.get(feature, feature.replace("_", " ").title())
            ex_list = examples.get(feature, [])
            example_html = ""
            if ex_list:
                example_html = (
                    f"<br><span style='font-size:0.78rem;color:#64748B;'>"
                    f"e.g. {html.escape(str(ex_list[0]))}</span>"
                )
            st.markdown(
                f"<div style='background:#FEF2F2;border-left:3px solid #DC2626;"
                f"padding:8px 12px;border-radius:4px;margin-bottom:6px;font-size:0.85rem;'>"
                f"<strong>{html.escape(label)}</strong><br>"
                f"{count} competitor(s) have this{example_html}</div>",
                unsafe_allow_html=True,
            )

    # Raw competitor gap details from crawl
    raw_gaps = ai.get("competitor_gaps") or []
    if raw_gaps:
        with st.expander("Per-competitor details"):
            for comp in raw_gaps:
                domain = comp.get("domain") or comp.get("url", "Competitor")
                features = comp.get("positive_features") or {}
                if not features:
                    continue
                st.markdown(f"**{domain}**")
                for feat, detail in features.items():
                    label = _FEATURE_LABELS.get(feat, feat.replace("_", " ").title())
                    st.markdown(f"- {label}: {detail}")


def render_ai_consensus_table(page: PageData) -> None:
    """Show each Claude finding with DeepSeek's agree/disagree verdict."""
    if not page.ai_complete:
        return

    ai = page.ai_analysis or {}
    annotations = ai.get("annotations") or []
    reviews = ai.get("gemini_reviews") or []
    rec_cards = ai.get("recommendation_cards") or []
    reviewer_label = ai.get("reviewer_label") or "DeepSeek"
    reviewer_active = ai.get("reviewer_active", False)
    reviewer_attempted = bool(ai.get("reviewer_attempted", False))
    reviewer_error = str(ai.get("reviewer_error", "") or "")

    st.markdown(f"### 🤝 AI Consensus — Claude vs {reviewer_label}")

    if not reviewer_active and not reviews:
        from app.main import _reload_settings, _has_deepseek_key

        deepseek_loaded = _has_deepseek_key(_reload_settings())
        if deepseek_loaded:
            if reviewer_attempted:
                st.warning(
                    f"{reviewer_label} was called but returned no structured review items for this page. "
                    "Use **Force AI refresh** and check logs for reviewer output format."
                )
                if reviewer_error:
                    st.caption(f"Reviewer error: {reviewer_error}")
            else:
                st.warning(
                    f"{reviewer_label} is configured but review was not attempted for this page yet. "
                    "This usually means cached Claude-only output. Click **Force AI refresh**."
                )
        else:
            st.warning(
                f"{reviewer_label} did not run for this page because no DeepSeek key was loaded. "
                "Set `DEEPSEEK_API_KEY` (or `DeepSeek_API_KEY`) in `.env`, restart the app, "
                "then re-open this page."
            )
        if annotations:
            st.markdown(f"Claude found **{len(annotations)}** issue(s) without a second review.")
        return

    if not annotations and not reviews:
        st.info("No AI findings to compare yet.")
        return

    review_by_selector = {r.get("selector", ""): r for r in reviews}
    card_by_selector = {c.get("selector", ""): c for c in rec_cards}

    rows_html = []
    for ann in annotations:
        selector = ann.get("selector", "")
        label = ann.get("label") or ann.get("issue", "")[:60]
        claude_priority = ann.get("priority", "warning")
        review = review_by_selector.get(selector)
        card = card_by_selector.get(selector)

        if review:
            verdict = review.get("gemini_verdict", "agree")
            verdict_text, v_bg, v_fg = _VERDICT_LABELS.get(
                verdict, ("—", "#F3F4F6", "#374151")
            )
            note = review.get("gemini_note", "")
        else:
            verdict_text, v_bg, v_fg = _AGREEMENT_LABELS["claude_only"]
            note = "No review returned for this finding"

        agreement = (card or {}).get("agreement_level", "claude_only")
        agr_text, a_bg, a_fg = _AGREEMENT_LABELS.get(
            agreement, _AGREEMENT_LABELS["claude_only"]
        )

        comp_evidence = (review or {}).get("competitor_evidence") or {}
        comp_cell = "<br>".join(
            f"<span style='font-size:0.75rem;'>{html.escape(k)}: {html.escape(str(v))}</span>"
            for k, v in comp_evidence.items()
        ) or "—"

        rows_html.append(
            f"<tr>"
            f"<td style='padding:8px;font-size:0.82rem;'>{html.escape(label)}</td>"
            f"<td style='padding:8px;text-align:center;'>"
            f"<span style='background:#FEE2E2;color:#991B1B;padding:2px 8px;"
            f"border-radius:9999px;font-size:0.75rem;font-weight:600;'>"
            f"{html.escape(claude_priority)}</span></td>"
            f"<td style='padding:8px;text-align:center;'>"
            f"<span style='background:{v_bg};color:{v_fg};padding:2px 8px;"
            f"border-radius:9999px;font-size:0.75rem;font-weight:600;'>"
            f"{verdict_text}</span></td>"
            f"<td style='padding:8px;text-align:center;'>"
            f"<span style='background:{a_bg};color:{a_fg};padding:2px 8px;"
            f"border-radius:9999px;font-size:0.75rem;font-weight:600;'>"
            f"{agr_text}</span></td>"
            f"<td style='padding:8px;font-size:0.78rem;color:#64748B;'>{html.escape(note)}</td>"
            f"<td style='padding:8px;font-size:0.78rem;'>{comp_cell}</td>"
            f"</tr>"
        )

    # DeepSeek-only findings (additional annotations merged into cards)
    claude_selectors = {a.get("selector") for a in annotations}
    for card in rec_cards:
        if card.get("agreement_level") != "gemini_only":
            continue
        selector = card.get("selector", "")
        if selector in claude_selectors:
            continue
        label = card.get("label") or card.get("problem", "")[:60]
        agr_text, a_bg, a_fg = _AGREEMENT_LABELS["gemini_only"]
        rows_html.append(
            f"<tr>"
            f"<td style='padding:8px;font-size:0.82rem;'>{html.escape(label)}</td>"
            f"<td style='padding:8px;text-align:center;color:#94A3B8;'>—</td>"
            f"<td style='padding:8px;text-align:center;'>"
            f"<span style='background:#EDE9FE;color:#5B21B6;padding:2px 8px;"
            f"border-radius:9999px;font-size:0.75rem;font-weight:600;'>➕ Adds finding</span></td>"
            f"<td style='padding:8px;text-align:center;'>"
            f"<span style='background:{a_bg};color:{a_fg};padding:2px 8px;"
            f"border-radius:9999px;font-size:0.75rem;font-weight:600;'>"
            f"{agr_text}</span></td>"
            f"<td style='padding:8px;font-size:0.78rem;color:#64748B;'>"
            f"{html.escape(card.get('gemini_note', ''))}</td>"
            f"<td style='padding:8px;font-size:0.78rem;'>—</td>"
            f"</tr>"
        )

    table = (
        "<table style='width:100%;border-collapse:collapse;margin-top:8px;'>"
        "<thead><tr style='background:#F8FAFC;border-bottom:2px solid #E2E8F0;'>"
        "<th style='padding:8px;text-align:left;font-size:0.78rem;'>Finding</th>"
        "<th style='padding:8px;text-align:center;font-size:0.78rem;'>Claude</th>"
        f"<th style='padding:8px;text-align:center;font-size:0.78rem;'>{html.escape(reviewer_label)}</th>"
        "<th style='padding:8px;text-align:center;font-size:0.78rem;'>Consensus</th>"
        "<th style='padding:8px;text-align:left;font-size:0.78rem;'>Reviewer note</th>"
        "<th style='padding:8px;text-align:left;font-size:0.78rem;'>Competitor evidence</th>"
        "</tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table>"
    )
    st.markdown(table, unsafe_allow_html=True)
    st.caption(
        "Full recommended fixes are on the **💡 Recommendations** tab. "
        "Expand each card there for suggested text and competitor quotes."
    )


def _site_status_row(label: str, has_it: bool, extra: str = "") -> None:
    icon = "✅" if has_it else "❌"
    color = "#065F46" if has_it else "#991B1B"
    detail = extra or ("Present" if has_it else "Missing")
    st.markdown(
        f"<div style='font-size:0.85rem;padding:4px 0;color:{color};'>"
        f"{icon} <strong>{html.escape(label)}</strong> — {html.escape(detail)}</div>",
        unsafe_allow_html=True,
    )
