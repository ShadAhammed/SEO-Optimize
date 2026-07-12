"""Competitor Intelligence — Module I (full implementation).

Crawls competitor pages, extracts structured data, and compiles a
positive-gaps-only comparison dataset for the Gemini prompt.

EDITORIAL DISCIPLINE (SEOArch.md §6 — non-negotiable):
- Only report features where a competitor OUTPERFORMS the client.
- NEVER mention competitor weaknesses, broken links, slow pages, or errors.
- The business owner sees opportunity, not comfort.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.config.settings import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CompetitorIntelligence:
    """Crawls and extracts structured data from competitor home pages."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def gather(
        self,
        competitor_urls: list[str],
        client_data: dict[str, Any],
        rendered_competitors: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Crawl each competitor URL and return structured comparison data.

        Args:
            competitor_urls: Up to 5 competitor URLs.
            client_data: The client's structured page data (for comparison).
            rendered_competitors: Optional pre-rendered competitor extraction from
                the app rendering pipeline. When present, this is preferred over
                private Playwright loading so competitor pages follow the same
                render path as the audited site.

        Returns:
            List of competitor data dicts ready for the Gemini prompt.
        """
        if rendered_competitors:
            expected = set(competitor_urls[:8])
            results = [
                comp for comp in rendered_competitors
                if comp.get("url") in expected
            ]
            logger.info(
                "Competitor intelligence using %d pre-rendered competitor page(s)",
                len(results),
            )
        else:
            results = await self.render_and_extract(competitor_urls)

        # Filter: only include data points where competitor outperforms client
        positive_gaps = self._filter_positive_gaps(results, client_data)

        logger.info(
            "Competitor intelligence: %d competitors analysed, %d positive gaps found",
            len(results),
            len(positive_gaps),
        )
        return positive_gaps

    async def render_and_extract(self, competitor_urls: list[str]) -> list[dict[str, Any]]:
        """Fallback renderer for competitor pages.

        AnalysisService normally renders competitors through RenderingEngine and
        passes the extracted sources into gather(). This method remains as a
        safety net for direct use or stale sessions.
        """
        results: list[dict[str, Any]] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=self._settings.crawl_user_agent,
            )
            page = await context.new_page()

            for url in competitor_urls[:8]:
                try:
                    competitor_data = await self._extract_competitor(page, url)
                    if competitor_data:
                        results.append(competitor_data)
                    await asyncio.sleep(self._settings.crawl_delay_seconds)
                except Exception as exc:
                    logger.warning("Competitor extraction failed for %s: %s", url, exc)

            await browser.close()

        return results

    async def _extract_competitor(
        self, page: Any, url: str
    ) -> dict[str, Any] | None:
        """Fetch and extract key SEO signals from a competitor page.

        Returns:
            Structured dict or None on failure.
        """
        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self._settings.render_timeout_ms,
            )
            await page.wait_for_timeout(1000)
            html = await page.content()
        except Exception as exc:
            logger.warning("Could not load competitor %s: %s", url, exc)
            return None

        return self.extract_from_html(
            url=url,
            html=html,
            load_time_ms=0.0,
            screenshot_path="",
            mobile_screenshot_path="",
        )

    def extract_from_html(
        self,
        url: str,
        html: str,
        load_time_ms: float = 0.0,
        screenshot_path: str = "",
        mobile_screenshot_path: str = "",
    ) -> dict[str, Any]:
        """Extract competitor signals from already-rendered HTML."""
        soup = BeautifulSoup(html, "lxml")
        domain = urlparse(url).netloc

        def _text(tag: Any) -> str:
            return tag.get_text(strip=True) if tag else ""

        html_lower = html.lower()
        # FAQ detection: look for common FAQ patterns
        has_faq = (
            bool(soup.find(id=lambda i: i and "faq" in i.lower()))
            or bool(soup.find(class_=lambda c: c and "faq" in " ".join(c).lower()))
            or "faq" in html_lower
            or "häufig" in html_lower
            or "frequently asked" in html_lower
            or bool(soup.find("details"))  # HTML5 accordion pattern
        )
        h2_count = len(soup.find_all("h2"))

        return {
            "url": url,
            "domain": domain,
            "rendered": True,
            "load_time_ms": load_time_ms,
            "screenshot_path": screenshot_path,
            "mobile_screenshot_path": mobile_screenshot_path,
            "title": _text(soup.find("title")),
            "h1": _text(soup.find("h1")),
            "meta_description": (
                soup.find("meta", attrs={"name": "description"}) or {}
            ).get("content", ""),
            "h2_count": h2_count,
            "has_phone": bool(soup.find("a", href=lambda h: h and h.startswith("tel:"))),
            "has_whatsapp": "whatsapp" in html_lower or "wa.me" in html_lower,
            "has_schema": bool(
                soup.find("script", attrs={"type": "application/ld+json"})
            ),
            "has_faq": has_faq,
            "word_count": len(
                " ".join(
                    t for t in soup.stripped_strings
                    if t
                ).split()
            ),
            "has_reviews": any(
                kw in html_lower
                for kw in ["bewertung", "review", "sterne", "stars", "google"]
            ),
            "tel_links": [
                a.get("href", "").replace("tel:", "")
                for a in soup.find_all("a", href=lambda h: h and h.startswith("tel:"))
            ][:3],
            "img_count": len(soup.find_all("img", src=True)),
        }

    def _filter_positive_gaps(
        self,
        competitor_data: list[dict[str, Any]],
        client_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return only competitor data points where the competitor outperforms the client.

        This enforces the editorial discipline from SEOArch.md §6.
        """
        client_seo = client_data.get("seo_fields", {})
        client_local = client_data.get("local_seo", {})

        gaps: list[dict[str, Any]] = []

        for comp in competitor_data:
            comp_gaps: dict[str, Any] = {
                "url": comp.get("url", ""),
                "domain": comp.get("domain", ""),
                "positive_features": {},
            }

            # H1 with local keyword
            if comp.get("h1") and len(comp["h1"]) > 20:
                client_h1 = client_seo.get("h1", {}).get("value", "")
                if isinstance(client_h1, list):
                    client_h1 = client_h1[0] if client_h1 else ""
                if len(str(client_h1)) < len(comp["h1"]):
                    comp_gaps["positive_features"]["h1"] = comp["h1"]

            # WhatsApp button
            if comp.get("has_whatsapp") and not client_local.get("has_whatsapp"):
                comp_gaps["positive_features"]["whatsapp"] = "WhatsApp contact button present"

            # Review signals
            if comp.get("has_reviews") and not client_local.get("has_review_signals"):
                comp_gaps["positive_features"]["reviews"] = "Google reviews / review signals visible"

            # Schema markup
            if comp.get("has_schema") and not client_seo.get("schema_markup", {}).get("status") == "pass":
                comp_gaps["positive_features"]["schema"] = "Structured data (JSON-LD) implemented"

            # Content depth
            comp_words = comp.get("word_count", 0)
            client_words = client_seo.get("word_count", {}).get("value", 0)
            if isinstance(client_words, int) and comp_words > client_words * 1.5:
                comp_gaps["positive_features"]["word_count"] = (
                    f"{comp_words} words (significantly more than client's content)"
                )

            # Meta description
            if comp.get("meta_description") and len(comp.get("meta_description", "")) > 100:
                client_meta = client_seo.get("meta_description", {}).get("status", "fail")
                if client_meta in ("fail", "warn"):
                    comp_gaps["positive_features"]["meta_description"] = comp["meta_description"][:160]

            # FAQ section
            if comp.get("has_faq") and not bool(client_data.get("faq_items")):
                comp_gaps["positive_features"]["faq_section"] = (
                    "FAQ section present — answers common customer questions on the page"
                )

            # H2 content structure (competitor has significantly more headings = more content depth)
            client_h2 = client_seo.get("h2_count", {}).get("value", 0)
            if isinstance(client_h2, (int, float)) and comp.get("h2_count", 0) > client_h2 + 3:
                comp_gaps["positive_features"]["content_structure"] = (
                    f"{comp['h2_count']} H2 sections — richer content structure"
                )

            # Only include if there are actual positive gaps
            if comp_gaps["positive_features"]:
                gaps.append(comp_gaps)

        return gaps
