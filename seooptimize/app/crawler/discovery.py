"""Website Discovery Engine — Module B.

Crawls all internal pages up to depth 3, respecting robots.txt.
Outputs an ordered list of discovered URLs for the rendering pipeline.
"""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Callable
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import Browser, Page, async_playwright

from app.config.settings import Settings
from app.core.logging import get_logger
from app.crawler.robots import RobotsChecker
from app.utils.url import is_crawlable_page_url, is_same_origin, normalise_url, resolve_url, url_depth

logger = get_logger(__name__)


class DiscoveryEngine:
    """Crawls a website and returns an ordered list of internal page URLs.

    Crawl limits (from SEOArch.md §Module B):
    - Max pages: configurable (default 50)
    - Max depth: 3 levels from root
    - Delay: 1.5 seconds between requests
    - User-agent: SEOOptimize/1.0
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._robots = RobotsChecker(settings.crawl_user_agent)

    async def discover(
        self,
        root_url: str,
        on_progress: Callable[[str, int], None] | None = None,
    ) -> list[str]:
        """Crawl root_url and return discovered internal page URLs.

        Args:
            root_url: The starting URL to crawl.
            on_progress: Optional callback(message, pages_found) for UI updates.

        Returns:
            Ordered list of discovered URLs (root first).
        """
        root_url = normalise_url(root_url)
        discovered: list[str] = []
        visited: set[str] = set()

        # BFS queue: (url, depth)
        queue: deque[tuple[str, int]] = deque([(root_url, 0)])

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self._settings.crawl_user_agent,
                viewport={"width": self._settings.render_viewport_width, "height": 900},
            )
            page = await context.new_page()

            try:
                while queue and len(discovered) < self._settings.crawl_max_pages:
                    url, depth = queue.popleft()
                    norm_url = normalise_url(url)

                    if norm_url in visited:
                        continue
                    if depth > self._settings.crawl_max_depth:
                        continue
                    if not is_crawlable_page_url(norm_url):
                        continue
                    if not await self._robots.can_fetch(norm_url):
                        logger.info("robots.txt disallows: %s", norm_url)
                        continue

                    visited.add(norm_url)

                    try:
                        links = await self._visit_page(page, norm_url)
                        discovered.append(norm_url)
                        logger.info(
                            "Discovered [%d/%d] depth=%d: %s",
                            len(discovered),
                            self._settings.crawl_max_pages,
                            depth,
                            norm_url,
                        )

                        if on_progress:
                            on_progress(f"Discovered: {norm_url}", len(discovered))

                        # Enqueue unvisited same-origin links
                        for link in links:
                            norm_link = normalise_url(link)
                            if (
                                norm_link not in visited
                                and is_same_origin(root_url, norm_link)
                                and is_crawlable_page_url(norm_link)
                            ):
                                link_depth = url_depth(root_url, norm_link)
                                queue.append((norm_link, link_depth))

                    except Exception as exc:
                        logger.warning("Failed to visit %s: %s", norm_url, exc)

                    # Politeness delay
                    await asyncio.sleep(self._settings.crawl_delay_seconds)

            finally:
                await browser.close()

        logger.info(
            "Discovery complete: %d pages found from %s", len(discovered), root_url
        )
        return discovered

    async def discover_quick(
        self,
        root_url: str,
        on_progress: Callable[[str, int], None] | None = None,
    ) -> list[str]:
        """Fast discovery for quick audit: one homepage load + sitemap, no BFS crawl."""
        root_url = normalise_url(root_url)
        discovered: list[str] = [root_url]
        link_candidates: list[str] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self._settings.crawl_user_agent,
                viewport={"width": self._settings.render_viewport_width, "height": 900},
            )
            page = await context.new_page()

            try:
                if not await self._robots.can_fetch(root_url):
                    logger.info("robots.txt disallows: %s", root_url)
                    return []

                links = await self._visit_page(page, root_url, fetch_sitemap=False)
                link_candidates.extend(links)

                if on_progress:
                    on_progress(f"Homepage scanned: {root_url}", 1)

                sitemap_links = await self._try_sitemap(page, root_url)
                link_candidates.extend(sitemap_links)

                seen = {root_url}
                for link in link_candidates:
                    norm_link = normalise_url(link)
                    if norm_link in seen:
                        continue
                    if not is_same_origin(root_url, norm_link):
                        continue
                    if not is_crawlable_page_url(norm_link):
                        continue
                    if not await self._robots.can_fetch(norm_link):
                        continue
                    seen.add(norm_link)
                    discovered.append(norm_link)

                if on_progress:
                    on_progress(
                        f"Quick discovery found {len(discovered)} crawlable pages",
                        len(discovered),
                    )
            finally:
                await browser.close()

        logger.info(
            "Quick discovery complete: %d pages from %s", len(discovered), root_url
        )
        return discovered

    async def _visit_page(
        self, page: Page, url: str, *, fetch_sitemap: bool = True
    ) -> list[str]:
        """Navigate to URL and extract all anchor links.

        Returns:
            List of resolved absolute URLs found on the page.
        """
        if not is_crawlable_page_url(url):
            return []

        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=self._settings.render_timeout_ms,
        )

        if response and response.status >= 400:
            logger.warning("HTTP %d for %s", response.status, url)
            return []

        html = await page.content()
        soup = BeautifulSoup(html, "lxml")

        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "")
            resolved = resolve_url(url, href)
            if resolved and is_crawlable_page_url(resolved):
                links.append(resolved)

        # Sitemap is fetched once during quick discovery, not on every BFS page.
        if fetch_sitemap:
            sitemap_links = await self._try_sitemap(page, url)
            links.extend(sitemap_links)

        return links

    async def _try_sitemap(self, page: Page, base_url: str) -> list[str]:
        """Attempt to read sitemap.xml and extract URLs."""
        parsed = urlparse(base_url)
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"

        try:
            response = await page.goto(
                sitemap_url,
                wait_until="domcontentloaded",
                timeout=5000,
            )
            if not response or response.status != 200:
                return []

            content = await page.content()
            soup = BeautifulSoup(content, "lxml-xml")
            locs = soup.find_all("loc")
            urls = []
            for loc in locs:
                raw_url = loc.get_text(strip=True)
                if raw_url and is_same_origin(base_url, raw_url):
                    urls.append(raw_url)

            if urls:
                logger.info("Sitemap provided %d additional URLs", len(urls))
            return urls

        except Exception as exc:
            logger.debug("Sitemap not available at %s: %s", sitemap_url, exc)
            return []
