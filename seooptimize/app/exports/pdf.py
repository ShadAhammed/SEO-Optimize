"""PDF Export Engine — M12.

Generates a professional customer-facing PDF report.
All pages are combined into one document: cover → executive summary →
site audit table → per-page sections → consolidated issues + fix plan.

Args for generate_pdf_report:
    lang: "en" (default) or "de" — language for all section headings/labels.
"""

from __future__ import annotations

import html
import io
from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.models.page import PageData, ScoreStatus
from app.models.project import ProjectConfig
from app.exports.report_data import (
    collect_consolidated_issues,
    pick_competitor_data,
)
from app.utils.fix_classifier import (
    FixTier,
    classify_fix,
    tier_bg,
    tier_color,
    tier_desc,
    tier_label,
)
from app.utils.friendly_text import humanize_selector

logger = get_logger(__name__)


# ── Bilingual strings ─────────────────────────────────────────────────────────

_T: dict[str, dict[str, str]] = {
    "report_title":         {"en": "SEO Audit Report",           "de": "SEO-Prüfbericht"},
    "overall_score":        {"en": "Overall Site Score / 100",   "de": "Gesamtpunktzahl / 100"},
    "business":             {"en": "Business",                   "de": "Unternehmen"},
    "service_area":         {"en": "Service Area",               "de": "Servicegebiet"},
    "website":              {"en": "Website",                    "de": "Webseite"},
    "report_date":          {"en": "Report Date",                "de": "Berichtsdatum"},
    "pages_audited":        {"en": "Pages Audited",              "de": "Geprüfte Seiten"},
    "exec_summary":         {"en": "Executive Summary",          "de": "Zusammenfassung"},
    "critical_issues":      {"en": "Critical Issues",            "de": "Kritische Probleme"},
    "warnings":             {"en": "Warnings",                   "de": "Warnungen"},
    "score_breakdown":      {"en": "Score Breakdown by Axis",    "de": "Punktzahl nach Bereich"},
    "pages_at_glance":      {"en": "Pages At a Glance",          "de": "Seitenübersicht"},
    "area":                 {"en": "Area",                       "de": "Bereich"},
    "score":                {"en": "Score",                      "de": "Punkte"},
    "performance":          {"en": "Performance",                "de": "Leistung"},
    "page":                 {"en": "Page",                       "de": "Seite"},
    "critical":             {"en": "Critical",                   "de": "Kritisch"},
    "warning_h":            {"en": "Warnings",                   "de": "Warnungen"},
    "status":               {"en": "Status",                     "de": "Status"},
    "comp_gap_analysis":    {"en": "Competitor Gap Analysis",    "de": "Wettbewerber-Lückenanalyse"},
    "compared":             {"en": "Compared",                   "de": "Verglichen"},
    "against":              {"en": "against",                    "de": "mit"},
    "competitor_sites":     {"en": "competitor site(s) you provided.", "de": "von Ihnen angegebene(n) Wettbewerber-Seite(n)."},
    "configured_comp":      {"en": "Configured Competitors",    "de": "Konfigurierte Wettbewerber"},
    "your_site":            {"en": "Your site",                  "de": "Ihre Website"},
    "what_comp_have":       {"en": "What competitors have that you lack", "de": "Was Wettbewerber haben, was Ihnen fehlt"},
    "per_comp":             {"en": "Per-Competitor Breakdown",   "de": "Aufschlüsselung je Wettbewerber"},
    "ai_consensus":         {"en": "AI Consensus (Claude + DeepSeek)", "de": "KI-Konsens (Claude + DeepSeek)"},
    "top_critical":         {"en": "Top Critical Issues Across All Pages", "de": "Kritische Probleme auf allen Seiten"},
    "element":              {"en": "Element",                    "de": "Element"},
    "fix_lbl":              {"en": "Fix",                        "de": "Lösung"},
    "what_to_change":       {"en": "What to change",             "de": "Was zu ändern ist"},
    "seo_check":            {"en": "SEO Check Results",          "de": "SEO-Prüfergebnisse"},
    "item":                 {"en": "Item",                       "de": "Prüfpunkt"},
    "finding":              {"en": "Finding",                    "de": "Befund"},
    "recommendations":      {"en": "Recommendations",            "de": "Empfehlungen"},
    "no_recs":              {"en": "✓ No AI recommendations — this page is well optimised.", "de": "✓ Keine KI-Empfehlungen — diese Seite ist gut optimiert."},
    "recs_pending":         {"en": "AI recommendations not yet available for this page.", "de": "KI-Empfehlungen für diese Seite noch nicht verfügbar."},
    "badge_good":           {"en": "✓ Good",                    "de": "✓ Gut"},
    "badge_warn":           {"en": "⚠ Needs Work",              "de": "⚠ Verbesserungsbedarf"},
    "badge_fail":           {"en": "✗ Issue",                   "de": "✗ Problem"},
    "badge_na":             {"en": "— N/A",                      "de": "— N/A"},
    "deepseek_lbl":         {"en": "DeepSeek",                   "de": "DeepSeek"},
    "comp_evidence":        {"en": "Competitor evidence",        "de": "Wettbewerber-Nachweis"},
    "finding_h":            {"en": "Finding",                    "de": "Befund"},
    "consensus_h":          {"en": "Consensus",                  "de": "Konsens"},
    "reviewer_note":        {"en": "Reviewer note",              "de": "Prüfer-Anmerkung"},
    "agrees":               {"en": "Agrees",                     "de": "Stimmt zu"},
    "upgraded":             {"en": "Upgraded",                   "de": "Aufgewertet"},
    "disagrees":            {"en": "Disagrees",                  "de": "Widerspricht"},
    "adds":                 {"en": "Adds",                       "de": "Ergänzt"},
    "no_review":            {"en": "No review",                  "de": "Keine Prüfung"},
    "both_agree":           {"en": "Both agree",                 "de": "Beide einig"},
    "disputed":             {"en": "Disputed",                   "de": "Umstritten"},
    "claude_only":          {"en": "Claude only",                "de": "Nur Claude"},
    "deepseek_only":        {"en": "DeepSeek only",              "de": "Nur DeepSeek"},
    # Consolidated table
    "cons_title":           {"en": "Action Plan — All Issues & Fix Packages", "de": "Aktionsplan — Alle Probleme & Lösungspakete"},
    "cons_subtitle":        {"en": "Every error and warning across all pages, mapped to a fix package and competitor context.", "de": "Alle Fehler und Warnungen auf allen Seiten, einem Lösungspaket und Wettbewerber-Kontext zugeordnet."},
    "cons_col_issue":       {"en": "Issue / Finding",            "de": "Problem / Befund"},
    "cons_col_priority":    {"en": "Priority",                   "de": "Priorität"},
    "cons_col_pages":       {"en": "Page(s)",                    "de": "Seite(n)"},
    "cons_col_comp":        {"en": "Competitor match",           "de": "Wettbewerber-Match"},
    "cons_col_fix":         {"en": "Fix Package",                "de": "Lösungspaket"},
    "cons_col_action":      {"en": "Suggested action",           "de": "Empfohlene Maßnahme"},
    "tier_legend":          {"en": "Fix Package Legend",         "de": "Lösungspaket-Legende"},
    "tier_basic_time":      {"en": "1–3 hours · text/content only · €10–50 (Fiverr basic)",
                             "de": "1–3 Stunden · nur Text/Inhalt · €10–50 (Fiverr Basis)"},
    "tier_adv_time":        {"en": "1–3 days · CMS / HTML · €50–300 (Fiverr standard)",
                             "de": "1–3 Tage · CMS/HTML · €50–300 (Fiverr Standard)"},
    "tier_all_time":        {"en": "2–4+ weeks · full SEO campaign · €300–1 000+ (premium)",
                             "de": "2–4+ Wochen · volle SEO-Kampagne · €300–1 000+ (Premium)"},
    "no_issues":            {"en": "No errors or warnings found across all pages.",
                             "de": "Keine Fehler oder Warnungen auf allen Seiten gefunden."},
    "comp_has":             {"en": "has this",                   "de": "hat dies"},
    "no_comp_data":         {"en": "—",                          "de": "—"},
    # Field table labels
    "f_meta_title":         {"en": "Page Title (shown in Google)",   "de": "Seitentitel (in Google)"},
    "f_meta_desc":          {"en": "Google Description",             "de": "Google-Beschreibung"},
    "f_h1":                 {"en": "Main Headline (H1)",             "de": "Hauptüberschrift (H1)"},
    "f_h2":                 {"en": "Section Headings (H2)",          "de": "Abschnittsüberschriften (H2)"},
    "f_word_count":         {"en": "Content Length",                 "de": "Inhaltslänge"},
    "f_images_alt":         {"en": "Image Alt Text",                 "de": "Bild-Alternativtext"},
    "f_phone":              {"en": "Phone Above Fold",               "de": "Telefon sichtbar"},
    "f_schema":             {"en": "Structured Data (Schema)",       "de": "Strukturierte Daten (Schema)"},
    "f_canonical":          {"en": "Canonical Tag",                  "de": "Canonical-Tag"},
    "f_viewport":           {"en": "Mobile Viewport",                "de": "Mobile-Ansicht"},
    "f_nap":                {"en": "Business Info (NAP)",            "de": "Geschäftsinfo (NAP)"},
    "f_internal_links":     {"en": "Internal Links",                 "de": "Interne Links"},
    "f_speed":              {"en": "Page Speed",                     "de": "Seitengeschwindigkeit"},
    "f_https":              {"en": "HTTPS Security",                 "de": "HTTPS-Sicherheit"},
    "page_score":           {"en": "Page Score",                     "de": "Seitenpunktzahl"},
    "footer_text":          {"en": "Generated",                      "de": "Erstellt"},
    "comp_no_data_hint":    {"en": "Re-open each page in the app after restarting to refresh AI analysis with competitor mapping, then export again.",
                             "de": "Öffnen Sie nach einem Neustart jede Seite in der App erneut, um die KI-Analyse mit Wettbewerber-Mapping zu aktualisieren, und exportieren Sie dann erneut."},
    "comp_no_data_strong":  {"en": "Competitor data not in this export.",
                             "de": "Wettbewerber-Daten nicht in diesem Export."},
}


def _t(key: str, lang: str) -> str:
    """Lookup a translation key; fall back to English."""
    return _T.get(key, {}).get(lang) or _T.get(key, {}).get("en") or key


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_pdf_report(
    project: ProjectConfig,
    pages: list[PageData],
    lang: str = "en",
) -> bytes:
    """Generate a complete, combined PDF report for all analysed pages.

    Args:
        project: Project configuration.
        pages: List of analysed pages.
        lang: Output language — "en" (default) or "de".
    """
    html_source = _build_html(project, pages, lang)
    return _html_to_pdf(html_source)


# ── PDF renderer ──────────────────────────────────────────────────────────────

def _html_to_pdf(html_str: str) -> bytes:
    try:
        from xhtml2pdf import pisa
        buf = io.BytesIO()
        pisa.CreatePDF(html_str, dest=buf, encoding="utf-8")
        return buf.getvalue()
    except ImportError:
        logger.warning("xhtml2pdf not available — returning HTML bytes as fallback")
        return html_str.encode("utf-8")
    except Exception as exc:
        logger.error("PDF generation failed: %s", exc)
        raise


# ── HTML builder ──────────────────────────────────────────────────────────────

def _build_html(project: ProjectConfig, pages: list[PageData], lang: str) -> str:
    now = datetime.now().strftime("%d %B %Y")
    year = datetime.now().year

    analysed = [p for p in pages if p.extraction_complete]
    site_scores = [int(p.scores.total) for p in analysed]
    avg_score = sum(site_scores) // len(site_scores) if site_scores else 0
    avg_color = _score_color(avg_score)

    total_critical = sum(
        sum(1 for c in p.ai_analysis.get("recommendation_cards", []) if c.get("priority") == "critical")
        for p in analysed
    )
    total_warnings = sum(
        sum(1 for c in p.ai_analysis.get("recommendation_cards", []) if c.get("priority") == "warning")
        for p in analysed
    )

    pages_html = "\n".join(_page_section(i, p, project, lang) for i, p in enumerate(analysed))

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>{_t('report_title', lang)} — {_esc(project.business_name)}</title>
<style>
  @page {{ size: A4; margin: 2cm 1.8cm; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 9.5pt;
    color: #1E293B;
    line-height: 1.45;
  }}

  /* ── Cover ── */
  .cover {{
    text-align: center;
    padding: 60px 20px 40px;
  }}
  .cover-brand {{
    font-size: 11pt;
    letter-spacing: 3px;
    color: #94A3B8;
    text-transform: uppercase;
    margin-bottom: 40px;
  }}
  .cover-title {{
    font-size: 22pt;
    font-weight: 700;
    color: #0F172A;
    margin-bottom: 8px;
  }}
  .cover-subtitle {{
    font-size: 12pt;
    color: #64748B;
    margin-bottom: 40px;
  }}
  .cover-score {{
    display: inline-block;
    width: 100px;
    height: 100px;
    border-radius: 50%;
    background: {avg_color};
    color: white;
    font-size: 28pt;
    font-weight: 700;
    line-height: 100px;
    text-align: center;
    margin: 0 auto 16px;
  }}
  .cover-score-label {{
    font-size: 9pt;
    color: #64748B;
    margin-bottom: 40px;
  }}
  .cover-meta table {{
    margin: 0 auto;
    border-collapse: collapse;
  }}
  .cover-meta td {{
    padding: 4px 16px;
    font-size: 9pt;
    border-bottom: 1px solid #F1F5F9;
    color: #475569;
  }}
  .cover-meta td:first-child {{
    font-weight: 600;
    color: #0F172A;
    text-align: right;
  }}

  /* ── Page break ── */
  .page-break {{ page-break-before: always; }}

  /* ── Section headings ── */
  h1 {{
    font-size: 15pt;
    color: #1E40AF;
    margin: 0 0 6px;
    padding-bottom: 4px;
    border-bottom: 2px solid #DBEAFE;
  }}
  h2 {{
    font-size: 12pt;
    color: #1E40AF;
    margin: 18px 0 6px;
    padding-bottom: 3px;
    border-bottom: 1px solid #E2E8F0;
  }}
  h3 {{
    font-size: 10pt;
    color: #334155;
    margin: 12px 0 4px;
  }}

  /* ── Summary stats strip ── */
  .stats-strip {{
    display: table;
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
  }}
  .stat-cell {{
    display: table-cell;
    width: 33%;
    padding: 10px 14px;
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    text-align: center;
    vertical-align: middle;
  }}
  .stat-number {{
    font-size: 18pt;
    font-weight: 700;
    display: block;
  }}
  .stat-label {{
    font-size: 8pt;
    color: #64748B;
    display: block;
  }}

  /* ── Tables ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 6px 0 12px;
    font-size: 8.5pt;
  }}
  th {{
    background: #F1F5F9;
    color: #334155;
    font-weight: 700;
    padding: 6px 8px;
    text-align: left;
    border: 1px solid #E2E8F0;
    font-size: 8pt;
  }}
  td {{
    padding: 5px 8px;
    border: 1px solid #F1F5F9;
    vertical-align: top;
    word-wrap: break-word;
    max-width: 200px;
  }}
  tr:nth-child(even) td {{ background: #FAFAFA; }}

  /* ── Status badges ── */
  .badge {{
    display: inline-block;
    padding: 1px 7px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 7.5pt;
    white-space: nowrap;
  }}
  .badge-pass {{ background: #D1FAE5; color: #065F46; }}
  .badge-warn {{ background: #FEF3C7; color: #92400E; }}
  .badge-fail {{ background: #FEE2E2; color: #991B1B; }}
  .badge-na   {{ background: #F3F4F6; color: #6B7280; }}
  .badge-critical  {{ background: #FEE2E2; color: #991B1B; }}
  .badge-warning   {{ background: #FEF3C7; color: #92400E; }}
  .badge-quick_win {{ background: #D1FAE5; color: #065F46; }}
  .badge-basic     {{ background: #D1FAE5; color: #065F46; }}
  .badge-advanced  {{ background: #FEF3C7; color: #92400E; }}
  .badge-all       {{ background: #FEE2E2; color: #991B1B; }}

  /* ── Recommendation cards ── */
  .rec {{
    border-left: 3px solid #CBD5E1;
    padding: 7px 10px;
    margin: 6px 0;
    background: #FAFAFA;
    page-break-inside: avoid;
  }}
  .rec-critical {{ border-left-color: #DC2626; background: #FEF2F2; }}
  .rec-warning  {{ border-left-color: #D97706; background: #FFFBEB; }}
  .rec-quick_win {{ border-left-color: #16A34A; background: #F0FDF4; }}
  .rec-label {{
    font-weight: 700;
    font-size: 9pt;
    margin-bottom: 3px;
  }}
  .rec-detail {{
    font-size: 8.5pt;
    color: #475569;
    margin: 2px 0;
  }}
  .rec-fix {{
    font-size: 8.5pt;
    color: #0F172A;
    margin-top: 4px;
    padding: 3px 6px;
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 3px;
  }}
  .comp-gap {{
    border-left: 3px solid #DC2626;
    padding: 7px 10px;
    margin: 6px 0;
    background: #FEF2F2;
    page-break-inside: avoid;
  }}
  .consensus-agree {{ background: #D1FAE5; color: #065F46; }}
  .consensus-disagree {{ background: #FEE2E2; color: #991B1B; }}
  .consensus-upgrade {{ background: #DBEAFE; color: #1E40AF; }}
  .consensus-claude {{ background: #F1F5F9; color: #475569; }}

  /* ── Page section header ── */
  .page-header {{
    background: #0F172A;
    color: white;
    padding: 10px 14px;
    margin-bottom: 10px;
  }}
  .page-header-url {{
    font-size: 10pt;
    font-weight: 700;
    color: #93C5FD;
    word-break: break-all;
  }}
  .page-header-score {{
    font-size: 8pt;
    color: #94A3B8;
    margin-top: 2px;
  }}

  /* ── Consolidated issues table ── */
  .tier-legend {{
    display: table;
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 16px;
  }}
  .tier-cell {{
    display: table-cell;
    width: 33%;
    padding: 8px 10px;
    border: 1px solid #E2E8F0;
    vertical-align: top;
  }}
  .tier-name {{
    font-weight: 700;
    font-size: 9pt;
    margin-bottom: 2px;
  }}
  .tier-time {{
    font-size: 7.5pt;
    color: #64748B;
  }}

  /* ── Footer ── */
  .footer {{
    text-align: center;
    font-size: 7.5pt;
    color: #94A3B8;
    margin-top: 24px;
    padding-top: 8px;
    border-top: 1px solid #F1F5F9;
  }}
</style>
</head>
<body>

<!-- ════════════════ COVER PAGE ════════════════ -->
<div class="cover">
  <div class="cover-brand">SEOOptimize</div>
  <div class="cover-title">{_t('report_title', lang)}</div>
  <div class="cover-subtitle">{_esc(project.business_name)}</div>
  <div class="cover-score" style="background:{avg_color};">{avg_score}</div>
  <div class="cover-score-label">{_t('overall_score', lang)}</div>
  <div class="cover-meta">
    <table>
      <tr><td>{_t('business', lang)}</td><td>{_esc(project.business_name)}</td></tr>
      <tr><td>{_t('service_area', lang)}</td><td>{_esc(project.target_city)}</td></tr>
      <tr><td>{_t('website', lang)}</td><td>{_esc(project.website_url)}</td></tr>
      <tr><td>{_t('report_date', lang)}</td><td>{now}</td></tr>
      <tr><td>{_t('pages_audited', lang)}</td><td>{len(analysed)}</td></tr>
    </table>
  </div>
</div>

<!-- ════════════════ EXECUTIVE SUMMARY ════════════════ -->
<div class="page-break">
<h1>{_t('exec_summary', lang)}</h1>

<div class="stats-strip">
  <div class="stat-cell">
    <span class="stat-number" style="color:{avg_color};">{avg_score}</span>
    <span class="stat-label">{_t('overall_score', lang)}</span>
  </div>
  <div class="stat-cell">
    <span class="stat-number" style="color:#DC2626;">{total_critical}</span>
    <span class="stat-label">{_t('critical_issues', lang)}</span>
  </div>
  <div class="stat-cell">
    <span class="stat-number" style="color:#D97706;">{total_warnings}</span>
    <span class="stat-label">{_t('warnings', lang)}</span>
  </div>
</div>

<h2>{_t('score_breakdown', lang)}</h2>
{_axis_table(analysed, lang)}

<h2>{_t('pages_at_glance', lang)}</h2>
{_summary_table(analysed, lang)}

{_competitor_section(project, analysed, lang)}

{_top_issues_section(analysed, lang)}
</div>

<!-- ════════════════ PER-PAGE SECTIONS ════════════════ -->
{pages_html}

<!-- ════════════════ CONSOLIDATED ISSUES & FIX PLAN ════════════════ -->
{_consolidated_issues_section(analysed, project, lang)}

<div class="footer">
  SEOOptimize v1.0 &nbsp;|&nbsp; {_t('footer_text', lang)} {now} &nbsp;|&nbsp; © {year} {_esc(project.business_name)}
</div>

</body>
</html>"""


# ── Section builders ──────────────────────────────────────────────────────────

def _axis_table(pages: list[PageData], lang: str) -> str:
    if not pages:
        return ""

    axis_names = {
        "en": {
            "Local SEO": "Local SEO",
            "Content Quality": "Content Quality",
            "Technical SEO": "Technical SEO",
            "Conversion Signals": "Conversion Signals",
            "On-Page Metadata": "On-Page Metadata",
            "Competitor Gap": "Competitor Gap",
        },
        "de": {
            "Local SEO": "Lokales SEO",
            "Content Quality": "Inhaltsqualität",
            "Technical SEO": "Technisches SEO",
            "Conversion Signals": "Conversion-Signale",
            "On-Page Metadata": "On-Page-Metadaten",
            "Competitor Gap": "Wettbewerber-Lücke",
        },
    }
    names = axis_names.get(lang, axis_names["en"])

    avg_axes = {
        "Local SEO":         (sum(p.scores.local_seo for p in pages) / len(pages), 30),
        "Content Quality":   (sum(p.scores.content_quality for p in pages) / len(pages), 25),
        "Technical SEO":     (sum(p.scores.technical_seo for p in pages) / len(pages), 15),
        "Conversion Signals":(sum(p.scores.conversion_signals for p in pages) / len(pages), 15),
        "On-Page Metadata":  (sum(p.scores.on_page_metadata for p in pages) / len(pages), 10),
        "Competitor Gap":    (sum(p.scores.competitor_gap for p in pages) / len(pages), 5),
    }
    rows = ""
    for axis, (val, max_v) in avg_axes.items():
        pct = (val / max_v * 100) if max_v else 0
        bar_color = _score_color_pct(pct)
        bar = (
            f"<div style='background:#F1F5F9;border-radius:3px;height:8px;width:100%;'>"
            f"<div style='width:{min(100,pct):.0f}%;background:{bar_color};"
            f"height:8px;border-radius:3px;'></div></div>"
        )
        rows += (
            f"<tr><td style='width:35%;'>{names.get(axis, axis)}</td>"
            f"<td style='width:15%;text-align:center;'>{val:.0f} / {max_v}</td>"
            f"<td style='width:50%;'>{bar}</td></tr>"
        )
    return (
        f"<table><tr><th>{_t('area', lang)}</th><th>{_t('score', lang)}</th>"
        f"<th>{_t('performance', lang)}</th></tr>"
        + rows + "</table>"
    )


def _summary_table(pages: list[PageData], lang: str) -> str:
    rows = ""
    for page in pages:
        score = int(page.scores.total)
        color = _score_color(score)
        cards = page.ai_analysis.get("recommendation_cards", [])
        critical = sum(1 for c in cards if c.get("priority") == "critical")
        warnings = sum(1 for c in cards if c.get("priority") == "warning")
        short_url = _short_url(page.url)
        status = "✓ Complete" if page.ai_complete else "Extracted"
        rows += (
            f"<tr>"
            f"<td style='word-break:break-all;max-width:0;'>{_esc(short_url)}</td>"
            f"<td style='text-align:center;font-weight:700;color:{color};"
            f"white-space:nowrap;'>{score}</td>"
            f"<td style='text-align:center;color:#DC2626;font-weight:600;white-space:nowrap;'>"
            f"{'—' if not critical else critical}</td>"
            f"<td style='text-align:center;color:#D97706;font-weight:600;white-space:nowrap;'>"
            f"{'—' if not warnings else warnings}</td>"
            f"<td style='text-align:center;font-size:8pt;color:#64748B;white-space:nowrap;'>"
            f"{status}</td>"
            f"</tr>"
        )
    return (
        "<table>"
        f"<tr>"
        f"<th style='width:48%;'>{_t('page', lang)}</th>"
        f"<th style='width:12%;text-align:center;'>{_t('score', lang)}</th>"
        f"<th style='width:13%;text-align:center;'>{_t('critical', lang)}</th>"
        f"<th style='width:13%;text-align:center;'>{_t('warning_h', lang)}</th>"
        f"<th style='width:14%;text-align:center;'>{_t('status', lang)}</th>"
        "</tr>"
        + rows + "</table>"
    )


_FEATURE_LABELS = {
    "faq_section": "FAQ section",
    "whatsapp": "WhatsApp contact button",
    "reviews": "Review / rating signals",
    "schema": "Structured data (Schema.org)",
    "word_count": "Content depth",
    "meta_description": "Meta description",
    "h1": "H1 headline",
    "content_structure": "Content structure (H2 sections)",
}

_FEATURE_LABELS_DE = {
    "faq_section": "FAQ-Bereich",
    "whatsapp": "WhatsApp-Kontaktschaltfläche",
    "reviews": "Bewertungs-Signale",
    "schema": "Strukturierte Daten (Schema.org)",
    "word_count": "Inhaltstiefe",
    "meta_description": "Meta-Beschreibung",
    "h1": "H1-Überschrift",
    "content_structure": "Inhaltsstruktur (H2-Abschnitte)",
}


def _pick_competitor_data(pages: list[PageData]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Backward-compatible alias — delegates to report_data."""
    return pick_competitor_data(pages)


def _competitor_section(project: ProjectConfig, pages: list[PageData], lang: str) -> str:
    """Executive-summary competitor mapping: what rivals have that the client lacks."""
    if not project.competitor_urls:
        return ""

    feat_labels = _FEATURE_LABELS_DE if lang == "de" else _FEATURE_LABELS
    summary, raw_gaps = _pick_competitor_data(pages)
    gap_counts = summary.get("competitor_gap_counts") or {}
    examples = summary.get("examples") or {}
    current = summary.get("current_site") or {}

    parts = [
        f"<h2>{_t('comp_gap_analysis', lang)}</h2>",
        f"<p style='font-size:8.5pt;color:#475569;margin-bottom:8px;'>"
        f"{_t('compared', lang)} <strong>{_esc(project.business_name)}</strong> "
        f"{_t('against', lang)} {len(project.competitor_urls)} {_t('competitor_sites', lang)}</p>",
    ]

    parts.append(f"<h3>{_t('configured_comp', lang)}</h3><ul style='font-size:8.5pt;margin:4px 0 10px 18px;'>")
    for url in project.competitor_urls:
        parts.append(f"<li>{_esc(url)}</li>")
    parts.append("</ul>")

    if not gap_counts and not raw_gaps:
        parts.append(
            f"<p style='font-size:8.5pt;color:#92400E;background:#FFFBEB;"
            f"padding:8px 10px;border-left:3px solid #D97706;'>"
            f"<strong>{_t('comp_no_data_strong', lang)}</strong> "
            f"{_t('comp_no_data_hint', lang)}</p>"
        )
        return "\n".join(parts)

    # Your site vs competitors side-by-side
    your_label = _t('your_site', lang)
    comp_label = _t('what_comp_have', lang)
    parts.append(f"<h3>{your_label} vs. Competitors</h3>")
    parts.append(
        f"<table><tr><th style='width:50%;'>{your_label}</th>"
        f"<th style='width:50%;'>{comp_label}</th></tr>"
    )

    yes_txt = "Yes" if lang == "en" else "Ja"
    miss_txt = "Missing" if lang == "en" else "Fehlt"

    your_rows = [
        ("FAQ section" if lang == "en" else "FAQ-Bereich",
         yes_txt if current.get("has_faq") else miss_txt),
        ("Review signals" if lang == "en" else "Bewertungs-Signale",
         yes_txt if current.get("has_reviews") else miss_txt),
        ("WhatsApp button" if lang == "en" else "WhatsApp-Schaltfläche",
         yes_txt if current.get("has_whatsapp") else miss_txt),
        ("Schema markup" if lang == "en" else "Schema-Markup",
         str(current.get("schema_status", "unknown"))),
        ("H2 headings" if lang == "en" else "H2-Überschriften",
         str(current.get("h2_count", "—"))),
    ]
    your_cell = "<br>".join(
        f"{'✓' if v not in (miss_txt, 'fail', 'unknown') else '✗'} "
        f"<strong>{_esc(k)}:</strong> {_esc(v)}"
        for k, v in your_rows
    )

    gap_cell_parts = []
    comp_has = _t('comp_has', lang)
    for feature, count in sorted(gap_counts.items(), key=lambda x: -x[1]):
        label = feat_labels.get(feature, feature.replace("_", " ").title())
        ex = examples.get(feature, [])
        ex_text = f" (e.g. {_esc(str(ex[0]))})" if ex else ""
        gap_cell_parts.append(
            f"<div class='comp-gap' style='margin:4px 0;'>"
            f"<strong>{_esc(label)}</strong><br>"
            f"{count} {comp_has}{ex_text}</div>"
        )
    gap_cell = "".join(gap_cell_parts) if gap_cell_parts else "—"

    parts.append(f"<tr><td style='vertical-align:top;'>{your_cell}</td>")
    parts.append(f"<td style='vertical-align:top;'>{gap_cell}</td></tr></table>")

    if raw_gaps:
        parts.append(f"<h3>{_t('per_comp', lang)}</h3>")
        for comp in raw_gaps:
            domain = comp.get("domain") or _esc(comp.get("url", "Competitor"))
            features = comp.get("positive_features") or {}
            if not features:
                continue
            parts.append(f"<p style='font-weight:700;font-size:9pt;margin:8px 0 4px;'>{_esc(domain)}</p>")
            parts.append("<ul style='font-size:8.5pt;margin:0 0 8px 18px;'>")
            for feat, detail in features.items():
                label = feat_labels.get(feat, feat.replace("_", " ").title())
                parts.append(f"<li><strong>{_esc(label)}:</strong> {_esc(str(detail))}</li>")
            parts.append("</ul>")

    total_reviews = sum(len(p.ai_analysis.get("gemini_reviews") or []) for p in pages)
    if total_reviews:
        parts.append(f"<h3>{_t('ai_consensus', lang)}</h3>")
        parts.append(_consensus_summary_table(pages, lang))
    else:
        no_ds = (
            "DeepSeek reviewer did not run for this export — only Claude findings are included. "
            "Ensure <code>DEEPSEEK_API_KEY</code> is set and re-analyse pages for dual-AI consensus."
            if lang == "en" else
            "DeepSeek-Prüfer wurde für diesen Export nicht ausgeführt — nur Claude-Erkenntnisse sind enthalten. "
            "Stellen Sie sicher, dass <code>DEEPSEEK_API_KEY</code> gesetzt ist, und analysieren Sie Seiten erneut."
        )
        parts.append(f"<p style='font-size:8.5pt;color:#64748B;'>{no_ds}</p>")

    return "\n".join(parts)


def _consensus_summary_table(pages: list[PageData], lang: str) -> str:
    """Compact table of Claude vs DeepSeek verdicts for the PDF."""
    verdict_map = {
        "agree":     (_t("agrees", lang),    "consensus-agree"),
        "strengthen":(_t("upgraded", lang),  "consensus-upgrade"),
        "reject":    (_t("disagrees", lang), "consensus-disagree"),
        "add":       (_t("adds", lang),      "consensus-upgrade"),
    }
    agree_map = {
        "full_agreement": _t("both_agree", lang),
        "strengthened":   _t("upgraded", lang),
        "disagreement":   _t("disputed", lang),
        "claude_only":    _t("claude_only", lang),
        "gemini_only":    _t("deepseek_only", lang),
    }

    rows = ""
    for page in pages:
        ai = page.ai_analysis or {}
        reviews = {r.get("selector", ""): r for r in (ai.get("gemini_reviews") or [])}
        cards = {c.get("selector", ""): c for c in (ai.get("recommendation_cards") or [])}

        for ann in ai.get("annotations") or []:
            selector = ann.get("selector", "")
            label = _esc(_trunc(ann.get("label") or ann.get("issue", ""), 50))
            claude_p = _esc(ann.get("priority", ""))
            review = reviews.get(selector, {})
            verdict = review.get("gemini_verdict", "")
            card = cards.get(selector, {})
            agreement = card.get("agreement_level", "claude_only")

            v_label, v_class = verdict_map.get(verdict, (_t("no_review", lang), "consensus-claude"))
            agr_label = agree_map.get(agreement, agreement)
            note = _esc(_trunc(review.get("gemini_note", ""), 80))
            page_ref = _esc(_short_url(page.url))

            rows += (
                f"<tr>"
                f"<td>{label}<br><span style='color:#94A3B8;font-size:7pt;'>{page_ref}</span></td>"
                f"<td style='text-align:center;'><span class='badge badge-{claude_p}'>{claude_p}</span></td>"
                f"<td style='text-align:center;'>"
                f"<span class='badge {v_class}'>{v_label}</span></td>"
                f"<td style='text-align:center;font-size:8pt;'>{_esc(agr_label)}</td>"
                f"<td style='font-size:8pt;color:#64748B;'>{note}</td>"
                f"</tr>"
            )

    if not rows:
        return "<p style='font-size:8.5pt;color:#64748B;'>—</p>"

    return (
        "<table>"
        f"<tr><th>{_t('finding_h', lang)}</th><th>Claude</th>"
        f"<th>{_t('deepseek_lbl', lang)}</th>"
        f"<th>{_t('consensus_h', lang)}</th><th>{_t('reviewer_note', lang)}</th></tr>"
        + rows + "</table>"
    )


def _top_issues_section(pages: list[PageData], lang: str) -> str:
    all_cards: list[dict] = []
    for page in pages:
        for card in page.ai_analysis.get("recommendation_cards", []):
            if card.get("priority") == "critical":
                all_cards.append({**card, "_page_url": _short_url(page.url)})

    if not all_cards:
        return ""

    html_parts = [f"<h2>{_t('top_critical', lang)}</h2>"]
    fix_lbl = _t("fix_lbl", lang)
    elem_lbl = _t("element", lang)
    for card in all_cards[:8]:
        label = _esc(card.get("label", "Issue"))
        page_ref = _esc(card.get("_page_url", ""))
        problem = _esc(_trunc(card.get("problem", card.get("issue", "")), 200))
        fix = _esc(_trunc(card.get("suggested_fix", ""), 220))
        element = _esc(humanize_selector(card.get("selector", "")))
        html_parts.append(
            f'<div class="rec rec-critical">'
            f'<div class="rec-label">{label}'
            f' &nbsp;<span style="font-weight:400;color:#64748B;font-size:8pt;">'
            f'— {page_ref}</span></div>'
            f'<div class="rec-detail"><strong>{elem_lbl}:</strong> {element}</div>'
            f'<div class="rec-detail">{problem}</div>'
            f'<div class="rec-fix"><strong>{fix_lbl}:</strong> {fix}</div>'
            f'</div>'
        )
    return "\n".join(html_parts)


def _consolidated_issues_section(
    pages: list[PageData],
    project: ProjectConfig,
    lang: str,
) -> str:
    """Final section: every error + warning across all pages with competitor & fix tier."""
    collected = collect_consolidated_issues(pages, project, lang)

    title = _t("cons_title", lang)
    subtitle = _t("cons_subtitle", lang)
    legend_title = _t("tier_legend", lang)

    tiers_legend_html = f"<h3>{legend_title}</h3><div class='tier-legend'>"
    for tier, time_key in (("Basic", "tier_basic_time"), ("Advanced", "tier_adv_time"), ("All", "tier_all_time")):
        tf: FixTier = tier  # type: ignore[assignment]
        bg = tier_bg(tf)
        clr = tier_color(tf)
        t_name = tier_label(tf, lang)
        t_time = _t(time_key, lang)
        tiers_legend_html += (
            f"<div class='tier-cell' style='background:{bg};border-color:{clr};'>"
            f"<div class='tier-name' style='color:{clr};'>{t_name}</div>"
            f"<div class='tier-time'>{_esc(t_time)}</div>"
            f"</div>"
        )
    tiers_legend_html += "</div>"

    if not collected:
        return (
            f"<div class='page-break'>"
            f"<h1>{_esc(title)}</h1>"
            f"<p style='color:#16A34A;'>{_t('no_issues', lang)}</p>"
            f"</div>"
        )

    col_issue   = _t("cons_col_issue",    lang)
    col_prio    = _t("cons_col_priority", lang)
    col_pages   = _t("cons_col_pages",    lang)
    col_comp    = _t("cons_col_comp",     lang)
    col_fix     = _t("cons_col_fix",      lang)
    col_action  = _t("cons_col_action",   lang)

    badge_map = {
        "critical":  "🔴 Critical" if lang == "en" else "🔴 Kritisch",
        "warning":   "🟡 Warning"  if lang == "en" else "🟡 Warnung",
        "quick_win": "🟢 Quick Win" if lang == "en" else "🟢 Schneller Gewinn",
    }

    rows = ""
    for issue in collected:
        label_txt  = _esc(issue.label)
        fix_txt    = _esc(_trunc(issue.suggested_fix, 160))
        tier: FixTier = issue.tier  # type: ignore[assignment]
        pages_txt  = "<br>".join(_esc(p) for p in sorted(issue.pages))
        prio_badge = badge_map.get(issue.priority, issue.priority)

        comp_cell = (
            "<br>".join(
                f"<span style='font-size:7.5pt;'>✓ {_esc(d)}</span>"
                for d in issue.competitors[:3]
            )
            if issue.competitors else _t("no_comp_data", lang)
        )

        tier_name  = tier_label(tier, lang)
        tier_clr   = tier_color(tier)
        tier_bg_c  = tier_bg(tier)

        rows += (
            f"<tr>"
            f"<td style='width:22%;font-weight:600;'>{label_txt}</td>"
            f"<td style='width:11%;text-align:center;'>"
            f"<span class='badge badge-{issue.priority}'>{prio_badge}</span></td>"
            f"<td style='width:16%;font-size:7.5pt;'>{pages_txt}</td>"
            f"<td style='width:18%;font-size:7.5pt;'>{comp_cell}</td>"
            f"<td style='width:14%;text-align:center;'>"
            f"<span style='background:{tier_bg_c};color:{tier_clr};font-weight:700;"
            f"font-size:7.5pt;padding:2px 6px;border-radius:8px;white-space:nowrap;'>"
            f"{tier_name}</span></td>"
            f"<td style='width:19%;font-size:7.5pt;color:#475569;'>{fix_txt}</td>"
            f"</tr>"
        )

    table_html = (
        f"<table>"
        f"<tr>"
        f"<th style='width:22%;'>{col_issue}</th>"
        f"<th style='width:11%;'>{col_prio}</th>"
        f"<th style='width:16%;'>{col_pages}</th>"
        f"<th style='width:18%;'>{col_comp}</th>"
        f"<th style='width:14%;'>{col_fix}</th>"
        f"<th style='width:19%;'>{col_action}</th>"
        f"</tr>"
        + rows + "</table>"
    )

    return (
        f"<div class='page-break'>"
        f"<h1>{_esc(title)}</h1>"
        f"<p style='font-size:8.5pt;color:#475569;margin-bottom:10px;'>{_esc(subtitle)}</p>"
        f"{tiers_legend_html}"
        f"{table_html}"
        f"</div>"
    )


def _page_section(index: int, page: PageData, project: ProjectConfig, lang: str) -> str:
    score = int(page.scores.total)
    color = _score_color(score)
    short = _short_url(page.url)
    score_lbl = _t("page_score", lang)

    return (
        '<div class="page-break">'
        f'<div class="page-header">'
        f'<div class="page-header-url">{_esc(short)}</div>'
        f'<div class="page-header-score">{score_lbl}: '
        f'<span style="color:{color};font-weight:700;">{score}/100</span>'
        f' &nbsp;|&nbsp; Page {index + 1}</div>'
        f'</div>'
        + _field_table(page, lang)
        + _rec_cards(page, lang)
        + '</div>'
    )


def _field_table(page: PageData, lang: str) -> str:
    fields = [
        (_t("f_meta_title",     lang), page.extracted.meta_title),
        (_t("f_meta_desc",      lang), page.extracted.meta_description),
        (_t("f_h1",             lang), page.extracted.h1),
        (_t("f_h2",             lang), page.extracted.h2_structure),
        (_t("f_word_count",     lang), page.extracted.word_count),
        (_t("f_images_alt",     lang), page.extracted.images_with_alt),
        (_t("f_phone",          lang), page.extracted.phone_above_fold),
        (_t("f_schema",         lang), page.extracted.schema_markup),
        (_t("f_canonical",      lang), page.extracted.canonical_tag),
        (_t("f_viewport",       lang), page.extracted.mobile_viewport),
        (_t("f_nap",            lang), page.extracted.nap_on_page),
        (_t("f_internal_links", lang), page.extracted.internal_links),
        (_t("f_speed",          lang), page.extracted.page_load_time),
        (_t("f_https",          lang), page.extracted.https),
    ]

    badge_status = {
        ScoreStatus.PASS: _t("badge_good", lang),
        ScoreStatus.WARN: _t("badge_warn", lang),
        ScoreStatus.FAIL: _t("badge_fail", lang),
        ScoreStatus.NA:   _t("badge_na",   lang),
    }

    rows = ""
    for label, field in fields:
        badge_class = f"badge-{field.status.value}"
        badge_text  = badge_status.get(field.status, field.status.value)
        note = _esc(_trunc(field.note or "", 120))
        rows += (
            f"<tr>"
            f"<td style='width:38%;font-weight:500;'>{label}</td>"
            f"<td style='width:18%;text-align:center;'>"
            f"<span class='badge {badge_class}'>{badge_text}</span></td>"
            f"<td style='width:44%;color:#475569;'>{note}</td>"
            f"</tr>"
        )

    return (
        f"<h3>{_t('seo_check', lang)}</h3>"
        "<table>"
        f"<tr><th>{_t('item', lang)}</th><th>{_t('status', lang)}</th>"
        f"<th>{_t('finding', lang)}</th></tr>"
        + rows + "</table>"
    )


def _rec_cards(page: PageData, lang: str) -> str:
    cards = page.ai_analysis.get("recommendation_cards", [])
    if not cards:
        if page.ai_complete:
            return f"<p style='color:#16A34A;font-size:8.5pt;'>{_t('no_recs', lang)}</p>"
        return f"<p style='color:#94A3B8;font-size:8.5pt;'>{_t('recs_pending', lang)}</p>"

    priority_order = {"critical": 0, "warning": 1, "quick_win": 2, "ok": 3}
    sorted_cards = sorted(cards, key=lambda c: priority_order.get(c.get("priority", "ok"), 9))

    what_to_change = _t("what_to_change", lang)
    comp_evidence_lbl = _t("comp_evidence", lang)
    deepseek_lbl = _t("deepseek_lbl", lang)

    agr_labels_map = {
        "full_agreement": ("🤝 " + ("Both agree" if lang == "en" else "Beide einig"),   "consensus-agree"),
        "strengthened":   ("⬆️ " + ("DeepSeek upgraded" if lang == "en" else "DeepSeek aufgewertet"), "consensus-upgrade"),
        "disagreement":   ("⚖️ " + ("Disputed" if lang == "en" else "Umstritten"),      "consensus-disagree"),
        "gemini_only":    ("⚡ " + ("DeepSeek only" if lang == "en" else "Nur DeepSeek"), "consensus-upgrade"),
        "claude_only":    ("🔵 " + ("Claude only" if lang == "en" else "Nur Claude"),    "consensus-claude"),
    }
    badge_text_map = {
        "critical":  "🔴 " + ("Critical" if lang == "en" else "Kritisch"),
        "warning":   "🟡 " + ("Warning"  if lang == "en" else "Warnung"),
        "quick_win": "🟢 " + ("Quick Win" if lang == "en" else "Schneller Gewinn"),
    }

    html_parts = [f"<h3>{_t('recommendations', lang)}</h3>"]
    for card in sorted_cards[:12]:
        priority = card.get("priority", "warning")
        label = _esc(card.get("label", "Improvement"))
        element = _esc(humanize_selector(card.get("selector", "")))
        problem = _esc(_trunc(card.get("problem", card.get("issue", "")), 250))
        why = _esc(_trunc(card.get("why_it_matters", ""), 200))
        fix = _esc(_trunc(card.get("suggested_fix", ""), 280))
        badge_text = badge_text_map.get(priority, priority.title())

        agreement = card.get("agreement_level", "")
        agr_text, agr_class = agr_labels_map.get(agreement, ("", ""))
        agr_html = (
            f" <span class='badge {agr_class}' style='font-size:7pt;'>{agr_text}</span>"
            if agr_text else ""
        )

        comp_evidence = card.get("competitor_evidence") or {}
        comp_html = ""
        if comp_evidence:
            comp_lines = "".join(
                f"<div class='rec-detail'><strong>{_esc(k)}:</strong> {_esc(str(v))}</div>"
                for k, v in comp_evidence.items()
            )
            comp_html = (
                f"<div class='rec-detail' style='margin-top:4px;'>"
                f"<strong>{comp_evidence_lbl}:</strong></div>{comp_lines}"
            )

        gemini_note = _esc(_trunc(card.get("gemini_note", ""), 150))
        note_html = (
            f"<div class='rec-detail' style='color:#1E40AF;'>"
            f"<strong>{deepseek_lbl}:</strong> {gemini_note}</div>"
            if gemini_note else ""
        )

        # Fix tier badge inline on each card
        tier: FixTier = classify_fix(card)  # type: ignore[assignment]
        tier_html = (
            f"<span style='background:{tier_bg(tier)};color:{tier_color(tier)};"
            f"font-size:7pt;font-weight:700;padding:1px 5px;border-radius:6px;"
            f"margin-left:6px;'>{tier_label(tier, lang)}</span>"
        )

        html_parts.append(
            f'<div class="rec rec-{priority}">'
            f'<div class="rec-label">{badge_text}: {label}{agr_html}{tier_html}'
            f' <span style="font-weight:400;color:#94A3B8;font-size:8pt;">'
            f'({element})</span></div>'
            + (f'<div class="rec-detail">{problem}</div>' if problem else "")
            + (f'<div class="rec-detail" style="color:#64748B;">{why}</div>' if why else "")
            + comp_html
            + note_html
            + (f'<div class="rec-fix"><strong>{what_to_change}:</strong> {fix}</div>' if fix else "")
            + '</div>'
        )
    return "\n".join(html_parts)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _score_color(score: int) -> str:
    if score >= 70:
        return "#16A34A"
    if score >= 45:
        return "#D97706"
    return "#DC2626"


def _score_color_pct(pct: float) -> str:
    if pct >= 70:
        return "#16A34A"
    if pct >= 45:
        return "#D97706"
    return "#DC2626"


def _short_url(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").rstrip("/")


def _trunc(text: str, max_len: int) -> str:
    text = (text or "").strip()
    return text[:max_len] + "…" if len(text) > max_len else text


def _esc(text: str) -> str:
    return html.escape(str(text or ""))
