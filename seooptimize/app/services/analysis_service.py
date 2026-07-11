"""AnalysisService — orchestrates the full pipeline from URL to recommendations.

Pipeline order (SEOArch.md §3 Full System Workflow):

    1. Website Discovery (Module B) — crawl all pages
    2. Rendering Engine (Module C) — screenshots + bounding boxes
    3. Deterministic Extraction (Module D) — 14 scored fields
    4. Local SEO Analysis (Module E) — NAP, schema, urgency
    5. Knowledge Cache (Module F) — store/retrieve page data
    6. Competitor Intelligence (Module I, extraction part)
    7. Claude Primary Analysis (Module H)
    8. Gemini Independent Review (Module I, AI part)
    9. Consensus Engine (Module J) — merge to recommendation cards
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from app.analysis.competitor import CompetitorIntelligence
from app.analysis.consensus import ConsensusEngine
from app.ai.claude import ClaudeProvider
from app.ai.gemini import GeminiProvider
from app.ai.prompts import (
    build_claude_prompt,
    build_competitor_summary,
    build_gemini_prompt,
    build_section_payloads,
    build_structured_page_data,
)
from app.cache.store import CacheStore
from app.config.settings import Settings
from app.core.logging import get_logger
from app.crawler.discovery import DiscoveryEngine
from app.extractors.dom import DOMExtractor
from app.extractors.local_seo import LocalSEOAnalyser
from app.extractors.scorer import calculate_scores
from app.models.page import PageData
from app.models.project import ProjectConfig
from app.rendering.playwright_engine import RenderingEngine
from app.utils.friendly_text import format_priority_actions
from app.utils.url import is_crawlable_page_url

logger = get_logger(__name__)

ProgressCallback = Callable[[str, float], None]


def _settings_has_deepseek(settings: Settings) -> bool:
    import os
    from pathlib import Path

    try:
        if bool(settings.has_deepseek_key):
            return True
    except AttributeError:
        if bool(getattr(settings, "deepseek_api_key", "").strip()):
            return True

    env_val = (
        os.getenv("DEEPSEEK_API_KEY", "")
        or os.getenv("DeepSeek_API_KEY", "")
        or os.getenv("deepseek_api_key", "")
    )
    if str(env_val).strip():
        return True

    # Final fallback: read .env directly
    env_file = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, value = raw.split("=", 1)
                if key.strip() in {"DEEPSEEK_API_KEY", "DeepSeek_API_KEY", "deepseek_api_key"}:
                    if value.strip().strip("\"'"):
                        return True
        except Exception:
            pass
    return False


def _settings_has_anthropic(settings: Settings) -> bool:
    try:
        return bool(settings.has_anthropic_key)
    except AttributeError:
        return bool(getattr(settings, "anthropic_api_key", "").strip())


def _settings_has_google(settings: Settings) -> bool:
    try:
        return bool(settings.has_google_key)
    except AttributeError:
        return bool(getattr(settings, "google_api_key", "").strip())


class AnalysisService:
    """Orchestrates the full SEO analysis pipeline for a project."""

    def __init__(self, project: ProjectConfig, settings: Settings) -> None:
        self._project = project
        self._settings = settings
        self._cache = CacheStore(settings.cache_path, settings.cache_enabled)
        self._discovery = DiscoveryEngine(settings)
        self._renderer = RenderingEngine(settings, settings.cache_path)
        self._extractor = DOMExtractor()
        self._local_seo = LocalSEOAnalyser()
        self._consensus = ConsensusEngine()
        self._competitor = CompetitorIntelligence(settings)

    def _competitor_cache_file(self, competitor_urls: list[str]) -> Path:
        """Return competitor cache file path independent of CacheStore methods."""
        key = hashlib.sha256(
            json.dumps(sorted(competitor_urls[:5]), ensure_ascii=False).encode()
        ).hexdigest()[:16]
        return self._settings.cache_path / "competitors" / f"{key}.json"

    def _read_competitor_cache(self, competitor_urls: list[str]) -> list[dict[str, Any]]:
        """Read cached competitor sources even if stale CacheStore class is loaded."""
        if not self._settings.cache_enabled or not competitor_urls:
            return []
        cache_file = self._competitor_cache_file(competitor_urls)
        if not cache_file.exists():
            return []
        try:
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            sources = payload.get("sources", [])
            return sources if isinstance(sources, list) else []
        except Exception as exc:
            logger.warning("Competitor cache read failed: %s", exc)
            return []

    def _write_competitor_cache(
        self, competitor_urls: list[str], sources: list[dict[str, Any]]
    ) -> None:
        """Persist competitor sources independent of CacheStore methods."""
        if not self._settings.cache_enabled or not competitor_urls:
            return
        cache_file = self._competitor_cache_file(competitor_urls)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "competitor_urls": competitor_urls[:5],
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

    async def run(
        self,
        on_progress: ProgressCallback | None = None,
    ) -> list[PageData]:
        """Run the full pipeline and return a list of PageData.

        Args:
            on_progress: Callback(message, 0.0-1.0) for UI progress updates.

        Returns:
            Ordered list of fully analysed PageData objects.
        """
        def progress(msg: str, pct: float) -> None:
            if on_progress:
                on_progress(msg, pct)
            logger.info("[%.0f%%] %s", pct * 100, msg)

        # ── Step 1: Discovery ─────────────────────────────────────────────
        progress("Discovering pages…", 0.02)
        if self._settings.quick_audit_enabled:
            urls = await self._discovery.discover_quick(
                self._project.website_url,
                on_progress=lambda msg, n: progress(msg, 0.02 + n * 0.02),
            )
        else:
            urls = await self._discovery.discover(
                self._project.website_url,
                on_progress=lambda msg, n: progress(msg, 0.02 + n * 0.001),
            )
        if not urls:
            logger.warning("No pages discovered from %s", self._project.website_url)
            return []

        discovered_count = len(urls)
        if self._settings.quick_audit_enabled:
            urls = _prioritize_quick_audit_urls(
                urls=urls,
                root_url=self._project.website_url,
                target_city=self._project.target_city,
                service_areas=self._project.service_areas,
                max_pages=self._settings.quick_audit_max_pages,
            )
            progress(
                f"Quick audit selected {len(urls)}/{discovered_count} priority pages. Starting rendering…",
                0.10,
            )
        else:
            progress(f"Found {len(urls)} pages. Starting rendering…", 0.10)

        # ── Step 2: Render pages ─────────────────────────────────────────
        render_results = await self._renderer.render_pages(
            urls,
            on_progress=lambda msg, i, total: progress(
                msg, 0.10 + ((i + 1) / total) * 0.25
            ),
        )
        if self._project.competitor_urls:
            progress("Rendering competitor pages…", 0.33)
            await self._render_competitor_sources(
                on_progress=lambda msg, i, total: progress(
                    msg, 0.33 + ((i + 1) / max(1, total)) * 0.02
                )
            )
        else:
            progress("No competitor URLs configured; skipping competitor rendering.", 0.33)

        progress("Rendering complete. Extracting data…", 0.35)

        # ── Step 3 + 4 + 5: Extract + Local SEO + Score + Cache ──────────
        pages: list[PageData] = []
        for i, (url, render) in enumerate(zip(urls, render_results)):
            pct = 0.35 + (i / len(urls)) * 0.20

            if render.error:
                logger.warning("Skipping %s due to render error: %s", url, render.error)
                page = PageData(url=url, error=render.error)
                pages.append(page)
                continue

            # Cache check
            cached = self._cache.get(url, render.html)
            if cached and cached.extraction_complete:
                progress(f"Cache hit: {url}", pct)
                pages.append(cached)
                continue

            progress(f"Extracting: {url}", pct)

            # Deterministic extraction
            extracted = self._extractor.extract(render.html, url, render.load_time_ms)

            # Local SEO analysis
            local_seo_result = self._local_seo.analyse(
                html=render.html,
                url=url,
                city=self._project.target_city,
                business_name=self._project.business_name,
                service_areas=self._project.service_areas,
            )

            # Six-axis scoring
            scores = calculate_scores(extracted, local_seo_result)

            page = PageData(
                url=url,
                title=_extract_title(render.html),
                fetched_at=datetime.utcnow(),
                content_hash=_compute_hash(url, render.html),
                screenshot_path=render.screenshot_path,
                mobile_screenshot_path=render.mobile_screenshot_path,
                element_boxes=render.element_boxes,
                extracted=extracted,
                local_seo=local_seo_result,
                scores=scores,
                extraction_complete=True,
            )

            self._cache.put(page, render.html)
            pages.append(page)

        progress("Extraction complete. AI will run when a page is opened.", 1.0)
        return pages

    async def _render_competitor_sources(
        self,
        on_progress: Callable[[str, int, int], None] | None = None,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        """Render competitor URLs through the same RenderingEngine as client pages."""
        competitor_urls = self._project.competitor_urls[:5]
        if not competitor_urls:
            logger.info("Competitor rendering skipped: no competitor URLs configured")
            return []

        if not force:
            cached = self._read_competitor_cache(competitor_urls)
            if len(cached) == len(competitor_urls):
                if on_progress:
                    on_progress(
                        f"Competitor render cache hit: {len(cached)}/{len(competitor_urls)} page(s)",
                        0,
                        len(competitor_urls),
                    )
                logger.info("Competitor render cache hit: %d page(s)", len(cached))
                return cached
            if cached:
                logger.info(
                    "Competitor render cache incomplete: %d/%d page(s); rendering again",
                    len(cached),
                    len(competitor_urls),
                )

        logger.info(
            "Rendering competitor pages through app renderer: %s",
            ", ".join(competitor_urls),
        )

        render_results = await self._renderer.render_pages(
            competitor_urls,
            on_progress=on_progress,
        )

        sources: list[dict[str, Any]] = []
        for render in render_results:
            if render.error:
                logger.warning(
                    "Skipping competitor render result for %s: %s",
                    render.url,
                    render.error,
                )
                continue

            source = self._competitor.extract_from_html(
                url=render.url,
                html=render.html,
                load_time_ms=render.load_time_ms,
                screenshot_path=render.screenshot_path,
                mobile_screenshot_path=render.mobile_screenshot_path,
            )
            sources.append(source)

        self._write_competitor_cache(competitor_urls, sources)
        logger.info(
            "Competitor rendering complete: %d/%d page(s)",
            len(sources),
            len(competitor_urls),
        )
        return sources

    async def run_ai_for_page(
        self,
        page: PageData,
        on_progress: ProgressCallback | None = None,
        force: bool = False,
    ) -> None:
        """Run lazy section-level AI for one page, reusing unchanged section cache."""
        def progress(msg: str, pct: float) -> None:
            if on_progress:
                on_progress(msg, pct)
            logger.info("[%.0f%%] %s", pct * 100, msg)

        logger.info(
            "Lazy AI requested: url=%s ai_complete=%s force=%s anthropic=%s deepseek=%s competitors=%d",
            page.url,
            page.ai_complete,
            force,
            _settings_has_anthropic(self._settings),
            _settings_has_deepseek(self._settings),
            len(self._project.competitor_urls or []),
        )

        if page.ai_complete and not force:
            logger.info("Lazy AI skipped because page is already marked complete: %s", page.url)
            return

        if not _settings_has_anthropic(self._settings):
            logger.warning("ANTHROPIC_API_KEY not set — skipping AI analysis")
            progress("AI analysis skipped (no API key)", 1.0)
            return

        claude = ClaudeProvider(
            self._settings.anthropic_api_key,
            self._settings.claude_model,
            self._settings.ai_max_retries,
        )

        # Reviewer AI: prefer DeepSeek, fall back to Gemini if only Google key present
        gemini: DeepSeekProvider | GeminiProvider | None = None
        reviewer_name = "none"
        if _settings_has_deepseek(self._settings):
            try:
                from app.ai.deepseek import DeepSeekProvider
            except ImportError as exc:
                logger.error(
                    "DeepSeek requires the openai package. Run: pip install openai — %s",
                    exc,
                )
                DeepSeekProvider = None  # type: ignore[misc, assignment]
            if DeepSeekProvider is not None:
                gemini = DeepSeekProvider(
                    self._settings.deepseek_api_key,
                    self._settings.deepseek_model,
                    self._settings.ai_max_retries,
                )
                reviewer_name = "DeepSeek"
                logger.info("Reviewer AI: DeepSeek (%s)", self._settings.deepseek_model)
        elif _settings_has_google(self._settings):
            gemini = GeminiProvider(
                self._settings.google_api_key,
                self._settings.gemini_model,
                self._settings.ai_max_retries,
            )
            reviewer_name = "Gemini"
            logger.info("Reviewer AI: Gemini (%s)", self._settings.gemini_model)
        else:
            logger.warning("No reviewer AI configured — running Claude only")

        if not page.extraction_complete:
            logger.warning("Skipping AI for non-extracted page: %s", page.url)
            return

        structured = build_structured_page_data(
            page.model_dump(),
            self._project.model_dump(),
        )
        section_payloads = build_section_payloads(structured)
        logger.info(
            "Section payloads for %s: %s",
            page.url,
            ", ".join(section_payloads.keys()) or "none",
        )
        if not section_payloads:
            competitor_data: list[dict[str, Any]] = []
            competitor_summary: dict[str, Any] = {}
            if self._project.competitor_urls:
                try:
                    progress("Gathering competitor data…", 0.08)
                    competitor_sources = await self._render_competitor_sources(
                        on_progress=lambda msg, i, total: progress(
                            msg, 0.08 + ((i + 1) / max(1, total)) * 0.02
                        )
                    )
                    competitor_data = await self._competitor.gather(
                        self._project.competitor_urls,
                        structured,
                        rendered_competitors=competitor_sources,
                    )
                    competitor_summary = build_competitor_summary(
                        competitor_data, structured
                    )
                except Exception as exc:
                    logger.warning("Competitor intelligence failed: %s", exc)

            page.ai_analysis = {
                "page_score": int(page.scores.total),
                "top_priority_action": "No warning or failed fields require AI analysis.",
                "annotations": [],
                "gemini_reviews": [],
                "recommendation_cards": [],
                "section_cache": {},
                "competitor_summary": competitor_summary,
                "competitor_gaps": competitor_data,
                "reviewer_active": False,
                "reviewer_label": reviewer_name if reviewer_name != "none" else "",
            }
            page.ai_complete = True
            progress("No AI issues found for this page", 1.0)
            return

        # Stable hash that changes whenever the competitor URL list changes.
        competitor_version = hashlib.sha256(
            json.dumps(
                sorted(self._project.competitor_urls or []), ensure_ascii=False
            ).encode()
        ).hexdigest()[:16]

        # Invalidate section cache when reviewer AI config changes (e.g. DeepSeek added).
        if _settings_has_deepseek(self._settings):
            reviewer_version = hashlib.sha256(
                f"deepseek:{self._settings.deepseek_model}".encode()
            ).hexdigest()[:16]
        elif _settings_has_google(self._settings):
            reviewer_version = hashlib.sha256(
                f"gemini:{self._settings.gemini_model}".encode()
            ).hexdigest()[:16]
        else:
            reviewer_version = "none"

        progress(f"Preparing section AI: {page.url}", 0.05)
        section_results: dict[str, dict[str, Any]] = {}
        changed_sections: dict[str, dict[str, Any]] = {}

        for section_id, payload in section_payloads.items():
            section_hash = self._cache.section_hash(payload)
            cached = self._cache.get_section(page.url, section_id)
            cached_ai = (cached or {}).get("ai_response") or {}
            cached_gemini = cached_ai.get("gemini") or {}
            cached_claude_anns = (cached_ai.get("claude") or {}).get("annotations") or []

            cache_valid = (
                not force
                and cached
                and cached.get("content_hash") == section_hash
                and cached.get("competitor_version") == competitor_version
                and cached.get("reviewer_version") == reviewer_version
                and cached_ai
            )
            # Re-run if reviewer is configured but cached section has no DeepSeek output
            if cache_valid and gemini and cached_claude_anns and not cached_gemini.get("reviews"):
                cache_valid = False
                logger.info(
                    "Section cache miss (reviewer upgrade): %s [%s]", page.url, section_id
                )

            if cache_valid:
                section_results[section_id] = cached_ai
                logger.info("Section AI cache hit: %s [%s]", page.url, section_id)
                continue

            changed_sections[section_id] = payload
            logger.info("Section AI scheduled: %s [%s]", page.url, section_id)
            self._cache.put_section(
                url=page.url,
                section_id=section_id,
                content_hash=section_hash,
                extracted_data=payload,
                competitor_version=competitor_version,
                reviewer_version=reviewer_version,
            )

        # Competitor intelligence runs whenever URLs are configured — regardless
        # of section cache status. It is cheap (one HTTP fetch per competitor)
        # and must always be available so Claude can reference actual gaps.
        competitor_data: list[dict[str, Any]] = []
        competitor_summary: dict[str, Any] = {}
        if self._project.competitor_urls:
            try:
                progress("Gathering competitor data…", 0.08)
                competitor_sources = await self._render_competitor_sources(
                    on_progress=lambda msg, i, total: progress(
                        msg, 0.08 + ((i + 1) / max(1, total)) * 0.02
                    ),
                    force=force,
                )
                competitor_data = await self._competitor.gather(
                    self._project.competitor_urls,
                    structured,
                    rendered_competitors=competitor_sources,
                )
                competitor_summary = build_competitor_summary(competitor_data, structured)
                logger.info(
                    "Competitor summary built: %d positive gaps",
                    len(competitor_summary.get("competitor_gap_counts", {})),
                )
            except Exception as exc:
                logger.warning("Competitor intelligence failed: %s", exc)

        total_changed = len(changed_sections)
        reviewer_attempted = False
        reviewer_errors: list[str] = []
        for index, (section_id, payload) in enumerate(changed_sections.items(), start=1):
            pct = 0.10 + (index / max(1, total_changed)) * 0.85
            progress(f"AI analysis: {section_id}", pct)
            section_hash = self._cache.section_hash(payload)

            # Claude receives section issues PLUS any competitor gaps so it can
            # produce competitor-referenced recommendations without a second AI.
            claude_prompt = build_claude_prompt(
                business_name=self._project.business_name,
                business_category=self._project.business_category.value,
                city=self._project.target_city,
                page_url=page.url,
                structured_data=payload,
                section_id=section_id,
                competitor_summary=competitor_summary if competitor_summary else None,
            )
            logger.info(
                "Claude prompt built: page=%s section=%s prompt_chars=%d "
                "seo_fields=%d local_issues=%d competitor_gaps=%d",
                page.url,
                section_id,
                len(claude_prompt),
                len(payload.get("seo_fields", {})),
                len(payload.get("local_seo", {})),
                len((competitor_summary or {}).get("competitor_gap_counts", {})),
            )
            claude_result = await claude.analyse(
                claude_prompt, page_url=page.url, section_id=section_id
            )
            logger.info(
                "Claude complete: page=%s section=%s score=%d annotations=%d",
                page.url,
                section_id,
                claude_result.page_score,
                len(claude_result.annotations),
            )

            gemini_result = None
            if gemini and claude_result.annotations:
                reviewer_attempted = True
                logger.info(
                    "Sending %d Claude annotations to %s for review: page=%s section=%s",
                    len(claude_result.annotations),
                    reviewer_name,
                    page.url,
                    section_id,
                )
                gemini_prompt = build_gemini_prompt(
                    business_name=self._project.business_name,
                    city=self._project.target_city,
                    page_url=page.url,
                    claude_annotations=[
                        ann.model_dump() for ann in claude_result.annotations
                    ],
                    competitor_data=competitor_summary,
                    structured_data=payload,
                    section_id=section_id,
                )
                try:
                    gemini_result = await gemini.review(gemini_prompt)
                except Exception as exc:
                    reviewer_errors.append(f"{section_id}: {exc}")
                    logger.error(
                        "%s review failed: page=%s section=%s error=%s",
                        reviewer_name,
                        page.url,
                        section_id,
                        exc,
                    )
                    gemini_result = None
                review_count = len(gemini_result.reviews) if gemini_result else 0
                logger.info(
                    "%s review complete: page=%s section=%s reviews=%d additional=%d",
                    reviewer_name,
                    page.url,
                    section_id,
                    review_count,
                    len(gemini_result.additional_annotations) if gemini_result else 0,
                )
            elif gemini and not claude_result.annotations:
                logger.info(
                    "%s review skipped: no Claude annotations for page=%s section=%s",
                    reviewer_name,
                    page.url,
                    section_id,
                )

            ai_response = {
                "claude": claude_result.model_dump(),
                "gemini": gemini_result.model_dump() if gemini_result else {},
            }
            self._cache.update_section_ai(
                url=page.url,
                section_id=section_id,
                content_hash=section_hash,
                extracted_data=payload,
                ai_response=ai_response,
                competitor_version=competitor_version,
                reviewer_version=reviewer_version,
            )
            section_results[section_id] = ai_response

        self._merge_section_ai(
            page,
            section_results,
            competitor_data,
            competitor_summary,
            reviewer_attempted=reviewer_attempted,
            reviewer_error="; ".join(reviewer_errors),
        )
        progress("AI analysis complete!", 1.0)

    def _merge_section_ai(
        self,
        page: PageData,
        section_results: dict[str, dict[str, Any]],
        competitor_data: list[dict[str, Any]],
        competitor_summary: dict[str, Any] | None = None,
        reviewer_attempted: bool = False,
        reviewer_error: str = "",
    ) -> None:
        """Merge cached/new section AI outputs into the existing page format."""
        from app.models.annotations import ClaudeAnalysis, GeminiAnalysis

        section_cache: dict[str, Any] = {}
        page_scores: list[int] = []
        all_annotations = []
        all_reviews = []
        all_additional = []

        for section_id, ai_response in section_results.items():
            try:
                claude_data = ai_response.get("claude") or {}
                gemini_data = ai_response.get("gemini") or {}
                claude_section = ClaudeAnalysis(**claude_data)
                gemini_section = GeminiAnalysis(**gemini_data) if gemini_data else GeminiAnalysis()

                page_scores.append(claude_section.page_score)
                all_annotations.extend(claude_section.annotations)
                all_reviews.extend(gemini_section.reviews)
                all_additional.extend(gemini_section.additional_annotations)
                section_cache[section_id] = {
                    "page_score": claude_section.page_score,
                    "annotations": [a.model_dump() for a in claude_section.annotations],
                }
            except Exception as exc:
                logger.warning("Skipping invalid section AI for %s [%s]: %s", page.url, section_id, exc)

        claude_result = ClaudeAnalysis(
            page_score=int(sum(page_scores) / len(page_scores)) if page_scores else 0,
            annotations=all_annotations,
            top_priority_action=_top_priority_action(all_annotations),
        )
        gemini_result = GeminiAnalysis(
            reviews=all_reviews,
            additional_annotations=all_additional,
        )

        page_recs = self._consensus.merge(page.url, claude_result, gemini_result)
        reviewer_active = len(gemini_result.reviews) > 0 or len(gemini_result.additional_annotations) > 0
        page.ai_analysis = {
            "page_score": claude_result.page_score,
            "top_priority_action": claude_result.top_priority_action,
            "annotations": [a.model_dump() for a in claude_result.annotations],
            "gemini_reviews": [r.model_dump() for r in gemini_result.reviews],
            "recommendation_cards": [
                c.model_dump() for c in page_recs.cards
            ],
            "section_cache": section_cache,
            "competitor_summary": competitor_summary or {},
            "competitor_gaps": competitor_data,
            "reviewer_active": reviewer_active,
            "reviewer_attempted": reviewer_attempted,
            "reviewer_error": reviewer_error,
            "reviewer_label": "DeepSeek" if _settings_has_deepseek(self._settings) else (
                "Gemini" if _settings_has_google(self._settings) else ""
            ),
        }
        page.ai_complete = True
        self._cache.update_ai_for_url(page.url, page.ai_analysis)

        if claude_result.page_score > 0 and competitor_data:
            page.scores.competitor_gap = min(5.0, competitor_data.__len__() * 0.5)


def _extract_title(html: str) -> str:
    """Extract page title from HTML without full BS4 parse."""
    import re
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()[:200]
    return ""


def _compute_hash(url: str, html: str) -> str:
    from app.utils.hash import page_cache_key
    return page_cache_key(url, html)


def _top_priority_action(annotations: list[Any]) -> str:
    """Build customer-friendly bullet points for the overview panel."""
    return format_priority_actions(annotations)


_LOW_VALUE_PATH_PARTS = (
    "impressum",
    "datenschutz",
    "privacy",
    "agb",
    "terms",
    "cookies",
    "cookie",
    "wp-json",
    "wp-content",
    "uploads",
    "feed",
    "author",
    "tag",
    "category",
)

_HIGH_VALUE_PATH_PARTS = (
    "leistung",
    "service",
    "angebot",
    "kontakt",
    "referenz",
    "bewertungen",
    "entraempel",
    "entruempel",
    "haushalts",
    "umzug",
    "transport",
)


def _prioritize_quick_audit_urls(
    urls: list[str],
    root_url: str,
    target_city: str,
    service_areas: list[str],
    max_pages: int,
) -> list[str]:
    """Pick high-value URLs for a fast local SEO audit.

    The full pipeline remains unchanged; this only reduces which pages enter
    rendering/extraction/AI. Homepage is always first, then service/contact/city
    pages, while legal and archive-style URLs are skipped.
    """
    root_host = urlparse(root_url).netloc.lower()
    seen: set[str] = set()
    candidates: list[tuple[int, int, str]] = []

    city_terms = [target_city.lower(), *(area.lower() for area in service_areas)]

    for index, url in enumerate(urls):
        parsed = urlparse(url)
        if parsed.netloc.lower() != root_host:
            continue
        if not is_crawlable_page_url(url):
            continue

        path = parsed.path.strip("/").lower()
        if url in seen:
            continue
        if any(part in path for part in _LOW_VALUE_PATH_PARTS):
            continue

        seen.add(url)
        score = 0

        if not path:
            score += 1000
        if any(part in path for part in _HIGH_VALUE_PATH_PARTS):
            score += 250
        if any(city and city in path for city in city_terms):
            score += 175
        if path.count("/") == 0:
            score += 40
        if len(path) <= 40:
            score += 20

        candidates.append((-score, index, url))

    candidates.sort()
    prioritized = [url for _, _, url in candidates[:max_pages]]

    # If all links were filtered out, fall back to the first discovered URL.
    return prioritized or urls[:1]
