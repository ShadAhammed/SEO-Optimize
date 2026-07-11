"""robots.txt parser and polite crawl checker."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


class RobotsChecker:
    """Async-compatible robots.txt checker with in-memory caching per domain."""

    def __init__(self, user_agent: str) -> None:
        self._user_agent = user_agent
        self._parsers: dict[str, RobotFileParser] = {}

    async def can_fetch(self, url: str) -> bool:
        """Return True if the user-agent is allowed to crawl the URL.

        Fetches robots.txt on first call per domain; caches the result.
        """
        parsed = urlparse(url)
        domain_key = f"{parsed.scheme}://{parsed.netloc}"

        if domain_key not in self._parsers:
            await self._load_robots(domain_key)

        parser = self._parsers.get(domain_key)
        if parser is None:
            return True  # Assume allowed if robots.txt unavailable

        return parser.can_fetch(self._user_agent, url)

    async def _load_robots(self, base_url: str) -> None:
        robots_url = f"{base_url}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(
                    robots_url,
                    headers={"User-Agent": self._user_agent},
                )
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                    logger.info("Loaded robots.txt from %s", robots_url)
                else:
                    logger.debug(
                        "robots.txt not found at %s (status %d)",
                        robots_url,
                        response.status_code,
                    )
        except Exception as exc:
            logger.warning("Could not fetch robots.txt from %s: %s", robots_url, exc)

        self._parsers[base_url] = parser
