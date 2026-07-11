"""Page-level data models — extraction results, bounding boxes, scoring."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ScoreStatus(str, Enum):
    """Deterministic field score as specified in Module D."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NA = "na"


class BoundingBox(BaseModel):
    """Pixel coordinates of a DOM element within the full-page screenshot.

    Captured via ``playwright.locator(selector).first.bounding_box()``.
    """

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def as_rect(self) -> tuple[float, float, float, float]:
        """Return (x, y, x+w, y+h) — PIL rectangle format."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)


class FieldScore(BaseModel):
    """Score + raw value for a single extracted field."""

    status: ScoreStatus
    value: Any = None
    note: str = ""


class ExtractionResult(BaseModel):
    """All deterministic fields extracted from one page (Module D)."""

    meta_title: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    meta_description: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    h1: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    h2_structure: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    word_count: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    images_with_alt: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    phone_above_fold: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    schema_markup: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    canonical_tag: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    mobile_viewport: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    nap_on_page: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    internal_links: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    page_load_time: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))
    https: FieldScore = Field(default_factory=lambda: FieldScore(status=ScoreStatus.NA))

    # Extra extracted data used downstream (not scored individually)
    all_headings: list[dict[str, str]] = Field(default_factory=list)
    all_links: list[dict[str, str]] = Field(default_factory=list)
    all_images: list[dict[str, str]] = Field(default_factory=list)
    schema_objects: list[dict[str, Any]] = Field(default_factory=list)
    faq_items: list[dict[str, str]] = Field(default_factory=list)
    raw_text: str = ""

    def pass_count(self) -> int:
        return sum(1 for f in self._scored_fields() if f.status == ScoreStatus.PASS)

    def warn_count(self) -> int:
        return sum(1 for f in self._scored_fields() if f.status == ScoreStatus.WARN)

    def fail_count(self) -> int:
        return sum(1 for f in self._scored_fields() if f.status == ScoreStatus.FAIL)

    def _scored_fields(self) -> list[FieldScore]:
        return [
            self.meta_title, self.meta_description, self.h1, self.h2_structure,
            self.word_count, self.images_with_alt, self.phone_above_fold,
            self.schema_markup, self.canonical_tag, self.mobile_viewport,
            self.nap_on_page, self.internal_links, self.page_load_time, self.https,
        ]


class LocalSEOResult(BaseModel):
    """Output from Module E — Local SEO Analysis."""

    nap_consistent: bool = False
    nap_name: str = ""
    nap_address: str = ""
    nap_phone: str = ""
    nap_issues: list[str] = Field(default_factory=list)

    has_local_business_schema: bool = False
    schema_missing_fields: list[str] = Field(default_factory=list)
    suggested_schema: dict[str, Any] = Field(default_factory=dict)

    city_in_title: bool = False
    city_in_h1: bool = False
    city_mention_count: int = 0
    missing_service_area_pages: list[str] = Field(default_factory=list)

    has_review_signals: bool = False
    has_review_schema: bool = False

    # Urgency / trust signals
    phone_above_fold_mobile: bool = False
    has_whatsapp: bool = False
    has_response_time_claim: bool = False
    has_free_inspection: bool = False
    has_insurance_badge: bool = False
    has_photo_gallery: bool = False

    urgency_score: float = 0.0  # 0.0–1.0


class SixAxisScore(BaseModel):
    """Six-axis weighted score for one page or the site overall."""

    local_seo: float = Field(default=0.0, ge=0.0, le=30.0)
    content_quality: float = Field(default=0.0, ge=0.0, le=25.0)
    technical_seo: float = Field(default=0.0, ge=0.0, le=15.0)
    conversion_signals: float = Field(default=0.0, ge=0.0, le=15.0)
    on_page_metadata: float = Field(default=0.0, ge=0.0, le=10.0)
    competitor_gap: float = Field(default=0.0, ge=0.0, le=5.0)

    @property
    def total(self) -> float:
        return (
            self.local_seo
            + self.content_quality
            + self.technical_seo
            + self.conversion_signals
            + self.on_page_metadata
            + self.competitor_gap
        )

    def as_dict(self) -> dict[str, float]:
        return {
            "Local SEO": self.local_seo,
            "Content Quality": self.content_quality,
            "Technical SEO": self.technical_seo,
            "Conversion Signals": self.conversion_signals,
            "On-Page Metadata": self.on_page_metadata,
            "Competitor Gap": self.competitor_gap,
        }


class PageData(BaseModel):
    """Complete data record for one crawled and analysed page.

    This is the primary unit stored in the knowledge cache (Module F).
    """

    url: str
    title: str = ""
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    content_hash: str = ""

    # Screenshot paths (relative to cache dir)
    screenshot_path: str = ""
    mobile_screenshot_path: str = ""

    # Playwright bounding boxes: CSS selector → BoundingBox
    element_boxes: dict[str, BoundingBox] = Field(default_factory=dict)

    # Deterministic results
    extracted: ExtractionResult = Field(default_factory=ExtractionResult)
    local_seo: LocalSEOResult = Field(default_factory=LocalSEOResult)
    scores: SixAxisScore = Field(default_factory=SixAxisScore)

    # AI results (populated after AI pipeline)
    ai_analysis: dict[str, Any] = Field(default_factory=dict)

    # Analysis state flags
    extraction_complete: bool = False
    ai_complete: bool = False
    error: str = ""
