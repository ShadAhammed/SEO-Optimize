"""Six-axis scoring calculator.

Converts ExtractionResult + LocalSEOResult into a SixAxisScore using the
weights defined in SEOArch.md §2:

    Local SEO        30%
    Content Quality  25%
    Technical SEO    15%
    Conversion       15%
    Metadata         10%
    Competitor Gap    5%
"""

from __future__ import annotations

from app.models.page import (
    ExtractionResult,
    FieldScore,
    LocalSEOResult,
    ScoreStatus,
    SixAxisScore,
)


def _field_score(field: FieldScore) -> float:
    """Convert pass/warn/fail to a 0–1 value."""
    return {
        ScoreStatus.PASS: 1.0,
        ScoreStatus.WARN: 0.5,
        ScoreStatus.FAIL: 0.0,
        ScoreStatus.NA: 0.5,  # Neutral for unavailable fields
    }.get(field.status, 0.5)


def calculate_scores(
    extracted: ExtractionResult,
    local_seo: LocalSEOResult,
    competitor_gap_score: float = 0.5,
) -> SixAxisScore:
    """Calculate a SixAxisScore from deterministic extraction results.

    Args:
        extracted: Output from DOMExtractor.
        local_seo: Output from LocalSEOAnalyser.
        competitor_gap_score: 0.0–1.0 from competitor intelligence module
                              (defaults to neutral 0.5 until M9 is complete).

    Returns:
        SixAxisScore with each axis scored out of its max value.
    """
    # ── Local SEO (max 30) ────────────────────────────────────────────────────
    local_signals = [
        1.0 if local_seo.nap_consistent else 0.0,
        1.0 if local_seo.has_local_business_schema else 0.0,
        1.0 if local_seo.city_in_title else 0.0,
        1.0 if local_seo.city_in_h1 else 0.0,
        1.0 if local_seo.has_review_signals else 0.0,
        local_seo.urgency_score,
        _field_score(extracted.nap_on_page),
        1.0 if not local_seo.schema_missing_fields else 0.0,
    ]
    local_raw = sum(local_signals) / len(local_signals)
    local_seo_score = local_raw * 30.0

    # ── Content Quality (max 25) ──────────────────────────────────────────────
    content_signals = [
        _field_score(extracted.word_count),
        _field_score(extracted.h1),
        _field_score(extracted.h2_structure),
        _field_score(extracted.images_with_alt),
        1.0 if extracted.faq_items else 0.5,
    ]
    content_raw = sum(content_signals) / len(content_signals)
    content_score = content_raw * 25.0

    # ── Technical SEO (max 15) ────────────────────────────────────────────────
    tech_signals = [
        _field_score(extracted.https),
        _field_score(extracted.mobile_viewport),
        _field_score(extracted.canonical_tag),
        _field_score(extracted.schema_markup),
        _field_score(extracted.page_load_time),
    ]
    tech_raw = sum(tech_signals) / len(tech_signals)
    tech_score = tech_raw * 15.0

    # ── Conversion Signals (max 15) ───────────────────────────────────────────
    conversion_signals = [
        _field_score(extracted.phone_above_fold),
        1.0 if local_seo.phone_above_fold_mobile else 0.0,
        1.0 if local_seo.has_whatsapp else 0.0,
        1.0 if local_seo.has_response_time_claim else 0.0,
        1.0 if local_seo.has_free_inspection else 0.0,
    ]
    conversion_raw = sum(conversion_signals) / len(conversion_signals)
    conversion_score = conversion_raw * 15.0

    # ── On-Page Metadata (max 10) ─────────────────────────────────────────────
    meta_signals = [
        _field_score(extracted.meta_title),
        _field_score(extracted.meta_description),
        _field_score(extracted.internal_links),
    ]
    meta_raw = sum(meta_signals) / len(meta_signals)
    meta_score = meta_raw * 10.0

    # ── Competitor Gap (max 5) ───────────────────────────────────────────────
    # Will be updated by M9 (Competitor Intelligence)
    competitor_score = competitor_gap_score * 5.0

    return SixAxisScore(
        local_seo=round(local_seo_score, 1),
        content_quality=round(content_score, 1),
        technical_seo=round(tech_score, 1),
        conversion_signals=round(conversion_score, 1),
        on_page_metadata=round(meta_score, 1),
        competitor_gap=round(competitor_score, 1),
    )
