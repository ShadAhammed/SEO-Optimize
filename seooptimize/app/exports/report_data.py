"""Shared report data collector for PDF export and in-app summary views.

Merges AI recommendation cards and deterministic extraction failures/warnings
into one deduplicated action-plan table with competitor matching and fix tiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from app.models.page import PageData, ScoreStatus
from app.models.project import ProjectConfig
from app.utils.fix_classifier import FixTier, classify_field, classify_fix

# Field attr → selector keyword used by fix classifier
_FIELD_SELECTORS: dict[str, str] = {
    "meta_title": "meta_title",
    "meta_description": "meta_desc",
    "h1": "h1",
    "h2_structure": "h2",
    "word_count": "word_count",
    "images_with_alt": "alt",
    "phone_above_fold": "phone",
    "schema_markup": "schema",
    "canonical_tag": "canonical",
    "mobile_viewport": "viewport",
    "nap_on_page": "nap",
    "internal_links": "internal_link",
    "page_load_time": "speed",
    "https": "https",
}

_FIELD_LABELS_EN: dict[str, str] = {
    "meta_title": "Page Title (Meta Title)",
    "meta_description": "Google Description (Meta)",
    "h1": "Main Headline (H1)",
    "h2_structure": "Section Headings (H2)",
    "word_count": "Content Length",
    "images_with_alt": "Image Alt Text",
    "phone_above_fold": "Phone Above Fold",
    "schema_markup": "Structured Data (Schema)",
    "canonical_tag": "Canonical Tag",
    "mobile_viewport": "Mobile Viewport",
    "nap_on_page": "Business Info (NAP)",
    "internal_links": "Internal Links",
    "page_load_time": "Page Speed",
    "https": "HTTPS Security",
}

_FIELD_LABELS_DE: dict[str, str] = {
    "meta_title": "Seitentitel (Meta)",
    "meta_description": "Google-Beschreibung (Meta)",
    "h1": "Hauptüberschrift (H1)",
    "h2_structure": "Abschnittsüberschriften (H2)",
    "word_count": "Inhaltslänge",
    "images_with_alt": "Bild-Alternativtext",
    "phone_above_fold": "Telefon sichtbar",
    "schema_markup": "Strukturierte Daten (Schema)",
    "canonical_tag": "Canonical-Tag",
    "mobile_viewport": "Mobile-Ansicht",
    "nap_on_page": "Geschäftsinfo (NAP)",
    "internal_links": "Interne Links",
    "page_load_time": "Seitengeschwindigkeit",
    "https": "HTTPS-Sicherheit",
}

# Field → competitor positive_features keys for matching
_FIELD_COMP_FEATURES: dict[str, list[str]] = {
    "meta_description": ["meta_description"],
    "h1": ["h1"],
    "h2_structure": ["content_structure"],
    "word_count": ["word_count"],
    "schema_markup": ["schema"],
    "phone_above_fold": ["whatsapp"],
    "nap_on_page": ["whatsapp"],
}

# Card selector/label keywords → competitor feature keys
_CARD_COMP_KEYWORDS: dict[str, list[str]] = {
    "faq": ["faq_section"],
    "whatsapp": ["whatsapp"],
    "review": ["reviews"],
    "schema": ["schema"],
    "meta": ["meta_description"],
    "description": ["meta_description"],
    "h1": ["h1"],
    "h2": ["content_structure"],
    "word": ["word_count"],
    "content": ["word_count", "content_structure"],
    "phone": ["whatsapp"],
    "nap": ["whatsapp"],
}


@dataclass
class ConsolidatedIssue:
    """One row in the site-wide action plan table."""

    label: str
    selector: str
    priority: str
    pages: list[str] = field(default_factory=list)
    suggested_fix: str = ""
    source: str = "ai"  # "ai" | "extraction"
    tier: FixTier = "Advanced"
    competitors: list[str] = field(default_factory=list)
    problem: str = ""


def short_url(url: str) -> str:
    p = urlparse(url)
    path = p.path.strip("/")
    return f"{p.netloc}/{path}" if path else p.netloc


def is_kontakt_url(url: str) -> bool:
    path = urlparse(url).path.lower().strip("/")
    return "kontakt" in path.split("/")


def pick_competitor_data(pages: list[PageData]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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


def _build_comp_feature_index(raw_gaps: list[dict[str, Any]]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for comp in raw_gaps:
        domain = comp.get("domain") or ""
        if not domain:
            continue
        for feat in (comp.get("positive_features") or {}):
            if domain not in index.setdefault(feat, []):
                index[feat].append(domain)
    return index


def _match_competitors(
    selector: str,
    label: str,
    field_attr: str | None,
    comp_index: dict[str, list[str]],
    comp_domains: list[str],
    comp_evidence: dict | None = None,
) -> list[str]:
    matched: list[str] = []
    selector_low = selector.lower()
    label_low = label.lower()

    if field_attr:
        for feat in _FIELD_COMP_FEATURES.get(field_attr, []):
            for d in comp_index.get(feat, []):
                if d not in matched:
                    matched.append(d)

    for kw, feats in _CARD_COMP_KEYWORDS.items():
        if kw in selector_low or kw in label_low:
            for feat in feats:
                for d in comp_index.get(feat, []):
                    if d not in matched:
                        matched.append(d)

    for feat, domains in comp_index.items():
        feat_kw = feat.replace("_", " ").lower()
        if feat_kw in selector_low or feat_kw in label_low:
            for d in domains:
                if d not in matched:
                    matched.append(d)
        for part in feat_kw.split():
            if len(part) > 3 and (part in selector_low or part in label_low):
                for d in domains:
                    if d not in matched:
                        matched.append(d)

    for ce_val in (comp_evidence or {}).values():
        ce_str = str(ce_val).lower()
        for d in comp_domains:
            if d and d.lower() in ce_str and d not in matched:
                matched.append(d)

    return matched[:5]


def _field_labels(lang: str) -> dict[str, str]:
    return _FIELD_LABELS_DE if lang == "de" else _FIELD_LABELS_EN


def _collect_extraction_issues(
    pages: list[PageData],
    lang: str,
    comp_index: dict[str, list[str]],
    comp_domains: list[str],
) -> list[ConsolidatedIssue]:
    """Turn deterministic FAIL/WARN fields into action-plan rows."""
    labels = _field_labels(lang)
    # key = (field_attr, priority) → merge pages
    merged: dict[tuple[str, str], ConsolidatedIssue] = {}

    for page in pages:
        if not page.extraction_complete:
            continue
        page_ref = short_url(page.url)
        for attr, selector in _FIELD_SELECTORS.items():
            field_score = getattr(page.extracted, attr, None)
            if not field_score or field_score.status not in (ScoreStatus.FAIL, ScoreStatus.WARN):
                continue

            priority = "critical" if field_score.status == ScoreStatus.FAIL else "warning"
            key = (attr, priority)
            label = labels.get(attr, attr.replace("_", " ").title())
            fix_hint = field_score.note or (
                "Review and correct this SEO element." if lang == "en"
                else "Dieses SEO-Element prüfen und korrigieren."
            )

            if key in merged:
                if page_ref not in merged[key].pages:
                    merged[key].pages.append(page_ref)
                continue

            pseudo_card = {"selector": selector, "label": label, "priority": priority}
            merged[key] = ConsolidatedIssue(
                label=label,
                selector=selector,
                priority=priority,
                pages=[page_ref],
                suggested_fix=fix_hint,
                source="extraction",
                tier=classify_field(attr),
                competitors=_match_competitors(
                    selector, label, attr, comp_index, comp_domains
                ),
                problem=fix_hint,
            )

    return list(merged.values())


def _collect_ai_issues(
    pages: list[PageData],
    comp_index: dict[str, list[str]],
    comp_domains: list[str],
) -> list[ConsolidatedIssue]:
    seen: set[tuple[str, str]] = set()
    collected: list[ConsolidatedIssue] = []

    for page in pages:
        page_ref = short_url(page.url)
        for card in page.ai_analysis.get("recommendation_cards", []):
            priority = card.get("priority", "ok")
            if priority not in ("critical", "warning", "quick_win"):
                continue
            label = card.get("label", "Issue")
            selector = card.get("selector", "")
            key = (label, selector)
            if key in seen:
                for existing in collected:
                    if existing.label == label and existing.selector == selector:
                        if page_ref not in existing.pages:
                            existing.pages.append(page_ref)
                        break
                continue
            seen.add(key)
            collected.append(
                ConsolidatedIssue(
                    label=label,
                    selector=selector,
                    priority=priority,
                    pages=[page_ref],
                    suggested_fix=card.get("suggested_fix", "") or card.get("problem", "") or card.get("issue", ""),
                    source="ai",
                    tier=classify_fix(card),
                    competitors=_match_competitors(
                        selector,
                        label,
                        None,
                        comp_index,
                        comp_domains,
                        card.get("competitor_evidence"),
                    ),
                    problem=card.get("problem", "") or card.get("issue", ""),
                )
            )

    return collected


def collect_consolidated_issues(
    pages: list[PageData],
    project: ProjectConfig,
    lang: str = "en",
) -> list[ConsolidatedIssue]:
    """Collect all errors and warnings across pages for the action-plan table."""
    _, raw_gaps = pick_competitor_data(pages)
    comp_index = _build_comp_feature_index(raw_gaps)
    comp_domains: list[str] = []
    if project.competitor_urls:
        comp_domains = [urlparse(u).netloc or u for u in project.competitor_urls]

    extraction = _collect_extraction_issues(pages, lang, comp_index, comp_domains)
    ai_issues = _collect_ai_issues(pages, comp_index, comp_domains)

    # Merge: prefer AI card when same selector+label overlap with extraction
    ai_keys = {(i.label.lower(), i.selector.lower()) for i in ai_issues}
    combined = list(ai_issues)
    for ext_issue in extraction:
        ext_key = (ext_issue.label.lower(), ext_issue.selector.lower())
        if ext_key not in ai_keys:
            combined.append(ext_issue)

    priority_order = {"critical": 0, "warning": 1, "quick_win": 2}
    tier_order = {"All": 0, "Advanced": 1, "Basic": 2}
    combined.sort(key=lambda i: (
        priority_order.get(i.priority, 9),
        tier_order.get(i.tier, 1),
        i.label.lower(),
    ))
    return combined


def tier_counts(issues: list[ConsolidatedIssue]) -> dict[str, int]:
    counts = {"Basic": 0, "Advanced": 0, "All": 0}
    for issue in issues:
        counts[issue.tier] = counts.get(issue.tier, 0) + 1
    return counts
