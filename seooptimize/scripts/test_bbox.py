import asyncio
import time

from playwright.async_api import async_playwright

from app.rendering.playwright_engine import TRACKED_SELECTORS

URL = "https://fischer-entruempelungen.de/"


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=15000)

        for sel in TRACKED_SELECTORS:
            t0 = time.monotonic()
            handle = await page.query_selector(sel)
            box = None
            if handle:
                try:
                    box = await handle.bounding_box(timeout=1000)
                except Exception:
                    pass
            dt = time.monotonic() - t0
            print(f"{dt:5.2f}s  {sel:42}  handle={bool(handle)} box={bool(box)}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
