"""Rendering Engine — Module C.

Per-page Playwright rendering that produces:
- Viewport PNG screenshot (desktop 1280px by default)
- Mobile viewport PNG screenshot (375px)
- Final rendered DOM HTML
- Element bounding boxes for the canvas annotation bridge (Module G)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import urlparse

from playwright.async_api import Browser, Page, async_playwright

from app.config.settings import Settings
from app.core.logging import get_logger
from app.models.page import BoundingBox
from app.utils.url import is_crawlable_page_url

logger = get_logger(__name__)

WaitUntil = Literal["load", "domcontentloaded", "commit"]

# CSS selectors to capture bounding boxes for (Module G spec)
TRACKED_SELECTORS: list[str] = [
    "h1",
    "h2",
    "h3",
    "meta[name='description']",
    "img",
    "a[href]",
    ".hero, header, #hero",
    "footer",
    "form",
    "[class*=cta], [class*=button], button",
    "script[type='application/ld+json']",
    "nav",
    ".phone, a[href^='tel:'], [class*=phone]",
    "#header, .header",
    ".whatsapp, a[href*='whatsapp']",
]

@dataclass
class RenderResult:
    """Output of rendering one page."""

    url: str
    html: str = ""
    screenshot_path: str = ""
    mobile_screenshot_path: str = ""
    element_boxes: dict[str, BoundingBox] = field(default_factory=dict)
    load_time_ms: float = 0.0
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error and bool(self.html)


class RenderingEngine:
    """Playwright-based rendering engine (Module C)."""

    def __init__(self, settings: Settings, cache_dir: Path) -> None:
        self._settings = settings
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._wait_until: WaitUntil = settings.render_wait_until  # type: ignore[assignment]

    async def render_page(
        self,
        url: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> RenderResult:
        """Render a single page and return structured results."""
        result = RenderResult(url=url)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                result = await self._render_with_browser(browser, url, on_progress)
            finally:
                await browser.close()

        return result

    async def render_pages(
        self,
        urls: list[str],
        on_progress: Callable[[str, int, int], None] | None = None,
    ) -> list[RenderResult]:
        """Render multiple pages sequentially with one shared browser."""
        results: list[RenderResult] = []
        total = len(urls)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                for i, url in enumerate(urls):
                    if on_progress:
                        on_progress(f"Rendering page {i + 1}/{total}: {url}", i, total)

                    def _page_progress(msg: str) -> None:
                        if on_progress:
                            on_progress(f"Page {i + 1}/{total}: {msg}", i, total)

                    # Hard timeout so one problematic URL cannot block the pipeline.
                    per_page_timeout_s = max(
                        30.0,
                        (self._settings.render_timeout_ms / 1000.0)
                        + (self._settings.render_js_settle_ms / 1000.0)
                        + 12.0,
                    )
                    try:
                        result = await asyncio.wait_for(
                            self._render_with_browser(browser, url, on_progress=_page_progress),
                            timeout=per_page_timeout_s,
                        )
                    except asyncio.TimeoutError:
                        logger.error(
                            "Rendering hard-timeout for %s after %.1fs",
                            url,
                            per_page_timeout_s,
                        )
                        result = RenderResult(
                            url=url,
                            error=f"render timeout after {int(per_page_timeout_s)}s",
                        )
                    results.append(result)

                    # Short pause — rendering re-visits URLs already crawled.
                    if i < total - 1:
                        await asyncio.sleep(min(self._settings.crawl_delay_seconds, 0.5))
            finally:
                await browser.close()

        return results

    async def _render_with_browser(
        self,
        browser: Browser,
        url: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> RenderResult:
        result = RenderResult(url=url)

        if not is_crawlable_page_url(url):
            result.error = "Skipped non-HTML asset URL"
            return result

        desktop_ctx = None
        desktop_page = None
        try:
            desktop_ctx = await browser.new_context(
                viewport={
                    "width": self._settings.render_viewport_width,
                    "height": 900,
                },
                user_agent=self._settings.crawl_user_agent,
            )
            desktop_page = await desktop_ctx.new_page()

            start = time.monotonic()
            await desktop_page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self._settings.render_timeout_ms,
            )
            if self._settings.render_js_settle_ms:
                await desktop_page.wait_for_timeout(self._settings.render_js_settle_ms)
            result.load_time_ms = (time.monotonic() - start) * 1000

            result.html = await desktop_page.content()

            slug = _url_to_slug(url)
            shot_path = self._cache_dir / f"{slug}_desktop.png"
            await desktop_page.screenshot(
                path=str(shot_path),
                full_page=self._settings.render_full_page_screenshots,
                type="png",
            )
            result.screenshot_path = str(shot_path)

            if on_progress:
                on_progress(f"Desktop screenshot captured: {url}")

            result.element_boxes = await self._capture_bounding_boxes(desktop_page)

            # Mobile screenshot: resize viewport (no second full page load).
            mobile_shot_path = self._cache_dir / f"{slug}_mobile.png"
            await desktop_page.set_viewport_size(
                {
                    "width": self._settings.render_mobile_width,
                    "height": 812,
                }
            )
            await desktop_page.wait_for_timeout(400)
            await desktop_page.screenshot(
                path=str(mobile_shot_path),
                full_page=self._settings.render_full_page_screenshots,
                type="png",
            )
            result.mobile_screenshot_path = str(mobile_shot_path)

            logger.info(
                "Rendered %s in %.0fms (desktop + mobile)",
                url,
                result.load_time_ms,
            )

        except Exception as exc:
            logger.error("Rendering failed for %s: %s", url, exc)
            result.error = str(exc)
        finally:
            try:
                if desktop_page:
                    await desktop_page.close()
            except Exception:
                pass
            try:
                if desktop_ctx:
                    await desktop_ctx.close()
            except Exception:
                pass

        return result

    async def _capture_bounding_boxes(
        self, page: Page
    ) -> dict[str, BoundingBox]:
        """Capture pixel bounding boxes without Playwright locator waits."""
        raw: dict[str, dict[str, float]] = await page.evaluate(
            """(selectors) => {
                const out = {};
                for (const sel of selectors) {
                    try {
                        const el = document.querySelector(sel);
                        if (!el) continue;
                        const r = el.getBoundingClientRect();
                        if (r.width <= 0 || r.height <= 0) continue;
                        out[sel] = {
                            x: r.x + window.scrollX,
                            y: r.y + window.scrollY,
                            width: r.width,
                            height: r.height,
                        };
                    } catch (e) {}
                }
                return out;
            }""",
            TRACKED_SELECTORS,
        )

        element_boxes: dict[str, BoundingBox] = {}
        for selector, box in raw.items():
            element_boxes[selector] = BoundingBox(
                x=box["x"],
                y=box["y"],
                width=box["width"],
                height=box["height"],
            )

        logger.debug(
            "Captured bounding boxes for %d/%d selectors",
            len(element_boxes),
            len(TRACKED_SELECTORS),
        )
        return element_boxes


def _url_to_slug(url: str, max_length: int = 60) -> str:
    """Convert a URL to a filesystem-safe slug for screenshot filenames."""
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_") or "home"
    slug = f"{parsed.netloc}_{path}"
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
    slug = "".join(c if c in safe_chars else "_" for c in slug)
    return slug[:max_length]
