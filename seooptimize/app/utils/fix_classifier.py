"""SEO Fix Complexity Classifier.

Categorises each recommendation into one of three service tiers
based on real-world Fiverr/Upwork SEO gig structures (2026):

  BASIC   — Text edits only; no code, no CMS plugins, no developer.
            Skilled person can do it in 1–3 hours.
            Fiverr equivalent: €10–50 "basic" package (audit report + text fixes).
            Examples: rewrite meta title/description, fix H1 wording,
            add alt text via admin panel, correct spelling.

  ADVANCED — Requires HTML/CMS access or a short development session.
            Expect 1–3 days of work.
            Fiverr equivalent: €50–300 "standard" package.
            Examples: add Schema markup, create FAQ section, fix internal
            linking, implement WhatsApp button, canonical tags, NAP fix.

  ALL     — Full-stack SEO campaign; ongoing or complex multi-week effort.
            Expect 2–4+ weeks, often ongoing monthly retainer.
            Fiverr equivalent: €300–1 000+ "premium" package.
            Examples: Core Web Vitals / page speed, full content rewrites,
            Google Reviews integration, backlink strategy, Search Console
            setup, competitor gap closure across all pages.
"""

from __future__ import annotations

from typing import Literal

FixTier = Literal["Basic", "Advanced", "All"]

# ── Selector-level keyword → tier mapping ────────────────────────────────────
# Matched against card["selector"] (lowercase).  First match wins.
_SELECTOR_RULES: list[tuple[str, FixTier]] = [
    # Core Web Vitals / performance → All
    ("lcp",          "All"),
    ("cls",          "All"),
    ("fid",          "All"),
    ("inp",          "All"),
    ("speed",        "All"),
    ("performance",  "All"),
    # Backlinks / off-page → All
    ("backlink",     "All"),
    ("link_build",   "All"),
    # Schema → Advanced
    ("schema",       "Advanced"),
    ("json-ld",      "Advanced"),
    ("structured",   "Advanced"),
    # Canonical → Advanced
    ("canonical",    "Advanced"),
    # FAQ / WhatsApp → Advanced
    ("faq",          "Advanced"),
    ("whatsapp",     "Advanced"),
    ("reviews",      "Advanced"),
    # Internal linking → Advanced
    ("internal_link","Advanced"),
    ("navigation",   "Advanced"),
    # NAP → Advanced
    ("nap",          "Advanced"),
    ("address",      "Advanced"),
    # H2 structure → Advanced
    ("h2",           "Advanced"),
    ("h3",           "Advanced"),
    # Meta text → Basic
    ("meta_title",   "Basic"),
    ("title",        "Basic"),
    ("meta_desc",    "Basic"),
    ("description",  "Basic"),
    # H1 → Basic
    ("h1",           "Basic"),
    # Alt text → Basic (text entry in CMS)
    ("alt",          "Basic"),
    ("image",        "Basic"),
    # Phone visibility → Basic (usually just moving or adding a text field)
    ("phone",        "Basic"),
    # Spelling / content text → Basic
    ("spell",        "Basic"),
    ("typo",         "Basic"),
    ("grammar",      "Basic"),
    # Mobile viewport → Advanced (template/CMS change)
    ("viewport",     "Advanced"),
    ("mobile",       "Advanced"),
    # HTTPS → All (hosting/server config)
    ("https",        "All"),
    ("ssl",          "All"),
    ("redirect",     "All"),
]

# ── Label-level keyword → tier mapping ───────────────────────────────────────
# Matched against card["label"] (lowercase).  Used when selector is generic.
_LABEL_RULES: list[tuple[str, FixTier]] = [
    # All tier keywords
    ("speed",             "All"),
    ("core web vitals",   "All"),
    ("performance",       "All"),
    ("backlink",          "All"),
    ("google analytics",  "All"),
    ("search console",    "All"),
    ("content rewrite",   "All"),
    ("page rewrite",      "All"),
    ("site audit",        "All"),
    ("monthly",           "All"),
    ("competitor gap",    "All"),
    ("off-page",          "All"),
    # Advanced tier keywords
    ("schema",            "Advanced"),
    ("structured data",   "Advanced"),
    ("json-ld",           "Advanced"),
    ("canonical",         "Advanced"),
    ("faq",               "Advanced"),
    ("whatsapp",          "Advanced"),
    ("reviews",           "Advanced"),
    ("review signal",     "Advanced"),
    ("internal link",     "Advanced"),
    ("nap",               "Advanced"),
    ("address",           "Advanced"),
    ("h2",                "Advanced"),
    ("heading structure", "Advanced"),
    ("viewport",          "Advanced"),
    ("mobile",            "Advanced"),
    ("redirect",          "Advanced"),
    ("sitemap",           "Advanced"),
    ("robots",            "Advanced"),
    # Basic tier keywords
    ("meta title",        "Basic"),
    ("page title",        "Basic"),
    ("title tag",         "Basic"),
    ("meta description",  "Basic"),
    ("h1",                "Basic"),
    ("headline",          "Basic"),
    ("alt text",          "Basic"),
    ("image alt",         "Basic"),
    ("phone",             "Basic"),
    ("spelling",          "Basic"),
    ("typo",              "Basic"),
    ("word count",        "Basic"),
    ("keyword",           "Basic"),
]

# Priority → default tier when no keyword matches
_PRIORITY_DEFAULTS: dict[str, FixTier] = {
    "critical":  "Advanced",
    "warning":   "Basic",
    "quick_win": "Basic",
    "ok":        "Basic",
}

# ── Public labels ─────────────────────────────────────────────────────────────
TIER_LABELS: dict[FixTier, dict[str, str]] = {
    "Basic": {
        "en": "Basic",
        "de": "Basis",
        "en_desc": "Text-only edit (1–3 h) — €10–50 Fiverr basic tier",
        "de_desc": "Nur Text bearbeiten (1–3 Std.) — €10–50 Fiverr-Basis",
        "color": "#16A34A",
        "bg":    "#D1FAE5",
    },
    "Advanced": {
        "en": "Advanced",
        "de": "Fortgeschritten",
        "en_desc": "CMS / HTML work (1–3 days) — €50–300 standard tier",
        "de_desc": "CMS / HTML-Arbeit (1–3 Tage) — €50–300 Standard",
        "color": "#D97706",
        "bg":    "#FEF3C7",
    },
    "All": {
        "en": "Full Campaign",
        "de": "Gesamtkampagne",
        "en_desc": "Full SEO campaign (2–4+ weeks) — €300–1 000+ premium",
        "de_desc": "Komplette SEO-Kampagne (2–4+ Wochen) — €300–1 000+",
        "color": "#DC2626",
        "bg":    "#FEE2E2",
    },
}

# Deterministic extraction field → tier (no AI card needed)
_FIELD_TIERS: dict[str, FixTier] = {
    "meta_title":       "Basic",
    "meta_description": "Basic",
    "h1":               "Basic",
    "word_count":       "Basic",
    "images_with_alt":  "Basic",
    "phone_above_fold": "Basic",
    "h2_structure":     "Advanced",
    "schema_markup":    "Advanced",
    "canonical_tag":    "Advanced",
    "mobile_viewport":  "Advanced",
    "nap_on_page":      "Advanced",
    "internal_links":   "Advanced",
    "page_load_time":   "All",
    "https":            "All",
}


def classify_field(field_attr: str) -> FixTier:
    """Return fix tier for a deterministic extraction field name."""
    return _FIELD_TIERS.get(field_attr, "Advanced")


def classify_fix(card: dict) -> FixTier:
    """Return the fix tier for a recommendation card.

    Checks selector keywords first, then label keywords, then falls back to
    the card's priority level.
    """
    selector = (card.get("selector") or "").lower()
    label    = (card.get("label") or "").lower()
    priority = (card.get("priority") or "warning").lower()

    for kw, tier in _SELECTOR_RULES:
        if kw in selector:
            return tier

    for kw, tier in _LABEL_RULES:
        if kw in label:
            return tier

    return _PRIORITY_DEFAULTS.get(priority, "Advanced")


def tier_label(tier: FixTier, lang: str = "en") -> str:
    """Return the display label for a tier in the requested language."""
    info = TIER_LABELS.get(tier, TIER_LABELS["Advanced"])
    return info.get(lang, info["en"])


def tier_desc(tier: FixTier, lang: str = "en") -> str:
    """Return the short description for a tier."""
    info = TIER_LABELS.get(tier, TIER_LABELS["Advanced"])
    key = f"{lang}_desc"
    return info.get(key, info["en_desc"])


def tier_color(tier: FixTier) -> str:
    return TIER_LABELS.get(tier, TIER_LABELS["Advanced"])["color"]


def tier_bg(tier: FixTier) -> str:
    return TIER_LABELS.get(tier, TIER_LABELS["Advanced"])["bg"]
