"""Data models package."""

from .annotations import (
    Annotation,
    ClaudeAnalysis,
    GeminiAnalysis,
    GeminiReview,
    GeminiVerdict,
    Impact,
    Priority,
)
from .page import (
    BoundingBox,
    ExtractionResult,
    FieldScore,
    LocalSEOResult,
    PageData,
    ScoreStatus,
    SixAxisScore,
)
from .project import BusinessCategory, CATEGORY_LABELS, ProjectConfig
from .recommendations import PageRecommendations, RecommendationCard, UserAction

__all__ = [
    "Annotation",
    "BoundingBox",
    "BusinessCategory",
    "CATEGORY_LABELS",
    "ClaudeAnalysis",
    "ExtractionResult",
    "FieldScore",
    "GeminiAnalysis",
    "GeminiReview",
    "GeminiVerdict",
    "Impact",
    "LocalSEOResult",
    "PageData",
    "PageRecommendations",
    "Priority",
    "ProjectConfig",
    "RecommendationCard",
    "ScoreStatus",
    "SixAxisScore",
    "UserAction",
]
