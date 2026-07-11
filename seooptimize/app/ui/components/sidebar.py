"""Left sidebar — project explorer, page tree, per-page scores, competitor panel."""

from __future__ import annotations

import html as _html

import streamlit as st

from app.models.page import PageData, ScoreStatus
from app.models.project import ProjectConfig
from app.ui.app_state import render_export_lang_selector, reset_export_lang

# Sentinel value for left-sidebar "Summary" navigation (not a real URL).
SITE_SUMMARY_ID = "__site_summary__"


def _score_color(score: int) -> str:
    if score >= 70:
        return "#16A34A"
    if score >= 45:
        return "#D97706"
    return "#DC2626"


def _status_icon(status: ScoreStatus) -> str:
    return {"pass": "✅", "warn": "⚠️", "fail": "❌", "na": "—"}.get(status.value, "—")


def render_sidebar(
    project: ProjectConfig | None,
    pages: list[PageData],
    selected_url: str | None,
    competitor_sources: list[dict] | None = None,
) -> str | None:
    """Render the sidebar and return the URL the user clicks on.

    Returns:
        The URL of the page selected by the user, or None if unchanged.
    """
    with st.sidebar:
        # ── Header ──────────────────────────────────────────────────────────
        st.markdown(
            """
            <div style="padding: 1rem 0 0.5rem 0;">
                <span style="font-size:1.4rem;font-weight:700;color:#3B82F6;">SEO</span>
                <span style="font-size:1.4rem;font-weight:700;color:#CBD5E1;">Optimize</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if project:
            st.markdown(
                f"<div style='font-size:0.75rem;color:#64748B;margin-bottom:1rem;'>"
                f"📁 {project.business_name}</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Navigation ────────────────────────────────────────────────────
        st.markdown(
            "<p class='section-label' style='color:#64748B;font-size:0.65rem;"
            "font-weight:700;letter-spacing:0.08em;text-transform:uppercase;'>Project</p>",
            unsafe_allow_html=True,
        )

        clicked_url: str | None = None
        summary_selected = selected_url == SITE_SUMMARY_ID

        if not pages:
            st.markdown(
                "<div style='color:#64748B;font-size:0.8rem;padding:0.5rem 0;'>"
                "No pages analysed yet.</div>",
                unsafe_allow_html=True,
            )
        else:
            analysed_count = sum(1 for p in pages if p.extraction_complete)
            if st.button(
                "📋 Summary",
                key="nav_site_summary",
                use_container_width=True,
                type="primary" if summary_selected else "secondary",
                disabled=analysed_count == 0,
                help="Site-wide action plan — all errors, warnings, competitor matches, fix packages",
            ):
                clicked_url = SITE_SUMMARY_ID

            st.markdown(
                "<p style='color:#64748B;font-size:0.6rem;font-weight:600;"
                "letter-spacing:0.06em;text-transform:uppercase;margin:8px 0 4px;'>"
                "Pages</p>",
                unsafe_allow_html=True,
            )

            for page in pages:
                score = int(page.scores.total)
                color = _score_color(score)
                label = _page_label(page)
                is_selected = page.url == selected_url and not summary_selected

                col1, col2 = st.columns([4, 1])
                with col1:
                    if st.button(
                        label,
                        key=f"nav_{page.url}",
                        use_container_width=True,
                        type="primary" if is_selected else "secondary",
                    ):
                        clicked_url = page.url
                with col2:
                    st.markdown(
                        f"<div style='text-align:center;color:{color};"
                        f"font-weight:700;font-size:0.8rem;padding-top:0.5rem;'>"
                        f"{score}</div>",
                        unsafe_allow_html=True,
                    )

        st.divider()

        # ── Site-level stats ──────────────────────────────────────────────
        if pages:
            scores = [int(p.scores.total) for p in pages if p.extraction_complete]
            if scores:
                avg = sum(scores) // len(scores)
                color = _score_color(avg)
                st.markdown(
                    f"<div style='margin-bottom:0.5rem;'>"
                    f"<span style='color:#94A3B8;font-size:0.75rem;'>Site Average</span>"
                    f"<br><span style='font-size:1.6rem;font-weight:700;color:{color};'>"
                    f"{avg}</span>"
                    f"<span style='font-size:0.75rem;color:#64748B;'>/100</span></div>",
                    unsafe_allow_html=True,
                )

        st.divider()

        # ── Competitor comparison panel ────────────────────────────────────
        if project and project.competitor_urls:
            _render_competitor_panel(project, pages, competitor_sources or [])
            st.divider()

        # ── Export ─────────────────────────────────────────────────
        if pages and any(p.ai_complete for p in pages):
            st.markdown(
                "<p style='color:#64748B;font-size:0.65rem;font-weight:700;"
                "letter-spacing:0.08em;text-transform:uppercase;margin:0 0 4px;'>"
                "Report Language</p>",
                unsafe_allow_html=True,
            )
            render_export_lang_selector(project)

            if st.button("📄 Export Report", use_container_width=True, type="primary"):
                st.session_state["trigger_export"] = True

        # ── Settings link ─────────────────────────────────────────────────
        if st.button("⚙️ New Project", use_container_width=True):
            st.session_state["view"] = "setup"
            st.session_state["project"] = None
            st.session_state["pages"] = []
            st.session_state["selected_url"] = None
            st.session_state["show_competitor_intel"] = False
            st.session_state.pop("export_pdf_cache", None)
            reset_export_lang(None)
            st.rerun()

    return clicked_url


# ── Competitor Intelligence Panel ─────────────────────────────────────────────

# Features checked: (extracted_key, display_label, icon)
_COMP_FEATURES: list[tuple[str, str, str]] = [
    ("has_faq",      "FAQ section",          "❓"),
    ("has_reviews",  "Google Reviews",        "⭐"),
    ("has_whatsapp", "WhatsApp button",        "💬"),
    ("has_schema",   "Structured data",        "🗂️"),
    ("has_phone",    "Phone number",           "📞"),
]


def _client_signals(pages: list[PageData]) -> dict[str, bool]:
    """Derive current-site feature flags from extraction or AI summary."""
    for page in pages:
        if page.ai_complete and page.ai_analysis:
            s = (page.ai_analysis.get("competitor_summary") or {}).get("current_site") or {}
            if s:
                return {
                    "has_faq":      bool(s.get("has_faq")),
                    "has_reviews":  bool(s.get("has_reviews")),
                    "has_whatsapp": bool(s.get("has_whatsapp")),
                    "has_schema":   s.get("schema_status") == "pass",
                    "has_phone":    True,
                }
    for page in pages:
        if page.extraction_complete and page.local_seo:
            ls = page.local_seo
            return {
                "has_faq":      bool(getattr(ls, "has_faq", False)),
                "has_reviews":  bool(getattr(ls, "has_review_signals", False)),
                "has_whatsapp": bool(getattr(ls, "has_whatsapp", False)),
                "has_schema":   bool(getattr(ls, "has_local_business_schema", False)),
                "has_phone":    True,
            }
    return {}


def _render_competitor_panel(
    project: ProjectConfig,
    pages: list[PageData],
    competitor_sources: list[dict],
) -> None:
    """Competitor Intelligence section in the sidebar (SEOArch.md §Issue 6)."""
    from urllib.parse import urlparse as _up

    st.markdown(
        "<p style='color:#64748B;font-size:0.65rem;font-weight:700;"
        "letter-spacing:0.08em;text-transform:uppercase;margin:0 0 4px;'>"
        "Competitor Intelligence</p>",
        unsafe_allow_html=True,
    )

    if not competitor_sources:
        for url in project.competitor_urls[:5]:
            domain = _up(url).netloc or url
            st.markdown(
                f"<div style='font-size:0.74rem;color:#94A3B8;padding:1px 0;'>"
                f"⏳ {_html.escape(domain)}</div>",
                unsafe_allow_html=True,
            )
        st.caption("Run analysis to populate competitor data.")
        return

    client = _client_signals(pages)

    # ── Per-competitor rows ───────────────────────────────────────────────────
    any_gap = False
    for comp in competitor_sources[:5]:
        domain = comp.get("domain") or _up(comp.get("url", "")).netloc
        gaps = [
            f"{icon} {label}"
            for key, label, icon in _COMP_FEATURES
            if comp.get(key) and not client.get(key, True)
        ]
        any_gap = any_gap or bool(gaps)

        gap_html = (
            "".join(
                f"<div style='font-size:0.7rem;color:#FCA5A5;line-height:1.6;'>{_html.escape(g)}</div>"
                for g in gaps
            )
            if gaps
            else "<div style='font-size:0.7rem;color:#4ADE80;'>✓ No gaps found</div>"
        )
        st.markdown(
            f"<div style='margin-bottom:8px;padding:6px 8px;"
            f"background:#1E293B;border-radius:6px;'>"
            f"<div style='font-size:0.74rem;font-weight:600;color:#CBD5E1;"
            f"margin-bottom:3px;'>{_html.escape(domain)}</div>"
            f"{gap_html}</div>",
            unsafe_allow_html=True,
        )

    # ── Competitor Intelligence button → full comparison view ─────────────────
    if st.button(
        "📊 View Full Comparison",
        key="sidebar_comp_intel_btn",
        use_container_width=True,
    ):
        st.session_state["show_competitor_intel"] = True

    if not any_gap:
        st.caption("No competitive gaps detected — client leads on all checked signals.")


def _page_label(page: PageData) -> str:
    """Short human-readable label for a page URL."""
    from urllib.parse import urlparse

    path = urlparse(page.url).path.strip("/")
    if not path:
        return "🏠 Homepage"
    parts = path.split("/")
    label = parts[-1].replace("-", " ").replace("_", " ").title()
    return f"📄 {label}" if label else "📄 /"
