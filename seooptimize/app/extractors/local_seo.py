"""Local SEO Analysis — Module E.

The most important addition to the architecture (SEOArch.md §Module E).
Checks NAP consistency, LocalBusiness schema, service area signals,
review signals, and urgency/trust signals for local service businesses.
"""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from app.core.logging import get_logger
from app.models.page import LocalSEOResult

logger = get_logger(__name__)

# ── German phone number patterns ────────────────────────────────────────────
_PHONE_PATTERNS = [
    r"\+49\s?[\d\s\-\/\.]{9,}",
    r"0\d{2,5}[\s\-\/\.]?\d{3,}[\s\-\d\.]{2,}",
    r"\(0\d+\)\s?\d+[\s\-\d]*",
]

# ── German address patterns ─────────────────────────────────────────────────
_ADDRESS_PATTERNS = [
    r"[A-ZÄÖÜ][a-zäöüß]+(str(?:aße|\.)|weg|gasse|platz|allee|ring|damm|chaussee)\s*\d+",
    r"\b\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+",  # PLZ + Stadt
]

# ── Urgency / trust signals ─────────────────────────────────────────────────
_RESPONSE_TIME_PATTERNS = [
    r"24\s*stunden",
    r"sofort",
    r"gleicher\s+tag",
    r"kurzfristig",
    r"schnell(e|er)?",
    r"express",
    r"notfall",
]

_FREE_INSPECTION_PATTERNS = [
    r"kostenlos(e|er|en)?\s+(besichtigung|angebot|beratung|vor-ort)",
    r"unverbindlich(e|er|es)?",
    r"gratis",
]

_INSURANCE_PATTERNS = [
    r"versichert",
    r"zertifiziert",
    r"gepr.ft",
    r"TÜV",
    r"haftpflicht",
]


class LocalSEOAnalyser:
    """Analyses a page for local SEO signals (Module E)."""

    def analyse(
        self,
        html: str,
        url: str,
        city: str,
        business_name: str,
        service_areas: list[str] | None = None,
    ) -> LocalSEOResult:
        """Run all local SEO checks.

        Args:
            html: Rendered page HTML.
            url: Page URL.
            city: Primary service city (e.g. 'Siegen').
            business_name: Business name for NAP checks.
            service_areas: Additional service area cities.

        Returns:
            LocalSEOResult with all checks populated.
        """
        soup = BeautifulSoup(html, "lxml")
        result = LocalSEOResult()
        text = _get_text(soup)
        text_lower = text.lower()

        # ── NAP consistency ───────────────────────────────────────────────
        result.nap_phone = self._extract_phone(text)
        result.nap_address = self._extract_address(text)
        result.nap_name = self._find_business_name(soup, business_name)

        nap_issues = []
        if not result.nap_phone:
            nap_issues.append("Phone number not found on page")
        if not result.nap_address:
            nap_issues.append("Street address not found on page")
        if not result.nap_name:
            nap_issues.append("Business name not clearly identified on page")

        result.nap_issues = nap_issues
        result.nap_consistent = len(nap_issues) == 0

        # ── Schema markup ─────────────────────────────────────────────────
        schemas = self._extract_schema_objects(soup)
        local_schema = self._find_local_business_schema(schemas)
        result.has_local_business_schema = bool(local_schema)

        if local_schema:
            missing = self._check_schema_fields(local_schema)
            result.schema_missing_fields = missing
        else:
            result.schema_missing_fields = [
                "@type", "name", "address", "telephone",
                "openingHours", "geo", "url",
            ]
            result.suggested_schema = self._generate_schema(
                business_name, city, result.nap_phone, result.nap_address
            )

        # ── Service area signals ──────────────────────────────────────────
        city_lower = city.lower()
        title_tag = soup.find("title")
        title_text = (title_tag.string or "").lower() if title_tag else ""

        h1_tags = soup.find_all("h1")
        h1_text = " ".join(h.get_text(strip=True).lower() for h in h1_tags)

        result.city_in_title = city_lower in title_text
        result.city_in_h1 = city_lower in h1_text
        result.city_mention_count = text_lower.count(city_lower)

        # Identify service areas with no dedicated pages
        all_areas = [city] + (service_areas or [])
        missing_pages = []
        for area in all_areas:
            area_lower = area.lower()
            # Very rough heuristic: if city appears fewer than 3 times, no dedicated page
            if text_lower.count(area_lower) < 3:
                missing_pages.append(area)
        result.missing_service_area_pages = missing_pages

        # ── Review signals ────────────────────────────────────────────────
        review_keywords = [
            "bewertung", "rezension", "review", "sterne", "stars",
            "google bewertung", "trustpilot",
        ]
        result.has_review_signals = any(kw in text_lower for kw in review_keywords)

        review_schema = any(
            s.get("@type") in ("Review", "AggregateRating")
            for s in schemas
        )
        result.has_review_schema = review_schema

        # ── Urgency / trust signals ───────────────────────────────────────
        # Phone above fold: heuristic from tel: links in header
        tel_links = soup.find_all("a", href=re.compile(r"^tel:"))
        for link in tel_links:
            if link.find_parent(["header", "nav"]) or self._is_near_top(link, soup):
                result.phone_above_fold_mobile = True
                break

        whatsapp_patterns = ["whatsapp", "wa.me", "whatsapp.com"]
        result.has_whatsapp = any(p in text_lower for p in whatsapp_patterns) or bool(
            soup.find("a", href=re.compile(r"wa\.me|whatsapp"))
        )

        result.has_response_time_claim = self._match_any(
            text_lower, _RESPONSE_TIME_PATTERNS
        )
        result.has_free_inspection = self._match_any(
            text_lower, _FREE_INSPECTION_PATTERNS
        )
        result.has_insurance_badge = self._match_any(
            text_lower, _INSURANCE_PATTERNS
        )

        gallery_keywords = ["galerie", "gallery", "vorher", "nachher", "before", "after", "referenz"]
        result.has_photo_gallery = any(kw in text_lower for kw in gallery_keywords) and bool(
            soup.find_all("img")
        )

        # ── Urgency score (0.0–1.0) ───────────────────────────────────────
        signals = [
            result.phone_above_fold_mobile,
            result.has_whatsapp,
            result.has_response_time_claim,
            result.has_free_inspection,
            result.has_insurance_badge,
            result.has_photo_gallery,
            result.has_review_signals,
        ]
        result.urgency_score = sum(signals) / len(signals)

        logger.debug(
            "Local SEO for %s: NAP=%s schema=%s urgency=%.2f",
            url,
            result.nap_consistent,
            result.has_local_business_schema,
            result.urgency_score,
        )
        return result

    # ── Private helpers ──────────────────────────────────────────────────────

    def _extract_phone(self, text: str) -> str:
        for pattern in _PHONE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group().strip()
        return ""

    def _extract_address(self, text: str) -> str:
        for pattern in _ADDRESS_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group().strip()
        return ""

    def _find_business_name(self, soup: BeautifulSoup, business_name: str) -> str:
        text = _get_text(soup).lower()
        if business_name.lower() in text:
            return business_name
        # Check schema
        for schema in self._extract_schema_objects(soup):
            if schema.get("name"):
                return schema["name"]
        return ""

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

    def _find_local_business_schema(
        self, schemas: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        local_types = {
            "LocalBusiness", "HomeAndConstructionBusiness", "ProfessionalService",
            "Service", "CleaningService", "HomeImprovement", "MovingCompany",
        }
        for schema in schemas:
            schema_type = schema.get("@type", "")
            if isinstance(schema_type, list):
                if any(t in local_types for t in schema_type):
                    return schema
            elif schema_type in local_types:
                return schema
        return None

    def _check_schema_fields(self, schema: dict[str, Any]) -> list[str]:
        required = ["name", "address", "telephone", "openingHours", "geo", "url"]
        return [f for f in required if not schema.get(f)]

    def _generate_schema(
        self, name: str, city: str, phone: str, address: str
    ) -> dict[str, Any]:
        """Generate a ready-to-paste corrected LocalBusiness schema block."""
        return {
            "@context": "https://schema.org",
            "@type": "HomeAndConstructionBusiness",
            "name": name,
            "description": f"Professionelle Dienstleistungen in {city} und Umgebung",
            "url": "",
            "telephone": phone or "+49-XXX-XXXXXXX",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": address or "Musterstraße 1",
                "addressLocality": city,
                "addressCountry": "DE",
            },
            "geo": {
                "@type": "GeoCoordinates",
                "latitude": "",
                "longitude": "",
            },
            "openingHours": ["Mo-Fr 08:00-18:00", "Sa 08:00-14:00"],
            "areaServed": {"@type": "City", "name": city},
            "priceRange": "€€",
        }

    @staticmethod
    def _match_any(text: str, patterns: list[str]) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    @staticmethod
    def _is_near_top(element: Any, soup: BeautifulSoup) -> bool:
        """Heuristic: element is in the first 25% of DOM nodes."""
        all_els = list(soup.descendants)
        total = len(all_els)
        if not total:
            return False
        try:
            idx = all_els.index(element)
            return idx / total < 0.25
        except ValueError:
            return False


def _get_text(soup: BeautifulSoup) -> str:
    """Extract visible text without mutating the soup."""
    soup_copy = BeautifulSoup(str(soup), "lxml")
    for tag in soup_copy(["script", "style"]):
        tag.decompose()
    return soup_copy.get_text(separator=" ", strip=True)
