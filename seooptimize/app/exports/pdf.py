"""PDF Export Engine — M12.

Generates a professional customer-facing PDF report.
All pages are combined into one document: cover → executive summary →
site audit table → per-page sections (issues + recommendations).
"""

from __future__ import annotations

import html
import io
from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.models.page import PageData, ScoreStatus
from app.models.project import ProjectConfig
from app.utils.friendly_text import humanize_selector

logger = get_logger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_pdf_report(project: ProjectConfig, pages: list[PageData]) -> bytes:
    """Generate a complete, combined PDF report for all analysed pages."""
    html_source = _build_html(project, pages)
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

def _build_html(project: ProjectConfig, pages: list[PageData]) -> str:
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

    pages_html = "\n".join(_page_section(i, p, project) for i, p in enumerate(analysed))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SEO Audit Report — {_esc(project.business_name)}</title>
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
  <div class="cover-title">SEO Audit Report</div>
  <div class="cover-subtitle">{_esc(project.business_name)}</div>
  <div class="cover-score" style="background:{avg_color};">{avg_score}</div>
  <div class="cover-score-label">Overall Site Score / 100</div>
  <div class="cover-meta">
    <table>
      <tr><td>Business</td><td>{_esc(project.business_name)}</td></tr>
      <tr><td>Service Area</td><td>{_esc(project.target_city)}</td></tr>
      <tr><td>Website</td><td>{_esc(project.website_url)}</td></tr>
      <tr><td>Report Date</td><td>{now}</td></tr>
      <tr><td>Pages Audited</td><td>{len(analysed)}</td></tr>
    </table>
  </div>
</div>

<!-- ════════════════ EXECUTIVE SUMMARY ════════════════ -->
<div class="page-break">
<h1>Executive Summary</h1>

<div class="stats-strip">
  <div class="stat-cell">
    <span class="stat-number" style="color:{avg_color};">{avg_score}</span>
    <span class="stat-label">Overall Score / 100</span>
  </div>
  <div class="stat-cell">
    <span class="stat-number" style="color:#DC2626;">{total_critical}</span>
    <span class="stat-label">Critical Issues</span>
  </div>
  <div class="stat-cell">
    <span class="stat-number" style="color:#D97706;">{total_warnings}</span>
    <span class="stat-label">Warnings</span>
  </div>
</div>

<h2>Score Breakdown by Axis</h2>
{_axis_table(analysed)}

<h2>Pages At a Glance</h2>
{_summary_table(analysed)}

{_competitor_section(project, analysed)}

{_top_issues_section(analysed)}
</div>

<!-- ════════════════ PER-PAGE SECTIONS ════════════════ -->
{pages_html}

<div class="footer">
  SEOOptimize v1.0 &nbsp;|&nbsp; Generated {now} &nbsp;|&nbsp; © {year} {_esc(project.business_name)}
</div>

</body>
</html>"""


# ── Section builders ──────────────────────────────────────────────────────────

def _axis_table(pages: list[PageData]) -> str:
    if not pages:
        return ""
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
            f"<tr><td style='width:35%;'>{axis}</td>"
            f"<td style='width:15%;text-align:center;'>{val:.0f} / {max_v}</td>"
            f"<td style='width:50%;'>{bar}</td></tr>"
        )
    return (
        "<table><tr><th>Area</th><th>Score</th><th>Performance</th></tr>"
        + rows + "</table>"
    )


def _summary_table(pages: list[PageData]) -> str:
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
        "<tr>"
        "<th style='width:48%;'>Page</th>"
        "<th style='width:12%;text-align:center;'>Score</th>"
        "<th style='width:13%;text-align:center;'>Critical</th>"
        "<th style='width:13%;text-align:center;'>Warnings</th>"
        "<th style='width:14%;text-align:center;'>Status</th>"
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


def _pick_competitor_data(pages: list[PageData]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the richest competitor summary + raw gaps from any analysed page."""
    best_summary: dict[str, Any] = {}
    best_gaps: list[dict[str, Any]] = []
    best_count = 0

    for page in pages:
        ai = page.ai_analysis or {}
        summary = ai.get("competitor_summary") or {}
        gaps = ai.get("competitor_gaps") or []
        count = len(summary.get("competitor_gap_counts") or {})
        if count > best_count:
            best_count = count
            best_summary = summary
            best_gaps = gaps
        elif not best_gaps and gaps:
            best_gaps = gaps

    return best_summary, best_gaps


def _competitor_section(project: ProjectConfig, pages: list[PageData]) -> str:
    """Executive-summary competitor mapping: what rivals have that the client lacks."""
    if not project.competitor_urls:
        return ""

    summary, raw_gaps = _pick_competitor_data(pages)
    gap_counts = summary.get("competitor_gap_counts") or {}
    examples = summary.get("examples") or {}
    current = summary.get("current_site") or {}

    parts = [
        "<h2>Competitor Gap Analysis</h2>",
        "<p style='font-size:8.5pt;color:#475569;margin-bottom:8px;'>"
        f"Compared <strong>{_esc(project.business_name)}</strong> against "
        f"{len(project.competitor_urls)} competitor site(s) you provided.</p>",
    ]

    parts.append("<h3>Configured Competitors</h3><ul style='font-size:8.5pt;margin:4px 0 10px 18px;'>")
    for url in project.competitor_urls:
        parts.append(f"<li>{_esc(url)}</li>")
    parts.append("</ul>")

    if not gap_counts and not raw_gaps:
        parts.append(
            "<p style='font-size:8.5pt;color:#92400E;background:#FFFBEB;"
            "padding:8px 10px;border-left:3px solid #D97706;'>"
            "<strong>Competitor data not in this export.</strong> "
            "Re-open each page in the app after restarting to refresh AI analysis "
            "with competitor mapping, then export again.</p>"
        )
        return "\n".join(parts)

    # Your site vs competitors side-by-side
    parts.append("<h3>Your Site vs Competitors</h3>")
    parts.append(
        "<table><tr><th style='width:50%;'>Your site</th>"
        "<th style='width:50%;'>What competitors have that you lack</th></tr>"
    )

    your_rows = [
        ("FAQ section", "Yes" if current.get("has_faq") else "Missing"),
        ("Review signals", "Yes" if current.get("has_reviews") else "Missing"),
        ("WhatsApp button", "Yes" if current.get("has_whatsapp") else "Missing"),
        ("Schema markup", str(current.get("schema_status", "unknown"))),
        ("H2 headings", str(current.get("h2_count", "—"))),
    ]
    your_cell = "<br>".join(
        f"{'✓' if v not in ('Missing', 'fail', 'unknown') else '✗'} "
        f"<strong>{_esc(k)}:</strong> {_esc(v)}"
        for k, v in your_rows
    )

    gap_cell_parts = []
    for feature, count in sorted(gap_counts.items(), key=lambda x: -x[1]):
        label = _FEATURE_LABELS.get(feature, feature.replace("_", " ").title())
        ex = examples.get(feature, [])
        ex_text = f" (e.g. {_esc(str(ex[0]))})" if ex else ""
        gap_cell_parts.append(
            f"<div class='comp-gap' style='margin:4px 0;'>"
            f"<strong>{_esc(label)}</strong><br>"
            f"{count} competitor(s) have this{ex_text}</div>"
        )
    gap_cell = "".join(gap_cell_parts) if gap_cell_parts else "No gaps detected."

    parts.append(f"<tr><td style='vertical-align:top;'>{your_cell}</td>")
    parts.append(f"<td style='vertical-align:top;'>{gap_cell}</td></tr></table>")

    if raw_gaps:
        parts.append("<h3>Per-Competitor Breakdown</h3>")
        for comp in raw_gaps:
            domain = comp.get("domain") or _esc(comp.get("url", "Competitor"))
            features = comp.get("positive_features") or {}
            if not features:
                continue
            parts.append(f"<p style='font-weight:700;font-size:9pt;margin:8px 0 4px;'>{_esc(domain)}</p>")
            parts.append("<ul style='font-size:8.5pt;margin:0 0 8px 18px;'>")
            for feat, detail in features.items():
                label = _FEATURE_LABELS.get(feat, feat.replace("_", " ").title())
                parts.append(f"<li><strong>{_esc(label)}:</strong> {_esc(str(detail))}</li>")
            parts.append("</ul>")

    # AI consensus summary across pages
    total_reviews = sum(len(p.ai_analysis.get("gemini_reviews") or []) for p in pages)
    if total_reviews:
        parts.append("<h3>AI Consensus (Claude + DeepSeek)</h3>")
        parts.append(_consensus_summary_table(pages))
    else:
        parts.append(
            "<p style='font-size:8.5pt;color:#64748B;'>"
            "DeepSeek reviewer did not run for this export — only Claude findings are included. "
            "Ensure <code>DEEPSEEK_API_KEY</code> is set and re-analyse pages for dual-AI consensus.</p>"
        )

    return "\n".join(parts)


def _consensus_summary_table(pages: list[PageData]) -> str:
    """Compact table of Claude vs DeepSeek verdicts for the PDF."""
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

            verdict_label = {
                "agree": ("Agrees", "consensus-agree"),
                "strengthen": ("Upgraded", "consensus-upgrade"),
                "reject": ("Disagrees", "consensus-disagree"),
                "add": ("Adds", "consensus-upgrade"),
            }.get(verdict, ("No review", "consensus-claude"))

            agr_label = {
                "full_agreement": "Both agree",
                "strengthened": "Upgraded",
                "disagreement": "Disputed",
                "claude_only": "Claude only",
                "gemini_only": "DeepSeek only",
            }.get(agreement, agreement)

            note = _esc(_trunc(review.get("gemini_note", ""), 80))
            page_ref = _esc(_short_url(page.url))

            rows += (
                f"<tr>"
                f"<td>{label}<br><span style='color:#94A3B8;font-size:7pt;'>{page_ref}</span></td>"
                f"<td style='text-align:center;'><span class='badge badge-{claude_p}'>{claude_p}</span></td>"
                f"<td style='text-align:center;'>"
                f"<span class='badge {verdict_label[1]}'>{verdict_label[0]}</span></td>"
                f"<td style='text-align:center;font-size:8pt;'>{_esc(agr_label)}</td>"
                f"<td style='font-size:8pt;color:#64748B;'>{note}</td>"
                f"</tr>"
            )

    if not rows:
        return "<p style='font-size:8.5pt;color:#64748B;'>No consensus data available.</p>"

    return (
        "<table>"
        "<tr><th>Finding</th><th>Claude</th><th>DeepSeek</th>"
        "<th>Consensus</th><th>Reviewer note</th></tr>"
        + rows + "</table>"
    )


def _top_issues_section(pages: list[PageData]) -> str:
    all_cards: list[dict] = []
    for page in pages:
        for card in page.ai_analysis.get("recommendation_cards", []):
            if card.get("priority") == "critical":
                all_cards.append({**card, "_page_url": _short_url(page.url)})

    if not all_cards:
        return ""

    html_parts = ["<h2>Top Critical Issues Across All Pages</h2>"]
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
            f'<div class="rec-detail"><strong>Element:</strong> {element}</div>'
            f'<div class="rec-detail">{problem}</div>'
            f'<div class="rec-fix"><strong>Fix:</strong> {fix}</div>'
            f'</div>'
        )
    return "\n".join(html_parts)


def _page_section(index: int, page: PageData, project: ProjectConfig) -> str:
    score = int(page.scores.total)
    color = _score_color(score)
    short = _short_url(page.url)

    return (
        '<div class="page-break">'
        f'<div class="page-header">'
        f'<div class="page-header-url">{_esc(short)}</div>'
        f'<div class="page-header-score">Page Score: '
        f'<span style="color:{color};font-weight:700;">{score}/100</span>'
        f' &nbsp;|&nbsp; Page {index + 1}</div>'
        f'</div>'
        + _field_table(page)
        + _rec_cards(page)
        + '</div>'
    )


def _field_table(page: PageData) -> str:
    fields = [
        ("Page Title (shown in Google)", page.extracted.meta_title),
        ("Google Description",           page.extracted.meta_description),
        ("Main Headline (H1)",           page.extracted.h1),
        ("Section Headings (H2)",        page.extracted.h2_structure),
        ("Content Length",               page.extracted.word_count),
        ("Image Alt Text",               page.extracted.images_with_alt),
        ("Phone Above Fold",             page.extracted.phone_above_fold),
        ("Structured Data (Schema)",     page.extracted.schema_markup),
        ("Canonical Tag",                page.extracted.canonical_tag),
        ("Mobile Viewport",              page.extracted.mobile_viewport),
        ("Business Info (NAP)",          page.extracted.nap_on_page),
        ("Internal Links",               page.extracted.internal_links),
        ("Page Speed",                   page.extracted.page_load_time),
        ("HTTPS Security",               page.extracted.https),
    ]

    rows = ""
    for label, field in fields:
        badge_class = f"badge-{field.status.value}"
        badge_text = {
            ScoreStatus.PASS: "✓ Good",
            ScoreStatus.WARN: "⚠ Needs Work",
            ScoreStatus.FAIL: "✗ Issue",
            ScoreStatus.NA:   "— N/A",
        }.get(field.status, field.status.value)
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
        "<h3>SEO Check Results</h3>"
        "<table>"
        "<tr><th>Item</th><th>Status</th><th>Finding</th></tr>"
        + rows + "</table>"
    )


def _rec_cards(page: PageData) -> str:
    cards = page.ai_analysis.get("recommendation_cards", [])
    if not cards:
        if page.ai_complete:
            return "<p style='color:#16A34A;font-size:8.5pt;'>✓ No AI recommendations — this page is well optimised.</p>"
        return "<p style='color:#94A3B8;font-size:8.5pt;'>AI recommendations not yet available for this page.</p>"

    priority_order = {"critical": 0, "warning": 1, "quick_win": 2, "ok": 3}
    sorted_cards = sorted(cards, key=lambda c: priority_order.get(c.get("priority", "ok"), 9))

    html_parts = ["<h3>Recommendations</h3>"]
    for card in sorted_cards[:12]:
        priority = card.get("priority", "warning")
        label = _esc(card.get("label", "Improvement"))
        element = _esc(humanize_selector(card.get("selector", "")))
        problem = _esc(_trunc(card.get("problem", card.get("issue", "")), 250))
        why = _esc(_trunc(card.get("why_it_matters", ""), 200))
        fix = _esc(_trunc(card.get("suggested_fix", ""), 280))
        badge_text = {"critical": "🔴 Critical", "warning": "🟡 Warning", "quick_win": "🟢 Quick Win"}.get(priority, priority.title())

        agreement = card.get("agreement_level", "")
        agr_labels = {
            "full_agreement": ("🤝 Both agree", "consensus-agree"),
            "strengthened": ("⬆️ DeepSeek upgraded", "consensus-upgrade"),
            "disagreement": ("⚖️ Disputed", "consensus-disagree"),
            "gemini_only": ("⚡ DeepSeek only", "consensus-upgrade"),
            "claude_only": ("🔵 Claude only", "consensus-claude"),
        }
        agr_text, agr_class = agr_labels.get(agreement, ("", ""))
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
                f"<strong>Competitor evidence:</strong></div>{comp_lines}"
            )

        gemini_note = _esc(_trunc(card.get("gemini_note", ""), 150))
        note_html = (
            f"<div class='rec-detail' style='color:#1E40AF;'><strong>DeepSeek:</strong> {gemini_note}</div>"
            if gemini_note else ""
        )

        html_parts.append(
            f'<div class="rec rec-{priority}">'
            f'<div class="rec-label">{badge_text}: {label}{agr_html}'
            f' <span style="font-weight:400;color:#94A3B8;font-size:8pt;">'
            f'({element})</span></div>'
            + (f'<div class="rec-detail">{problem}</div>' if problem else "")
            + (f'<div class="rec-detail" style="color:#64748B;">{why}</div>' if why else "")
            + comp_html
            + note_html
            + (f'<div class="rec-fix"><strong>What to change:</strong> {fix}</div>' if fix else "")
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
