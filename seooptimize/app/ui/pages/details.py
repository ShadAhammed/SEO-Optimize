"""Details view — field-by-field analysis of one page."""

from __future__ import annotations

import streamlit as st

from app.models.page import ExtractionResult, FieldScore, PageData, ScoreStatus
from app.models.project import ProjectConfig
from app.ui.components.ai_insights import render_ai_consensus_table, render_competitor_gaps
from app.ui.components.score_display import status_pill


_FIELD_META: list[tuple[str, str, str]] = [
    # (attr, display_label, help_text)
    ("meta_title", "Meta Title", "Optimal: 50–60 characters, contains target keyword"),
    ("meta_description", "Meta Description", "Optimal: 150–160 characters with CTA"),
    ("h1", "H1 Tag", "One H1, contains primary keyword"),
    ("h2_structure", "H2 Structure", "3+ H2 tags present"),
    ("word_count", "Word Count", "600+ words on service pages"),
    ("images_with_alt", "Image Alt Text", "All images have descriptive alt attributes"),
    ("phone_above_fold", "Phone Above Fold", "Phone number visible without scrolling"),
    ("schema_markup", "Schema Markup", "LocalBusiness + Service schema present"),
    ("canonical_tag", "Canonical Tag", "Present and self-referencing"),
    ("mobile_viewport", "Mobile Viewport", "Meta viewport tag present"),
    ("nap_on_page", "NAP on Page", "Name, Address, Phone all present"),
    ("internal_links", "Internal Links", "3+ contextual internal links"),
    ("page_load_time", "Page Load Time", "Under 2.5s LCP"),
    ("https", "HTTPS", "Full HTTPS — no mixed content"),
]


def render_details_page(page: PageData, project: ProjectConfig) -> None:
    """Render the field-by-field analysis view."""
    st.markdown(f"## Detailed Analysis — {_short_url(page.url)}")

    if not page.extraction_complete:
        st.info("Page has not been extracted yet. Run the analysis pipeline first.")
        return

    ext = page.extracted

    # ── Summary row ────────────────────────────────────────────────────────
    col_p, col_w, col_f = st.columns(3)
    with col_p:
        st.metric("Passed", ext.pass_count(), delta=None)
    with col_w:
        st.metric("Warnings", ext.warn_count(), delta=None)
    with col_f:
        st.metric("Failed", ext.fail_count(), delta=None)

    st.markdown("---")
    st.markdown("### SEO Field Audit")

    # ── Field table ────────────────────────────────────────────────────────
    for attr, label, help_text in _FIELD_META:
        field: FieldScore | None = getattr(ext, attr, None)
        if field is None:
            continue

        with st.container():
            col_label, col_val, col_status = st.columns([3, 4, 1])

            with col_label:
                st.markdown(
                    f"<div style='padding:6px 0;'>"
                    f"<strong style='font-size:0.9rem;'>{label}</strong>"
                    f"<br><span style='font-size:0.75rem;color:#64748B;'>{help_text}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with col_val:
                value_display = _format_value(field.value)
                st.markdown(
                    f"<div style='padding:6px 0;font-size:0.85rem;"
                    f"word-break:break-word;'>{value_display}</div>",
                    unsafe_allow_html=True,
                )
            with col_status:
                st.markdown(
                    f"<div style='padding:6px 0;'>{status_pill(field.status)}</div>",
                    unsafe_allow_html=True,
                )

            if field.note:
                st.markdown(
                    f"<div style='font-size:0.8rem;color:#64748B;"
                    f"padding:0 0 6px 0;'>{field.note}</div>",
                    unsafe_allow_html=True,
                )

        st.markdown(
            "<hr style='margin:4px 0;border-color:#F1F5F9;'>",
            unsafe_allow_html=True,
        )

    # ── Headings structure ──────────────────────────────────────────────────
    if ext.all_headings:
        st.markdown("---")
        st.markdown("### Heading Structure")
        for h in ext.all_headings:
            tag = h.get("tag", "h2")
            text = h.get("text", "")
            indent = (int(tag[1]) - 1) * 20 if tag[1:].isdigit() else 0
            st.markdown(
                f"<div style='padding:3px 0;padding-left:{indent}px;font-size:0.85rem;'>"
                f"<strong style='color:#64748B;'>{tag.upper()}</strong> {text}</div>",
                unsafe_allow_html=True,
            )

    # ── Schema objects ─────────────────────────────────────────────────────
    if ext.schema_objects:
        st.markdown("---")
        st.markdown("### Detected Schema Markup")
        for schema in ext.schema_objects:
            schema_type = _schema_label(schema)
            with st.expander(f"Schema: {schema_type}"):
                st.json(schema)

    # ── FAQ items ──────────────────────────────────────────────────────────
    if ext.faq_items:
        st.markdown("---")
        st.markdown("### FAQ Content Detected")
        for item in ext.faq_items:
            with st.expander(item.get("question", "Question")):
                st.write(item.get("answer", ""))

    # ── Local SEO section ──────────────────────────────────────────────────
    local = page.local_seo
    if local:
        st.markdown("---")
        st.markdown("### Local SEO Audit")

        _local_row("NAP Consistent", local.nap_consistent)
        if local.nap_name:
            st.caption(f"Name: {local.nap_name} | Address: {local.nap_address} | Phone: {local.nap_phone}")
        if local.nap_issues:
            for issue in local.nap_issues:
                st.warning(f"NAP Issue: {issue}")

        _local_row("LocalBusiness Schema", local.has_local_business_schema)
        if local.schema_missing_fields:
            st.caption(f"Missing fields: {', '.join(local.schema_missing_fields)}")

        _local_row("City in Title", local.city_in_title)
        _local_row("City in H1", local.city_in_h1)
        st.caption(f"City mentions on page: {local.city_mention_count}")

        _local_row("Review Signals", local.has_review_signals)
        _local_row("Phone Above Fold (Mobile)", local.phone_above_fold_mobile)
        _local_row("WhatsApp Button", local.has_whatsapp)
        _local_row("Response Time Claim", local.has_response_time_claim)
        _local_row("Free Inspection Offer", local.has_free_inspection)
        _local_row("Insurance/Cert Badge", local.has_insurance_badge)
        _local_row("Photo Gallery", local.has_photo_gallery)

    if project.competitor_urls:
        st.markdown("---")
        render_competitor_gaps(project, page)

    if page.ai_complete:
        st.markdown("---")
        render_ai_consensus_table(page)


def _local_row(label: str, value: bool) -> None:
    icon = "✅" if value else "❌"
    st.markdown(
        f"<div style='display:flex;gap:8px;padding:3px 0;font-size:0.85rem;'>"
        f"<span>{icon}</span><span>{label}</span></div>",
        unsafe_allow_html=True,
    )


def _format_value(value: object) -> str:
    if value is None:
        return "<em style='color:#94A3B8;'>—</em>"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value[:5])
    text = str(value)
    if len(text) > 200:
        return text[:200] + "…"
    return text or "<em style='color:#94A3B8;'>—</em>"


def _schema_label(schema: dict) -> str:
    """Return a readable label for flat or @graph schema objects."""
    direct = schema.get("@type")
    if direct:
        return str(direct)

    graph = schema.get("@graph")
    if isinstance(graph, list):
        types: list[str] = []
        for item in graph:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type")
            if isinstance(item_type, list):
                types.extend(str(t) for t in item_type)
            elif item_type:
                types.append(str(item_type))
        if types:
            unique = list(dict.fromkeys(types))
            return ", ".join(unique[:4]) + ("…" if len(unique) > 4 else "")

    return "Unknown"


def _short_url(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    path = p.path.strip("/")
    return f"{p.netloc}/{path}" if path else p.netloc
