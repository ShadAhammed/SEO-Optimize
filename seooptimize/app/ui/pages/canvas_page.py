"""Canvas view — annotated screenshot with clickable overlays."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.models.page import PageData
from app.models.project import ProjectConfig
from app.ui.components.ai_insights import render_ai_consensus_table, render_competitor_gaps


def render_canvas_page(page: PageData, project: ProjectConfig) -> None:
    """Render the visual canvas — annotated screenshot with sidebar panel."""
    st.markdown(f"## Visual Canvas — {_short_url(page.url)}")

    if not page.screenshot_path:
        st.info(
            "Screenshot not yet available. Run the crawl and rendering step first."
        )
        return

    screenshot = Path(page.screenshot_path)
    if not screenshot.exists():
        st.warning(f"Screenshot file not found: {page.screenshot_path}")
        return

    # ── Viewport toggle ──────────────────────────────────────────────────────
    col_t, col_conf = st.columns([2, 1])
    with col_t:
        view_mode = st.radio(
            "Viewport",
            ["Desktop (1280px)", "Mobile (375px)"],
            horizontal=True,
        )
    with col_conf:
        show_low_conf = st.checkbox(
            "Show low-confidence annotations",
            value=False,
            help="By default only annotations with confidence ≥ 65% are shown",
        )

    is_mobile = "Mobile" in view_mode
    shot_path = page.mobile_screenshot_path if is_mobile else page.screenshot_path
    if is_mobile and not Path(shot_path or "").exists():
        st.warning("Mobile screenshot not available — showing desktop.")
        shot_path = page.screenshot_path

    # ── Load and render annotated image ─────────────────────────────────────
    annotations_raw = page.ai_analysis.get("annotations", [])

    if annotations_raw and page.element_boxes:
        from app.canvas.renderer import render_canvas
        from app.models.annotations import Annotation

        annotations = []
        for a in annotations_raw:
            try:
                annotations.append(Annotation(**a))
            except Exception:
                continue

        # Filter by confidence
        threshold = 0.0 if show_low_conf else 0.65
        filtered = [a for a in annotations if a.confidence >= threshold]

        try:
            annotated = render_canvas(
                screenshot_path=shot_path,
                annotations=filtered,
                element_boxes=page.element_boxes,
            )
            st.image(annotated, use_container_width=True)
        except Exception as exc:
            st.warning(f"Could not render annotations: {exc}")
            st.image(shot_path, use_container_width=True)
    else:
        st.image(shot_path or page.screenshot_path, use_container_width=True)

    # ── Annotation panel ──────────────────────────────────────────────────────
    if annotations_raw:
        st.markdown("---")
        st.markdown("### Annotations")
        threshold = 0.0 if show_low_conf else 0.65
        for ann in annotations_raw:
            conf = ann.get("confidence", 1.0)
            if conf < threshold:
                continue
            priority = ann.get("priority", "warning")
            colors = {
                "critical": ("🔴", "#FEE2E2", "#991B1B"),
                "warning": ("🟡", "#FEF3C7", "#92400E"),
                "quick_win": ("🟢", "#D1FAE5", "#065F46"),
                "ok": ("⚪", "#F3F4F6", "#374151"),
            }
            icon, bg, fg = colors.get(priority, ("⚪", "#F3F4F6", "#374151"))
            st.markdown(
                f"""
                <div style="background:{bg};border-radius:8px;padding:10px 14px;
                            margin-bottom:8px;">
                    <span style="font-weight:700;color:{fg};">{icon} {ann.get('label','')}</span>
                    <span style="float:right;font-size:0.75rem;color:{fg};">
                        {conf*100:.0f}% · {ann.get('selector','')}
                    </span>
                    <br><span style="font-size:0.85rem;">{ann.get('issue','')}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if project.competitor_urls:
        st.markdown("---")
        render_competitor_gaps(project, page)

    if page.ai_complete:
        st.markdown("---")
        render_ai_consensus_table(page)


def _short_url(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    path = p.path.strip("/")
    return f"{p.netloc}/{path}" if path else p.netloc
