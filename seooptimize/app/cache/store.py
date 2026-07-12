"""Structured Knowledge Cache — Module F.

Cache is keyed by SHA-256(url + rendered_html).  If the content has not
changed, the cached PageData is returned and AI re-analysis is skipped.

Storage: one JSON file per page in the cache directory.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.models.page import BoundingBox, PageData
from app.utils.hash import page_cache_key, sha256_of_string

logger = get_logger(__name__)


class CacheStore:
    """JSON-file-backed page cache keyed by (URL + content hash).

    File layout:
        cache/
            <sha256_prefix>/
                meta.json     — PageData without ai_analysis (fast lookup)
                full.json     — Complete PageData including AI results
                *.png         — Screenshots (stored by RenderingEngine)
    """

    def __init__(self, cache_dir: Path, enabled: bool = True) -> None:
        self._dir = cache_dir
        self._enabled = enabled
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, url: str, html: str) -> PageData | None:
        """Return cached PageData if the content hash matches, else None.

        Args:
            url: The page URL.
            html: Rendered HTML (used to compute cache key).

        Returns:
            Cached PageData or None if cache miss.
        """
        if not self._enabled:
            return None

        key = page_cache_key(url, html)
        cache_file = self._full_path(key)

        if not cache_file.exists():
            logger.debug("Cache miss for %s (key=%s…)", url, key[:8])
            return None

        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            page = PageData(**self._deserialise(data))
            logger.info("Cache hit for %s", url)
            return page
        except Exception as exc:
            logger.warning("Cache read failed for %s: %s", url, exc)
            return None

    def put(self, page: PageData, html: str) -> None:
        """Save a PageData record to the cache.

        Args:
            page: The fully populated PageData to store.
            html: Rendered HTML (used to compute cache key).
        """
        if not self._enabled:
            return

        key = page_cache_key(page.url, html)
        cache_file = self._full_path(key)
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = self._serialise(page)
            cache_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            logger.debug("Cached page: %s → %s", page.url, cache_file)
        except Exception as exc:
            logger.error("Cache write failed for %s: %s", page.url, exc)

    def update_ai_results(
        self, url: str, html: str, ai_analysis: dict[str, Any]
    ) -> None:
        """Update only the AI analysis section of a cached page.

        Args:
            url: The page URL.
            html: Rendered HTML (to compute key).
            ai_analysis: New AI analysis dict to merge in.
        """
        if not self._enabled:
            return

        key = page_cache_key(url, html)
        cache_file = self._full_path(key)

        if not cache_file.exists():
            return

        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            data["ai_analysis"] = ai_analysis
            data["ai_complete"] = True
            cache_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            logger.info("Updated AI results in cache for %s", url)
        except Exception as exc:
            logger.error("Cache AI update failed for %s: %s", url, exc)

    def update_ai_for_url(self, url: str, ai_analysis: dict[str, Any]) -> None:
        """Update AI analysis on every cached page matching ``url``.

        There can be multiple cache entries for the same URL when the rendered
        HTML hash changes over time. Updating only the first match leaves stale
        Claude-only cache entries behind, which can later be loaded by the app.
        """
        if not self._enabled:
            return

        updated = 0
        for cache_file in self._dir.rglob("full.json"):
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("url") != url:
                continue
            data["ai_analysis"] = ai_analysis
            data["ai_complete"] = True
            try:
                cache_file.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
                logger.info("Updated AI results in cache for %s", url)
                updated += 1
            except Exception as exc:
                logger.error("Cache AI update failed for %s: %s", url, exc)

        if updated == 0:
            logger.warning("No cached full.json found to update AI for %s", url)
        else:
            logger.info("Updated AI results in %d cache entries for %s", updated, url)

    def section_hash(self, section_data: dict[str, Any]) -> str:
        """Return a stable hash for a logical section payload."""
        stable_json = json.dumps(section_data, ensure_ascii=False, sort_keys=True)
        return sha256_of_string(stable_json)

    def get_section(self, url: str, section_id: str) -> dict[str, Any] | None:
        """Return cached section metadata and AI output for a URL section."""
        if not self._enabled:
            return None

        section_file = self._section_path(url, section_id)
        if not section_file.exists():
            return None

        try:
            return json.loads(section_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Section cache read failed for %s [%s]: %s", url, section_id, exc)
            return None

    def put_section(
        self,
        url: str,
        section_id: str,
        content_hash: str,
        extracted_data: dict[str, Any],
        ai_response: dict[str, Any] | None = None,
        competitor_version: str | None = None,
        reviewer_version: str | None = None,
    ) -> None:
        """Store deterministic and optional AI data for a logical page section."""
        if not self._enabled:
            return

        section_file = self._section_path(url, section_id)
        section_file.parent.mkdir(parents=True, exist_ok=True)
        existing = self.get_section(url, section_id) or {}

        payload = {
            "url": url,
            "section_id": section_id,
            "content_hash": content_hash,
            "competitor_version": competitor_version or existing.get("competitor_version", ""),
            "reviewer_version": reviewer_version or existing.get("reviewer_version", ""),
            "extracted_data": extracted_data,
            "ai_response": ai_response if ai_response is not None else existing.get("ai_response", {}),
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            section_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Section cache write failed for %s [%s]: %s", url, section_id, exc)

    def update_section_ai(
        self,
        url: str,
        section_id: str,
        content_hash: str,
        extracted_data: dict[str, Any],
        ai_response: dict[str, Any],
        competitor_version: str | None = None,
        reviewer_version: str | None = None,
    ) -> None:
        """Update AI output for a logical page section."""
        self.put_section(
            url=url,
            section_id=section_id,
            content_hash=content_hash,
            extracted_data=extracted_data,
            ai_response=ai_response,
            competitor_version=competitor_version,
            reviewer_version=reviewer_version,
        )

    def get_competitor_sources(
        self, competitor_urls: list[str]
    ) -> list[dict[str, Any]]:
        """Return rendered competitor extraction for the exact configured URLs."""
        if not self._enabled or not competitor_urls:
            return []

        cache_file = self._competitors_path(competitor_urls)
        if not cache_file.exists():
            return []

        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            sources = data.get("sources", [])
            return sources if isinstance(sources, list) else []
        except Exception as exc:
            logger.warning("Competitor cache read failed: %s", exc)
            return []

    def put_competitor_sources(
        self,
        competitor_urls: list[str],
        sources: list[dict[str, Any]],
    ) -> None:
        """Persist rendered competitor extraction for lazy AI and PDF export."""
        if not self._enabled or not competitor_urls:
            return

        cache_file = self._competitors_path(competitor_urls)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "competitor_urls": competitor_urls[:8],
            "sources": sources,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            cache_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            logger.info("Cached %d rendered competitor page(s)", len(sources))
        except Exception as exc:
            logger.error("Competitor cache write failed: %s", exc)

    def clear_url(self, url: str, html: str) -> None:
        """Remove a specific cached entry."""
        key = page_cache_key(url, html)
        cache_file = self._full_path(key)
        if cache_file.exists():
            cache_file.unlink()
            logger.info("Cleared cache for %s", url)

    def clear_page_sections(self, url: str) -> int:
        """Delete all section cache files for a URL so AI will re-run completely.

        Returns:
            Number of section files deleted.
        """
        url_key = sha256_of_string(url)[:16]
        section_dir = self._dir / "sections" / url_key
        deleted = 0
        if section_dir.exists():
            for f in section_dir.glob("*.json"):
                try:
                    f.unlink()
                    deleted += 1
                except Exception as exc:
                    logger.warning("Could not delete section file %s: %s", f, exc)
            logger.info("Cleared %d section cache file(s) for %s", deleted, url)
        return deleted

    def list_cached_urls(self) -> list[str]:
        """Return all URLs currently in the cache."""
        urls = []
        for cache_file in self._dir.rglob("full.json"):
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if "url" in data:
                    urls.append(data["url"])
            except Exception:
                pass
        return urls

    # ── Private helpers ───────────────────────────────────────────────────────

    def _full_path(self, key: str) -> Path:
        """Return the path to the full.json file for a given cache key."""
        prefix = key[:16]
        return self._dir / prefix / "full.json"

    def _section_path(self, url: str, section_id: str) -> Path:
        """Return the path to the section cache entry for a URL + section."""
        url_key = sha256_of_string(url)[:16]
        safe_section = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in section_id
        )
        return self._dir / "sections" / url_key / f"{safe_section}.json"

    def _competitors_path(self, competitor_urls: list[str]) -> Path:
        """Return the cache file for a competitor URL set."""
        key = sha256_of_string(
            json.dumps(sorted(competitor_urls[:8]), ensure_ascii=False)
        )[:16]
        return self._dir / "competitors" / f"{key}.json"

    def _serialise(self, page: PageData) -> dict[str, Any]:
        """Convert PageData to a JSON-serialisable dict."""
        data = page.model_dump()
        # Convert datetime to ISO string
        if isinstance(data.get("fetched_at"), datetime):
            data["fetched_at"] = data["fetched_at"].isoformat()
        return data

    def _deserialise(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert raw JSON dict back to PageData-compatible format.

        Handles BoundingBox objects stored as plain dicts.
        """
        # element_boxes are stored as {selector: {x, y, width, height}}
        if "element_boxes" in data and isinstance(data["element_boxes"], dict):
            converted: dict[str, Any] = {}
            for selector, box in data["element_boxes"].items():
                if isinstance(box, dict):
                    converted[selector] = BoundingBox(**box)
                else:
                    converted[selector] = box
            data["element_boxes"] = converted

        return data
