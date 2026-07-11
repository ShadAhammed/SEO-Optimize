"""Deterministic Extraction Engine — Module D.

Extracts all 14 SEO fields from rendered HTML using BeautifulSoup.
No AI is used here. Every field receives a pass/warn/fail score per the
specification table in SEOArch.md §Module D.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.core.logging import get_logger
from app.models.page import ExtractionResult, FieldScore, ScoreStatus

logger = get_logger(__name__)

# ── Pass/warn/fail thresholds (verbatim from SEOArch.md §Module D) ──────────
_META_TITLE_PASS = (50, 60)    # chars
_META_DESC_PASS  = (150, 160)
_META_DESC_WARN  = (50, 200)   # lenient warn band
_WORD_COUNT_PASS = 600
_WORD_COUNT_WARN = 300
_H2_PASS         = 3
_H2_WARN         = 1
_INTERNAL_LINKS_PASS = 3
_INTERNAL_LINKS_WARN = 1
_PHONE_ABOVE_FOLD_Y  = 600     # approx pixel threshold (below this = above fold)


class DOMExtractor:
    """Extracts and scores all deterministic SEO fields from rendered HTML."""

    def extract(
        self,
        html: str,
        url: str,
        load_time_ms: float = 0.0,
    ) -> ExtractionResult:
        """Run all extractors and return a fully populated ExtractionResult.

        Args:
            html: Fully rendered HTML from Playwright.
            url: The page URL (used for link analysis).
            load_time_ms: Page load time from Playwright (for LCP proxy).

        Returns:
            ExtractionResult with all 14 scored fields.
        """
        soup = BeautifulSoup(html, "lxml")
        result = ExtractionResult()

        result.meta_title = self._score_meta_title(soup)
        result.meta_description = self._score_meta_description(soup)
        result.h1 = self._score_h1(soup)
        result.h2_structure = self._score_h2(soup)
        result.word_count = self._score_word_count(soup)
        result.images_with_alt = self._score_images_alt(soup)
        result.phone_above_fold = self._score_phone_above_fold(soup)
        result.schema_markup = self._score_schema(soup)
        result.canonical_tag = self._score_canonical(soup, url)
        result.mobile_viewport = self._score_mobile_viewport(soup)
        result.nap_on_page = self._score_nap(soup)
        result.internal_links = self._score_internal_links(soup, url)
        result.page_load_time = self._score_load_time(load_time_ms)
        result.https = self._score_https(url)

        # Extra data
        result.all_headings = self._extract_all_headings(soup)
        result.all_links = self._extract_all_links(soup, url)
        result.all_images = self._extract_all_images(soup)
        result.schema_objects = self._extract_schema_objects(soup)
        result.faq_items = self._extract_faq(soup)
        result.raw_text = _get_visible_text(soup)

        logger.debug(
            "Extracted %d fields for %s — pass=%d warn=%d fail=%d",
            14,
            url,
            result.pass_count(),
            result.warn_count(),
            result.fail_count(),
        )
        return result

    # ── Individual field extractors ──────────────────────────────────────────

    def _score_meta_title(self, soup: BeautifulSoup) -> FieldScore:
        tag = soup.find("title")
        if not tag or not tag.string:
            return FieldScore(status=ScoreStatus.FAIL, note="Meta title missing")

        title = tag.string.strip()
        length = len(title)

        if _META_TITLE_PASS[0] <= length <= _META_TITLE_PASS[1]:
            return FieldScore(
                status=ScoreStatus.PASS,
                value=title,
                note=f"{length} characters",
            )
        elif 30 <= length <= 80:
            return FieldScore(
                status=ScoreStatus.WARN,
                value=title,
                note=f"{length} characters (optimal: 50–60)",
            )
        else:
            return FieldScore(
                status=ScoreStatus.FAIL,
                value=title,
                note=f"{length} characters (too {'short' if length < 30 else 'long'})",
            )

    def _score_meta_description(self, soup: BeautifulSoup) -> FieldScore:
        tag = soup.find("meta", attrs={"name": "description"})
        if not tag:
            return FieldScore(status=ScoreStatus.FAIL, note="Meta description missing")

        content = tag.get("content", "").strip()
        if not content:
            return FieldScore(status=ScoreStatus.FAIL, note="Meta description is empty")

        length = len(content)
        if _META_DESC_PASS[0] <= length <= _META_DESC_PASS[1]:
            return FieldScore(status=ScoreStatus.PASS, value=content, note=f"{length} chars")
        elif _META_DESC_WARN[0] <= length <= _META_DESC_WARN[1]:
            return FieldScore(
                status=ScoreStatus.WARN,
                value=content,
                note=f"{length} chars (optimal: 150–160)",
            )
        else:
            return FieldScore(
                status=ScoreStatus.FAIL,
                value=content,
                note=f"{length} chars — {'too short' if length < 50 else 'too long'}",
            )

    def _score_h1(self, soup: BeautifulSoup) -> FieldScore:
        h1_tags = soup.find_all("h1")
        if not h1_tags:
            return FieldScore(status=ScoreStatus.FAIL, note="No H1 tag found")
        if len(h1_tags) > 1:
            texts = [h.get_text(strip=True) for h in h1_tags]
            return FieldScore(
                status=ScoreStatus.WARN,
                value=texts,
                note=f"{len(h1_tags)} H1 tags found (should be exactly 1)",
            )

        text = h1_tags[0].get_text(strip=True)
        if len(text) < 10:
            return FieldScore(
                status=ScoreStatus.WARN,
                value=text,
                note="H1 is very short — likely not keyword-optimised",
            )
        return FieldScore(status=ScoreStatus.PASS, value=text)

    def _score_h2(self, soup: BeautifulSoup) -> FieldScore:
        h2_tags = soup.find_all("h2")
        count = len(h2_tags)
        texts = [h.get_text(strip=True) for h in h2_tags[:10]]

        if count >= _H2_PASS:
            return FieldScore(status=ScoreStatus.PASS, value=texts, note=f"{count} H2 tags")
        elif count >= _H2_WARN:
            return FieldScore(status=ScoreStatus.WARN, value=texts, note=f"{count} H2 tags (need 3+)")
        else:
            return FieldScore(status=ScoreStatus.FAIL, note="No H2 tags found")

    def _score_word_count(self, soup: BeautifulSoup) -> FieldScore:
        text = _get_visible_text(soup)
        words = len(text.split())

        if words >= _WORD_COUNT_PASS:
            return FieldScore(status=ScoreStatus.PASS, value=words, note=f"{words} words")
        elif words >= _WORD_COUNT_WARN:
            return FieldScore(
                status=ScoreStatus.WARN,
                value=words,
                note=f"{words} words (service pages need 600+)",
            )
        else:
            return FieldScore(
                status=ScoreStatus.FAIL,
                value=words,
                note=f"{words} words — thin content",
            )

    def _score_images_alt(self, soup: BeautifulSoup) -> FieldScore:
        imgs = soup.find_all("img")
        if not imgs:
            return FieldScore(status=ScoreStatus.NA, note="No images found")

        missing = [
            img.get("src", "?")
            for img in imgs
            if not img.get("alt", "").strip()
        ]
        total = len(imgs)
        missing_count = len(missing)

        if missing_count == 0:
            return FieldScore(
                status=ScoreStatus.PASS,
                value=total,
                note=f"All {total} images have alt text",
            )
        elif missing_count < total:
            return FieldScore(
                status=ScoreStatus.WARN,
                value=missing[:5],
                note=f"{missing_count}/{total} images missing alt text",
            )
        else:
            return FieldScore(
                status=ScoreStatus.FAIL,
                note=f"All {total} images are missing alt text",
            )

    def _score_phone_above_fold(self, soup: BeautifulSoup) -> FieldScore:
        """Check for phone number presence; heuristically determine fold position."""
        phone_patterns = [
            r"\+49[\s\-]?\d[\s\-\d]{8,}",
            r"0\d{2,5}[\s\-\/]?\d{3,}[\s\-\d]*",
            r"tel:\+?\d",
        ]

        # Check tel: links (most reliable)
        tel_links = soup.find_all("a", href=re.compile(r"^tel:"))
        if tel_links:
            # Heuristic: if tel: link is in header/nav, it's above the fold
            for link in tel_links:
                if link.find_parent(["header", "nav"]) or _in_top_of_dom(link, soup):
                    return FieldScore(
                        status=ScoreStatus.PASS,
                        value=link.get("href", "").replace("tel:", ""),
                        note="Phone number found in header/nav (above fold)",
                    )
            return FieldScore(
                status=ScoreStatus.WARN,
                value=tel_links[0].get("href", "").replace("tel:", ""),
                note="Phone number found but may be below fold",
            )

        # Check visible text
        text = _get_visible_text(soup)
        for pattern in phone_patterns:
            match = re.search(pattern, text)
            if match:
                return FieldScore(
                    status=ScoreStatus.WARN,
                    value=match.group(),
                    note="Phone found in text — add as tel: link in header",
                )

        return FieldScore(status=ScoreStatus.FAIL, note="No phone number found on page")

    def _score_schema(self, soup: BeautifulSoup) -> FieldScore:
        schemas = self._extract_schema_objects(soup)
        if not schemas:
            return FieldScore(status=ScoreStatus.FAIL, note="No JSON-LD schema markup found")

        schema_types = [s.get("@type", "") for s in schemas]
        local_business_types = {
            "LocalBusiness", "HomeAndConstructionBusiness", "ProfessionalService",
            "Service", "CleaningService", "HomeImprovement",
        }
        has_local = any(
            any(t in str(st) for t in local_business_types)
            for st in schema_types
        )

        if has_local:
            return FieldScore(
                status=ScoreStatus.PASS,
                value=schema_types,
                note=f"Schema found: {', '.join(schema_types[:3])}",
            )
        else:
            return FieldScore(
                status=ScoreStatus.WARN,
                value=schema_types,
                note=(
                    f"Schema present ({', '.join(schema_types[:3])}) "
                    "but no LocalBusiness type found"
                ),
            )

    def _score_canonical(self, soup: BeautifulSoup, page_url: str) -> FieldScore:
        canonical = soup.find("link", attrs={"rel": "canonical"})
        if not canonical:
            return FieldScore(status=ScoreStatus.WARN, note="No canonical tag found")

        href = canonical.get("href", "").strip()
        if not href:
            return FieldScore(status=ScoreStatus.WARN, note="Canonical tag is empty")

        # Check if canonical points to the same page (self-referencing)
        page_norm = page_url.rstrip("/")
        canon_norm = href.rstrip("/")

        if canon_norm == page_norm or canon_norm in page_norm or page_norm in canon_norm:
            return FieldScore(
                status=ScoreStatus.PASS,
                value=href,
                note="Self-referencing canonical",
            )
        else:
            return FieldScore(
                status=ScoreStatus.WARN,
                value=href,
                note="Canonical points to a different URL — verify intentional",
            )

    def _score_mobile_viewport(self, soup: BeautifulSoup) -> FieldScore:
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if not viewport:
            return FieldScore(
                status=ScoreStatus.FAIL,
                note="No viewport meta tag — page is not mobile-friendly",
            )
        content = viewport.get("content", "")
        if "width=device-width" in content:
            return FieldScore(status=ScoreStatus.PASS, value=content)
        return FieldScore(
            status=ScoreStatus.WARN,
            value=content,
            note="Viewport tag present but may not be configured correctly",
        )

    def _score_nap(self, soup: BeautifulSoup) -> FieldScore:
        """Check for Name, Address, Phone presence on page."""
        text = _get_visible_text(soup)

        phone_found = bool(
            re.search(r"0\d{2,5}[\s\-\/]?\d{3,}", text)
            or soup.find("a", href=re.compile(r"^tel:"))
        )

        # Address heuristic: look for street patterns
        address_found = bool(
            re.search(
                r"(Str(?:aße|\.)|Weg|Gasse|Platz|Allee|Ring|Damm|Chaussee)\s+\d",
                text,
                re.IGNORECASE,
            )
            or re.search(r"\b\d{5}\b", text)  # German PLZ
        )

        schema_objects = self._extract_schema_objects(soup)
        name_found = bool(schema_objects) or len(text.strip()) > 50  # minimal heuristic

        found_count = sum([phone_found, address_found, name_found])

        if found_count == 3:
            return FieldScore(
                status=ScoreStatus.PASS,
                note="Name, Address, and Phone signals detected",
            )
        elif found_count >= 1:
            missing = []
            if not phone_found:
                missing.append("phone")
            if not address_found:
                missing.append("address")
            return FieldScore(
                status=ScoreStatus.WARN,
                note=f"Partial NAP — missing: {', '.join(missing)}",
            )
        else:
            return FieldScore(
                status=ScoreStatus.FAIL,
                note="No NAP signals detected on page",
            )

    def _score_internal_links(self, soup: BeautifulSoup, page_url: str) -> FieldScore:
        parsed = urlparse(page_url)
        domain = parsed.netloc

        all_links = soup.find_all("a", href=True)
        internal = [
            a for a in all_links
            if domain in a.get("href", "")
            or (
                a.get("href", "").startswith("/")
                and not a.get("href", "").startswith("//")
            )
        ]
        count = len(internal)

        if count >= _INTERNAL_LINKS_PASS:
            return FieldScore(
                status=ScoreStatus.PASS,
                value=count,
                note=f"{count} internal links",
            )
        elif count >= _INTERNAL_LINKS_WARN:
            return FieldScore(
                status=ScoreStatus.WARN,
                value=count,
                note=f"{count} internal links (need 3+)",
            )
        else:
            return FieldScore(
                status=ScoreStatus.FAIL,
                value=count,
                note="No internal links found",
            )

    def _score_load_time(self, load_time_ms: float) -> FieldScore:
        """Score load time as LCP proxy (actual LCP requires browser APIs)."""
        if load_time_ms <= 0:
            return FieldScore(status=ScoreStatus.NA, note="Load time not measured")

        seconds = load_time_ms / 1000

        if seconds <= 2.5:
            return FieldScore(
                status=ScoreStatus.PASS,
                value=round(seconds, 2),
                note=f"{seconds:.2f}s (excellent — under 2.5s threshold)",
            )
        elif seconds <= 4.0:
            return FieldScore(
                status=ScoreStatus.WARN,
                value=round(seconds, 2),
                note=f"{seconds:.2f}s (needs improvement — 2.5–4s range)",
            )
        else:
            return FieldScore(
                status=ScoreStatus.FAIL,
                value=round(seconds, 2),
                note=f"{seconds:.2f}s (critical — over 4s causes significant bounce rate)",
            )

    def _score_https(self, url: str) -> FieldScore:
        if url.startswith("https://"):
            return FieldScore(status=ScoreStatus.PASS, value=url)
        return FieldScore(
            status=ScoreStatus.FAIL,
            value=url,
            note="Page is served over HTTP — HTTPS is required for modern SEO and security",
        )

    # ── Extra data extractors (not scored) ──────────────────────────────────

    def _extract_all_headings(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        headings = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            text = tag.get_text(strip=True)
            if text:
                headings.append({"tag": tag.name, "text": text[:200]})
        return headings

    def _extract_all_links(self, soup: BeautifulSoup, page_url: str) -> list[dict[str, str]]:
        links = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            links.append({"href": href[:300], "text": text[:100]})
        return links[:100]

    def _extract_all_images(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        images = []
        for img in soup.find_all("img"):
            images.append({
                "src": img.get("src", "")[:300],
                "alt": img.get("alt", ""),
                "width": str(img.get("width", "")),
                "height": str(img.get("height", "")),
            })
        return images[:50]

    def _extract_schema_objects(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        schemas = []
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    schemas.extend(data)
                elif isinstance(data, dict):
                    schemas.append(data)
            except (json.JSONDecodeError, TypeError):
                pass
        return schemas

    def _extract_faq(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        """Extract FAQ items from structured schema or common HTML patterns."""
        faqs = []

        # From JSON-LD FAQ schema
        for schema in self._extract_schema_objects(soup):
            if schema.get("@type") == "FAQPage":
                for item in schema.get("mainEntity", []):
                    faqs.append({
                        "question": item.get("name", ""),
                        "answer": (
                            item.get("acceptedAnswer", {}).get("text", "")[:500]
                        ),
                    })

        # From common HTML patterns (dt/dd, accordion)
        if not faqs:
            for dt in soup.find_all("dt"):
                dd = dt.find_next_sibling("dd")
                q = dt.get_text(strip=True)
                a = dd.get_text(strip=True) if dd else ""
                if q and a:
                    faqs.append({"question": q[:200], "answer": a[:500]})

        return faqs[:20]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_visible_text(soup: BeautifulSoup) -> str:
    """Extract visible text only — works on a copy to avoid mutating the soup."""
    # Re-parse from string so we never modify the caller's soup object.
    soup_copy = BeautifulSoup(str(soup), "lxml")
    for tag in soup_copy(["script", "style", "meta", "link", "noscript", "head"]):
        tag.decompose()
    return soup_copy.get_text(separator=" ", strip=True)


def _in_top_of_dom(element: Tag, soup: BeautifulSoup) -> bool:
    """Rough heuristic: is this element in the first 20% of the DOM?"""
    all_elements = list(soup.descendants)
    total = len(all_elements)
    if not total:
        return False
    try:
        idx = all_elements.index(element)
        return idx / total < 0.2
    except ValueError:
        return False
