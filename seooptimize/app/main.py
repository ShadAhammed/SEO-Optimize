"""SEOOptimize v1.0 — Streamlit application entry point.

Run with:
    streamlit run app/main.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

# Make the project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import nest_asyncio
import streamlit as st

from app.config.settings import Settings, settings
from app.config.theme import CUSTOM_CSS
from app.core.logging import setup_logging

# ── Bootstrap ─────────────────────────────────────────────────────────────────
nest_asyncio.apply()
setup_logging(settings.log_level)
settings.cache_path.mkdir(parents=True, exist_ok=True)


def _reload_settings() -> Settings:
    """Re-read .env and return a fresh Settings instance."""
    return Settings()


def _has_deepseek_key(cfg: Settings) -> bool:
    import os

    cfg_val = str(getattr(cfg, "deepseek_api_key", "") or "").strip()
    env_val = (
        os.getenv("DEEPSEEK_API_KEY", "")
        or os.getenv("DeepSeek_API_KEY", "")
        or os.getenv("deepseek_api_key", "")
    )
    if cfg_val or str(env_val).strip():
        return True

    # Final fallback: read .env file directly (works even with stale process env).
    env_file = Path(__file__).resolve().parent.parent / ".env"
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


def _has_anthropic_key(cfg: Settings) -> bool:
    return bool(getattr(cfg, "anthropic_api_key", "").strip())


def _competitor_cache_file(cfg: Settings, competitor_urls: list[str]) -> Path:
    """Return competitor cache file path for the configured URL set."""
    key = hashlib.sha256(
        json.dumps(sorted(competitor_urls[:8]), ensure_ascii=False).encode()
    ).hexdigest()[:16]
    return cfg.cache_path / "competitors" / f"{key}.json"


def _get_competitor_sources(cfg: Settings, competitor_urls: list[str]) -> list[dict]:
    """Read cached competitor sources without depending on CacheStore methods."""
    if not cfg.cache_enabled or not competitor_urls:
        return []
    cache_file = _competitor_cache_file(cfg, competitor_urls)
    if not cache_file.exists():
        return []
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    sources = data.get("sources", [])
    return sources if isinstance(sources, list) else []


def _clear_page_sections(cfg: Settings, url: str) -> None:
    """Clear section cache for one URL without depending on CacheStore methods."""
    if not cfg.cache_enabled:
        return
    url_key = hashlib.sha256(url.encode()).hexdigest()[:16]
    section_dir = cfg.cache_path / "sections" / url_key
    if not section_dir.exists():
        return
    for f in section_dir.glob("*.json"):
        try:
            f.unlink()
        except Exception:
            continue

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="SEOOptimize",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Lazy imports (avoid circular imports at module level) ─────────────────────
from app.models.page import PageData
from app.models.project import ProjectConfig
from app.ui.components.sidebar import SITE_SUMMARY_ID, render_sidebar
from app.ui.pages.setup import render_setup_page
from app.ui.pages.overview import render_overview_page
from app.ui.pages.canvas_page import render_canvas_page
from app.ui.pages.details import render_details_page
from app.ui.components.consolidated_report import render_consolidated_action_plan
from app.exports.report_data import is_kontakt_url
from app.ui.app_state import get_export_lang, init_app_state, reset_export_lang


# ── Session state initialisation ──────────────────────────────────────────────
def _init_state() -> None:
    defaults: dict = {
        "view": "setup",              # "setup" | "analysis"
        "project": None,              # ProjectConfig
        "pages": [],                  # list[PageData]
        "selected_url": None,         # str
        "active_tab": "Overview",     # "Overview" | "Canvas" | "Details"
        "show_competitor_intel": False,
        "analysis_running": False,
        "trigger_export": False,
        "setup_form_version": 2,
        "competitor_sources": [],     # rendered competitor extraction dicts
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # Drop widget state from the old form (v1 keys / placeholders era).
    if st.session_state.get("setup_form_version") == 2:
        stale_prefixes = ("comp_",)
        stale_keys = {"project_setup"}
        for key in list(st.session_state.keys()):
            if key in stale_keys or key.startswith(stale_prefixes):
                del st.session_state[key]
        st.session_state["setup_form_version"] = 3


def _run_analysis(project: ProjectConfig, cfg: Settings) -> None:
    """Launch the full analysis pipeline for the configured project."""
    from app.services.analysis_service import AnalysisService

    service = AnalysisService(project, cfg)

    progress = st.progress(0, text="Initialising…")
    status = st.empty()

    def on_progress(step: str, pct: float) -> None:
        progress.progress(int(pct * 100), text=step)
        status.caption(step)

    try:
        pages = asyncio.run(service.run(on_progress=on_progress))
        st.session_state["pages"] = pages
        # Load competitor data into session so the sidebar can display it immediately.
        # Use a fresh CacheStore (not service._cache which may be stale).
        if project.competitor_urls:
            st.session_state["competitor_sources"] = _get_competitor_sources(
                cfg, project.competitor_urls
            )
        if pages:
            st.session_state["selected_url"] = pages[0].url
            st.session_state["view"] = "analysis"
            st.session_state["analysis_running"] = False
            progress.empty()
            status.empty()
            st.success(f"Analysis complete — {len(pages)} pages processed.")
            st.rerun()
        else:
            progress.empty()
            status.empty()
            st.error(
                "No pages could be discovered or rendered. "
                "Check the website URL and try again."
            )
            st.session_state["view"] = "setup"
            st.session_state["analysis_running"] = False
    except Exception as exc:
        progress.empty()
        status.empty()
        st.error(f"Analysis failed: {exc}")
        st.session_state["analysis_running"] = False


def _ensure_ai_analysis(page: PageData, project: ProjectConfig, cfg: Settings) -> None:
    """Run lazy AI for the currently opened page if needed."""
    if not page.extraction_complete:
        st.caption("AI status: skipped because deterministic extraction is not complete.")
        return

    refresh_required = _needs_ai_refresh(page, project, cfg)
    if page.ai_complete and not refresh_required:
        ai = page.ai_analysis or {}
        st.caption(
            "AI status: using cached analysis "
            f"({len(ai.get('recommendation_cards') or [])} cards, "
            f"{len(ai.get('gemini_reviews') or [])} DeepSeek reviews)."
        )
        return

    from app.services.analysis_service import AnalysisService

    service = AnalysisService(project, cfg)

    spinner_text = (
        "Refreshing AI recommendations with competitors + DeepSeek…"
        if refresh_required else
        "Preparing AI recommendations…"
    )
    with st.spinner(spinner_text):
        status = st.empty()

        def on_progress(step: str, pct: float) -> None:
            status.caption(f"{int(pct * 100)}% — {step}")

        try:
            # Reset the completion flag so run_ai_for_page always re-runs.
            page.ai_complete = False
            asyncio.run(
                service.run_ai_for_page(page, on_progress=on_progress)
            )
            # Refresh competitor sources in session after AI run
            if project.competitor_urls:
                comp = _get_competitor_sources(cfg, project.competitor_urls)
                if comp:
                    st.session_state["competitor_sources"] = comp
        except Exception as exc:
            page.error = f"AI analysis failed: {exc}"
            st.warning(page.error)
        finally:
            status.empty()


def _needs_ai_refresh(page: PageData, project: ProjectConfig, cfg: Settings) -> bool:
    """Return true when cached AI lacks now-required competitor/reviewer data."""
    if not page.ai_complete:
        return False

    ai = page.ai_analysis or {}
    fail_or_warn = page.extracted.fail_count() + page.extracted.warn_count()
    annotations = ai.get("annotations") or []
    cards = ai.get("recommendation_cards") or []

    if project.competitor_urls:
        summary = ai.get("competitor_summary") or {}
        if not summary.get("current_site") and not ai.get("competitor_gaps"):
            return True

    # If deterministic extraction found issues but cached AI has no cards, the
    # page should not be treated as complete.
    if fail_or_warn and not cards and not annotations:
        return True

    # DeepSeek must review any cached Claude output, whether it is represented
    # as raw annotations or already-merged recommendation cards.
    if _has_deepseek_key(cfg) and (annotations or cards):
        if not ai.get("reviewer_active") or not (ai.get("gemini_reviews") or []):
            return True

    return False


# ── Main render loop ──────────────────────────────────────────────────────────
def main() -> None:
    cfg = _reload_settings()
    _init_state()

    project: ProjectConfig | None = st.session_state["project"]
    init_app_state(project)
    pages: list[PageData] = st.session_state["pages"]
    selected_url: str | None = st.session_state["selected_url"]

    # ── Load competitor sources from cache if not yet in session ──────────────
    if (
        project
        and project.competitor_urls
        and not st.session_state.get("competitor_sources")
    ):
        cached_comp = _get_competitor_sources(cfg, project.competitor_urls)
        if cached_comp:
            st.session_state["competitor_sources"] = cached_comp

    # ── Sidebar ──────────────────────────────────────────────────────────────
    competitor_sources: list[dict] = st.session_state.get("competitor_sources", [])
    clicked_url = render_sidebar(project, pages, selected_url, competitor_sources)
    if clicked_url and clicked_url != selected_url:
        st.session_state["selected_url"] = clicked_url
        # Leaving competitor dashboard should happen automatically on page navigation.
        st.session_state["show_competitor_intel"] = False
        st.rerun()

    # ── Main content area ────────────────────────────────────────────────────
    # analysis_running must be checked before setup — otherwise a rerun after
    # submit still has view=="setup" and the pipeline never starts.
    if st.session_state.get("analysis_running"):
        project = st.session_state["project"]
        st.markdown(f"## Analysing {project.website_url}")
        _run_analysis(project, cfg)
        st.session_state["analysis_running"] = False

    elif st.session_state["view"] == "setup":
        config = render_setup_page()
        if config:
            st.session_state["project"] = config
            reset_export_lang(config)
            st.session_state["analysis_running"] = True
            st.rerun()

    elif st.session_state["view"] == "analysis":
        # ── Site Summary (left sidebar) ───────────────────────────────────
        if st.session_state.get("selected_url") == SITE_SUMMARY_ID:
            if st.session_state.get("show_competitor_intel"):
                _render_competitor_dashboard(project, pages, competitor_sources)
                if st.button("← Back to Summary", key="comp_intel_back_summary"):
                    st.session_state["show_competitor_intel"] = False
                    st.rerun()
                return

            _render_site_summary_view(project, pages)
            if st.session_state.get("trigger_export"):
                st.session_state["trigger_export"] = False
                _trigger_export(project, pages, cfg)
            return

        # ── Per-page analysis ─────────────────────────────────────────────
        current_url = st.session_state.get("selected_url")
        current_page: PageData | None = next(
            (p for p in pages if p.url == current_url), None
        )

        if not current_page and pages:
            current_page = pages[0]
            st.session_state["selected_url"] = current_page.url

        if not current_page:
            st.info("No pages found. Start a new project.")
            return

        col_refresh, col_status = st.columns([1, 3])
        with col_refresh:
            if st.button(
                "Force AI refresh",
                key=f"force_ai_refresh_{current_page.url}",
                help="Clears this page's section cache and re-runs Claude + DeepSeek.",
                use_container_width=True,
            ):
                # Wipe section cache so Claude + DeepSeek run fresh.
                _clear_page_sections(cfg, current_page.url)
                current_page.ai_complete = False
                current_page.ai_analysis = {}
                st.session_state["pages"] = pages
                st.rerun()
        with col_status:
            ai_meta = current_page.ai_analysis or {}
            reviewer_attempted = bool(ai_meta.get("reviewer_attempted", False))
            reviewer_state = "attempted" if reviewer_attempted else "not-attempted"
            if project.competitor_urls:
                st.caption(
                    f"Competitors configured: {len(project.competitor_urls)} | "
                    f"DeepSeek key: {'loaded' if _has_deepseek_key(cfg) else 'missing'} | "
                    f"Reviewer: {reviewer_state} | "
                    f"Claude key: {'loaded' if _has_anthropic_key(cfg) else 'missing'}"
                )
            else:
                st.caption(
                    f"No competitor URLs configured | "
                    f"DeepSeek key: {'loaded' if _has_deepseek_key(cfg) else 'missing'} | "
                    f"Reviewer: {reviewer_state} | "
                    f"Claude key: {'loaded' if _has_anthropic_key(cfg) else 'missing'}"
                )

        # ── Competitor Intelligence full dashboard ────────────────────────────
        if st.session_state.get("show_competitor_intel"):
            _render_competitor_dashboard(project, pages, competitor_sources)
            if st.button("← Back to page analysis", key="comp_intel_back"):
                st.session_state["show_competitor_intel"] = False
                st.rerun()
            return

        _ensure_ai_analysis(current_page, project, cfg)

        tab_overview, tab_canvas, tab_details, tab_recs = st.tabs(
            ["📊 Overview", "🖼️ Canvas", "🔍 Details", "💡 Recommendations"]
        )

        with tab_overview:
            render_overview_page(current_page, project)

        with tab_canvas:
            render_canvas_page(current_page, project)

        with tab_details:
            render_details_page(current_page, project)

        with tab_recs:
            _render_recommendations_tab(current_page, project)

        # ── Kontakt: English site-wide summary (matches PDF action plan) ──
        if is_kontakt_url(current_page.url):
            st.markdown("---")
            render_consolidated_action_plan(
                project,
                pages,
                lang="en",
                variant="kontakt",
                expanded=True,
            )

        # ── Export trigger ────────────────────────────────────────────────
        if st.session_state.get("trigger_export"):
            st.session_state["trigger_export"] = False
            _trigger_export(project, pages, cfg)


def _render_site_summary_view(project: ProjectConfig, pages: list[PageData]) -> None:
    """Left-sidebar Summary — site-wide action plan (English, matches PDF export)."""
    from app.exports.report_data import collect_consolidated_issues, tier_counts
    from app.ui.components.consolidated_report import render_consolidated_action_plan

    analysed = [p for p in pages if p.extraction_complete]
    scores = [int(p.scores.total) for p in analysed]
    avg = sum(scores) // len(scores) if scores else 0

    issues = collect_consolidated_issues(analysed, project, lang="en")
    counts = tier_counts(issues)
    critical = sum(1 for i in issues if i.priority == "critical")
    warnings = sum(1 for i in issues if i.priority == "warning")

    st.markdown("## 📋 Site Summary")
    st.caption(
        f"Extended report for **{project.business_name}** — all pages combined. "
        "Same data as the final section of the PDF export."
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Site score", f"{avg}/100")
    m2.metric("Pages", len(analysed))
    m3.metric("Critical", critical)
    m4.metric("Warnings", warnings)
    m5.metric("Fix packages", f"{counts.get('Basic', 0)} / {counts.get('Advanced', 0)} / {counts.get('All', 0)}")

    st.markdown("---")
    render_consolidated_action_plan(
        project,
        pages,
        lang="en",
        variant="default",
        expanded=True,
    )


def _render_competitor_dashboard(
    project: ProjectConfig,
    pages: list[PageData],
    competitor_sources: list[dict],
) -> None:
    """Full Competitor Intelligence dashboard (SEOArch.md §Issue 6 + §Issue 7)."""
    import html as _html
    from urllib.parse import urlparse as _up

    st.markdown("## 🏁 Competitor Intelligence")
    st.caption(
        f"Analysed {len(competitor_sources)} competitor site(s) for "
        f"**{project.business_name}** — only showing features competitors have that you lack."
    )

    if not competitor_sources:
        st.info("No competitor data yet. Run a new analysis with competitor URLs configured.")
        return

    # Build client signals from extraction results
    client: dict[str, bool] = {}
    for page in pages:
        if page.extraction_complete and page.local_seo:
            ls = page.local_seo
            client = {
                "has_faq":      bool(getattr(ls, "has_faq", False)),
                "has_reviews":  bool(getattr(ls, "has_review_signals", False)),
                "has_whatsapp": bool(getattr(ls, "has_whatsapp", False)),
                "has_schema":   bool(getattr(ls, "has_local_business_schema", False)),
                "has_phone":    bool(getattr(ls, "nap_phone", "")),
            }
            break

    feature_def: list[tuple[str, str, str, str]] = [
        ("has_faq",      "❓ FAQ section",           "Answers common questions → trust + SEO",       "Add a FAQ section with schema markup"),
        ("has_reviews",  "⭐ Google Reviews",         "Social proof → higher conversion rate",         "Embed Google review widget or review count"),
        ("has_whatsapp", "💬 WhatsApp button",        "Instant contact → more leads",                  "Add WhatsApp chat button (wa.me link)"),
        ("has_schema",   "🗂️ Structured data",        "Enables rich results → higher CTR",             "Add LocalBusiness JSON-LD schema"),
        ("has_phone",    "📞 Phone above fold",       "Urgent callers bounce if phone is hard to find","Add click-to-call tel: link in header"),
    ]

    # ── Competitor-by-competitor breakdown ───────────────────────────────────
    for comp in competitor_sources:
        domain = comp.get("domain") or _up(comp.get("url", "?")).netloc
        url = comp.get("url", "")
        gaps = [
            (label, rationale, fix)
            for key, label, rationale, fix in feature_def
            if comp.get(key) and not client.get(key, True)
        ]

        with st.expander(f"**{domain}** — {len(gaps)} gap(s) found", expanded=bool(gaps)):
            if not gaps:
                st.success("No competitive gaps on checked signals — you match or exceed this competitor.")
                continue
            for label, rationale, fix in gaps:
                st.markdown(
                    f"<div style='background:#1E293B;border-left:3px solid #EF4444;"
                    f"padding:10px 14px;border-radius:6px;margin-bottom:8px;'>"
                    f"<div style='font-weight:700;font-size:0.9rem;color:#F1F5F9;'>{label}</div>"
                    f"<div style='font-size:0.8rem;color:#94A3B8;margin:4px 0;'>{_html.escape(rationale)}</div>"
                    f"<div style='font-size:0.8rem;color:#93C5FD;'>→ {_html.escape(fix)}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # ── Cross-competitor gap summary ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Comparison Summary")

    gap_counts: dict[str, int] = {}
    for comp in competitor_sources:
        for key, label, _, _ in feature_def:
            if comp.get(key) and not client.get(key, True):
                gap_counts[label] = gap_counts.get(label, 0) + 1

    if not gap_counts:
        st.success(
            f"**{project.business_name}** matches or exceeds all competitors "
            "on the checked signals. No urgent gaps found."
        )
    else:
        total = len(competitor_sources)
        rows = sorted(gap_counts.items(), key=lambda x: -x[1])
        for label, count in rows:
            pct = count / total
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:10px;"
                f"margin-bottom:6px;'>"
                f"<div style='width:140px;font-size:0.82rem;color:#CBD5E1;'>{label}</div>"
                f"<div style='flex:1;background:#334155;border-radius:4px;height:12px;'>"
                f"<div style='width:{int(pct*100)}%;background:#EF4444;"
                f"border-radius:4px;height:12px;'></div></div>"
                f"<div style='width:60px;font-size:0.78rem;color:#94A3B8;text-align:right;'>"
                f"{count}/{total} competitors</div></div>",
                unsafe_allow_html=True,
            )


def _render_recommendations_tab(page: PageData, project: ProjectConfig) -> None:
    """Render the recommendations tab using data from AI analysis."""
    from app.ui.components.ai_insights import (
        render_ai_consensus_table,
        render_competitor_gaps,
    )
    from app.ui.components.rec_card import render_recommendation_card

    st.markdown("## AI Recommendations")

    if not page.ai_complete:
        st.info("AI analysis has not run yet for this page.")
        return

    if project.competitor_urls:
        render_competitor_gaps(project, page)
        st.markdown("---")

    render_ai_consensus_table(page)
    st.markdown("---")

    cards_data = page.ai_analysis.get("recommendation_cards", [])
    if not cards_data:
        st.info("No recommendation cards generated yet.")
        return

    from app.models.recommendations import RecommendationCard

    show_low_conf = st.checkbox(
        "Show low-confidence recommendations (< 65%)",
        value=False,
        key=f"show_low_conf_{page.url}",
    )

    displayed = 0
    for i, card_data in enumerate(cards_data):
        try:
            card = RecommendationCard(**card_data)
        except Exception:
            continue
        if not show_low_conf and not card.is_visible_by_default:
            continue
        render_recommendation_card(card, index=i)
        displayed += 1

    if displayed == 0:
        st.info(
            "All recommendations are below the 65% confidence threshold. "
            "Toggle 'Show low-confidence' to see them."
        )


def _trigger_export(project: ProjectConfig, pages: list[PageData], cfg: Settings) -> None:
    """Generate the full site PDF report and offer it as a download."""
    from app.exports.pdf import generate_pdf_report
    from app.services.analysis_service import AnalysisService

    analysed = [p for p in pages if p.extraction_complete]
    if not analysed:
        st.warning("No analysed pages to export yet.")
        return

    with st.spinner(f"Finalising AI for {len(analysed)} page(s) before export…"):
        service = AnalysisService(project, cfg)
        status = st.empty()
        for idx, page in enumerate(analysed, start=1):
            needs_refresh = _needs_ai_refresh(page, project, cfg)
            if page.ai_complete and not needs_refresh:
                continue

            def on_progress(step: str, pct: float, page_idx: int = idx) -> None:
                status.caption(
                    f"Page {page_idx}/{len(analysed)} — {int(pct * 100)}% — {step}"
                )

            try:
                page.ai_complete = False
                asyncio.run(service.run_ai_for_page(page, on_progress=on_progress))
            except Exception as exc:
                page.error = f"AI export refresh failed: {exc}"
                st.warning(f"{page.url}: {page.error}")
        status.empty()

    with st.spinner(f"Building report for {len(analysed)} page(s)…"):
        try:
            report_lang = get_export_lang(project)

            safe_name = project.business_name.replace(" ", "_")
            from datetime import datetime
            date_tag = datetime.now().strftime("%Y%m%d")

            cache_key = f"{len(analysed)}_{date_tag}_{project.website_url}"
            pdf_cache: dict[str, bytes] = st.session_state.get("export_pdf_cache", {})
            if st.session_state.get("export_cache_key") != cache_key or not pdf_cache:
                pdf_cache = {
                    "en": generate_pdf_report(project, analysed, lang="en"),
                    "de": generate_pdf_report(project, analysed, lang="de"),
                }
                st.session_state["export_pdf_cache"] = pdf_cache
                st.session_state["export_cache_key"] = cache_key

            st.success(f"Report ready — {len(analysed)} pages included.")
            st.caption(
                "Download in your preferred language. The final section lists all "
                "errors and warnings with competitor matches and fix packages "
                "(Basic · Advanced · Full Campaign)."
            )

            dl_cols = st.columns(2)
            for col, lang, label in (
                (dl_cols[0], "en", "🇬🇧 Download English PDF"),
                (dl_cols[1], "de", "🇩🇪 Download German PDF"),
            ):
                with col:
                    lang_tag = lang.upper()
                    st.download_button(
                        label=label,
                        data=pdf_cache[lang],
                        file_name=f"SEO_Audit_{safe_name}_{date_tag}_{lang_tag}.pdf",
                        mime="application/pdf",
                        key=f"download_pdf_{lang}",
                        use_container_width=True,
                        type="primary" if lang == report_lang else "secondary",
                    )
        except Exception as exc:
            st.error(f"Export failed: {exc}")


if __name__ == "__main__":
    main()
