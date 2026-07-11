"""Site-wide consolidated action plan — shared between Kontakt summary and export preview."""

from __future__ import annotations

import html as _html

import streamlit as st

from app.exports.report_data import collect_consolidated_issues, tier_counts
from app.models.page import PageData
from app.models.project import ProjectConfig
from app.utils.fix_classifier import tier_bg, tier_color, tier_label

_PRIORITY_STYLES = {
    "critical":  ("#FEE2E2", "#991B1B", "🔴"),
    "warning":   ("#FEF3C7", "#92400E", "🟡"),
    "quick_win": ("#D1FAE5", "#065F46", "🟢"),
}

_STRINGS = {
    "en": {
        "title": "Site-Wide Action Plan",
        "subtitle": (
            "All errors and warnings across every analysed page — with competitor context "
            "and fix packages (Basic / Advanced / Full Campaign)."
        ),
        "kontakt_title": "Extended Report Summary",
        "kontakt_subtitle": (
            "English summary of all site issues for client handoff. "
            "Matches the consolidated section at the end of the PDF export."
        ),
        "col_issue": "Issue / Finding",
        "col_priority": "Priority",
        "col_pages": "Page(s)",
        "col_comp": "Competitor match",
        "col_fix": "Fix package",
        "col_action": "Suggested action",
        "no_issues": "No errors or warnings found across all pages.",
        "no_comp": "—",
        "tier_legend": "Fix Package Legend",
        "basic_legend": "Basic — 1–3 h · text/content only · €10–50",
        "adv_legend": "Advanced — 1–3 days · CMS/HTML · €50–300",
        "all_legend": "Full Campaign — 2–4+ weeks · €300–1 000+",
        "count_label": "issues",
    },
    "de": {
        "title": "Aktionsplan — Gesamtübersicht",
        "subtitle": (
            "Alle Fehler und Warnungen auf allen geprüften Seiten — mit Wettbewerber-Kontext "
            "und Lösungspaketen (Basis / Fortgeschritten / Gesamtkampagne)."
        ),
        "kontakt_title": "Erweiterte Berichtszusammenfassung",
        "kontakt_subtitle": (
            "Zusammenfassung aller Website-Probleme für die Kundenübergabe."
        ),
        "col_issue": "Problem / Befund",
        "col_priority": "Priorität",
        "col_pages": "Seite(n)",
        "col_comp": "Wettbewerber-Match",
        "col_fix": "Lösungspaket",
        "col_action": "Empfohlene Maßnahme",
        "no_issues": "Keine Fehler oder Warnungen auf allen Seiten gefunden.",
        "no_comp": "—",
        "tier_legend": "Lösungspaket-Legende",
        "basic_legend": "Basis — 1–3 Std. · nur Text · €10–50",
        "adv_legend": "Fortgeschritten — 1–3 Tage · CMS/HTML · €50–300",
        "all_legend": "Gesamtkampagne — 2–4+ Wochen · €300–1 000+",
        "count_label": "Probleme",
    },
}


def _t(key: str, lang: str) -> str:
    return _STRINGS.get(lang, _STRINGS["en"]).get(key, key)


def render_consolidated_action_plan(
    project: ProjectConfig,
    pages: list[PageData],
    *,
    lang: str = "en",
    variant: str = "default",
    expanded: bool = True,
) -> None:
    """Render the site-wide issues table (same data as PDF final section).

    Args:
        variant: "default" or "kontakt" — kontakt uses English-specific headings.
    """
    analysed = [p for p in pages if p.extraction_complete]
    if not analysed:
        return

    issues = collect_consolidated_issues(analysed, project, lang)
    counts = tier_counts(issues)

    if variant == "kontakt":
        title = _STRINGS["en"]["kontakt_title"]
        subtitle = _STRINGS["en"]["kontakt_subtitle"]
        lang = "en"
    else:
        title = _t("title", lang)
        subtitle = _t("subtitle", lang)

    with st.expander(f"📋 {title} ({len(issues)} {_t('count_label', lang)})", expanded=expanded):
        st.caption(subtitle)

        # Tier legend
        legend_cols = st.columns(3)
        for col, (tier, legend_key) in zip(
            legend_cols,
            [("Basic", "basic_legend"), ("Advanced", "adv_legend"), ("All", "all_legend")],
        ):
            with col:
                bg = tier_bg(tier)  # type: ignore[arg-type]
                clr = tier_color(tier)  # type: ignore[arg-type]
                st.markdown(
                    f"<div style='background:{bg};border:1px solid {clr};"
                    f"border-radius:8px;padding:8px 10px;text-align:center;'>"
                    f"<div style='font-weight:700;color:{clr};font-size:0.82rem;'>"
                    f"{tier_label(tier, lang)}</div>"  # type: ignore[arg-type]
                    f"<div style='font-size:0.72rem;color:#475569;margin-top:2px;'>"
                    f"{_t(legend_key, lang)}</div>"
                    f"<div style='font-size:0.85rem;font-weight:700;color:{clr};margin-top:4px;'>"
                    f"{counts.get(tier, 0)}</div></div>",
                    unsafe_allow_html=True,
                )

        if not issues:
            st.success(_t("no_issues", lang))
            return

        # Build HTML table
        header = (
            f"<tr style='background:#1E293B;color:#F1F5F9;font-size:0.75rem;'>"
            f"<th style='padding:8px 10px;text-align:left;'>{_t('col_issue', lang)}</th>"
            f"<th style='padding:8px 6px;text-align:center;'>{_t('col_priority', lang)}</th>"
            f"<th style='padding:8px 6px;text-align:left;'>{_t('col_pages', lang)}</th>"
            f"<th style='padding:8px 6px;text-align:left;'>{_t('col_comp', lang)}</th>"
            f"<th style='padding:8px 6px;text-align:center;'>{_t('col_fix', lang)}</th>"
            f"<th style='padding:8px 6px;text-align:left;'>{_t('col_action', lang)}</th>"
            f"</tr>"
        )

        rows = ""
        for issue in issues:
            bg, fg, icon = _PRIORITY_STYLES.get(issue.priority, ("#F8FAFC", "#334155", "•"))
            prio_badge = (
                f"<span style='background:{bg};color:{fg};padding:2px 8px;"
                f"border-radius:9999px;font-size:0.7rem;font-weight:600;white-space:nowrap;'>"
                f"{icon} {issue.priority.replace('_', ' ').title()}</span>"
            )

            pages_html = "<br>".join(
                _html.escape(p) for p in sorted(issue.pages)
            )
            comp_html = (
                "<br>".join(f"✓ {_html.escape(d)}" for d in issue.competitors[:3])
                if issue.competitors else _t("no_comp", lang)
            )

            t_bg = tier_bg(issue.tier)
            t_clr = tier_color(issue.tier)
            t_name = tier_label(issue.tier, lang)
            tier_badge = (
                f"<span style='background:{t_bg};color:{t_clr};padding:2px 8px;"
                f"border-radius:9999px;font-size:0.7rem;font-weight:700;white-space:nowrap;'>"
                f"{_html.escape(t_name)}</span>"
            )

            action = _html.escape(
                (issue.suggested_fix or issue.problem or "")[:200]
            )

            rows += (
                f"<tr style='border-bottom:1px solid #E2E8F0;font-size:0.78rem;'>"
                f"<td style='padding:8px 10px;font-weight:600;color:#1E293B;vertical-align:top;'>"
                f"{_html.escape(issue.label)}</td>"
                f"<td style='padding:8px 6px;text-align:center;vertical-align:top;'>{prio_badge}</td>"
                f"<td style='padding:8px 6px;color:#64748B;vertical-align:top;'>{pages_html}</td>"
                f"<td style='padding:8px 6px;color:#64748B;vertical-align:top;'>{comp_html}</td>"
                f"<td style='padding:8px 6px;text-align:center;vertical-align:top;'>{tier_badge}</td>"
                f"<td style='padding:8px 6px;color:#475569;vertical-align:top;'>{action}</td>"
                f"</tr>"
            )

        table_html = (
            f"<div style='overflow-x:auto;margin-top:12px;'>"
            f"<table style='width:100%;border-collapse:collapse;background:#FFFFFF;"
            f"border-radius:8px;overflow:hidden;'>"
            f"{header}{rows}</table></div>"
        )
        st.markdown(table_html, unsafe_allow_html=True)
