"""Plain-language helpers for customer-facing UI text."""

from __future__ import annotations

from typing import Any

_SELECTOR_LABELS: dict[str, str] = {
    "h1": "Main headline",
    "h2": "Section heading",
    "h3": "Subheading",
    "title": "Page title shown in Google",
    "meta[name='description']": "Search result description",
    "meta_title": "Page title shown in Google",
    "meta_description": "Search result description",
    "footer": "Footer area",
    "form": "Contact form",
    "nav": "Navigation menu",
    "header": "Top of the page",
    "#header": "Top of the page",
    ".header": "Top of the page",
    ".hero": "Hero banner at the top",
    "#hero": "Hero banner at the top",
    "img": "Images on the page",
    "a[href]": "Links on the page",
    "button": "Buttons on the page",
    "script[type='application/ld+json']": "Business details for Google",
    ".phone": "Phone number",
    "a[href^='tel:']": "Click-to-call phone number",
    ".whatsapp": "WhatsApp contact button",
    "a[href*='whatsapp']": "WhatsApp contact button",
    "body": "Overall page content",
}


def humanize_selector(selector: str) -> str:
    """Turn a CSS selector into a label a business owner understands."""
    cleaned = (selector or "").strip()
    if not cleaned:
        return "Page element"

    lowered = cleaned.lower()
    for key, label in _SELECTOR_LABELS.items():
        if key.lower() == lowered:
            return label

    if "phone" in lowered or "tel:" in lowered:
        return "Phone number"
    if "whatsapp" in lowered:
        return "WhatsApp contact button"
    if "meta" in lowered and "description" in lowered:
        return "Search result description"
    if lowered.startswith("h1"):
        return "Main headline"
    if lowered.startswith("h2"):
        return "Section heading"
    if "footer" in lowered:
        return "Footer area"
    if "hero" in lowered or "header" in lowered:
        return "Top banner area"
    if "form" in lowered:
        return "Contact form"
    if "schema" in lowered or "ld+json" in lowered:
        return "Business details for Google"

    return "Page section"


def _annotation_sort_key(annotation: Any) -> tuple[int, int, float]:
    priority_rank = {"critical": 0, "warning": 1, "quick_win": 2, "ok": 3}
    impact_rank = {"high": 0, "medium": 1, "low": 2}

    priority = getattr(annotation, "priority", "")
    impact = getattr(annotation, "impact", "")
    priority_value = getattr(priority, "value", priority)
    impact_value = getattr(impact, "value", impact)

    return (
        priority_rank.get(str(priority_value), 9),
        impact_rank.get(str(impact_value), 9),
        -float(getattr(annotation, "confidence", 0.0)),
    )


def _plain_change_text(annotation: Any) -> str:
    """Prefer customer-readable wording over technical fix instructions."""
    issue = str(getattr(annotation, "issue", "") or "").strip()
    suggested = str(getattr(annotation, "suggested_fix", "") or "").strip()
    label = str(getattr(annotation, "label", "") or "").strip()

    if issue and suggested and len(suggested) < 180:
        return f"{issue} Change it to: {suggested}"
    if issue:
        return issue
    if suggested:
        return suggested
    if label:
        return label
    return "Improve this part of the page."


def format_priority_actions(annotations: list[Any], max_items: int = 5) -> str:
    """Build bullet points naming page objects and what should change."""
    if not annotations:
        return ""

    lines: list[str] = []
    seen: set[str] = set()

    for annotation in sorted(annotations, key=_annotation_sort_key):
        element = humanize_selector(getattr(annotation, "selector", ""))
        change = _plain_change_text(annotation)
        line = f"- **{element}:** {change}"
        key = f"{element}|{change}"
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
        if len(lines) >= max_items:
            break

    return "\n".join(lines)
