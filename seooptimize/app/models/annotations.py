"""Annotation and AI analysis models — Claude and Gemini outputs."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Priority(str, Enum):
    """SEO finding priority level."""

    CRITICAL = "critical"
    WARNING = "warning"
    QUICK_WIN = "quick_win"
    OK = "ok"


class Impact(str, Enum):
    """Estimated SEO impact of fixing a finding."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GeminiVerdict(str, Enum):
    """Gemini's verdict on a Claude annotation."""

    AGREE = "agree"
    STRENGTHEN = "strengthen"
    REJECT = "reject"
    ADD = "add"


class Annotation(BaseModel):
    """Single SEO finding returned by Claude (Module H).

    Matches the JSON schema defined in SEOArch.md §Module H.
    """

    selector: str = Field(..., description="CSS selector of the affected element")
    label: str = Field(..., max_length=40, description="Short badge text (max 4 words)")
    priority: Priority
    issue: str = Field(..., description="What is wrong")
    why_it_matters: str = Field(..., description="Business-language explanation")
    suggested_fix: str = Field(..., description="Exact replacement text or instruction")
    impact: Impact
    confidence: float = Field(..., ge=0.0, le=1.0)


class GeminiReview(BaseModel):
    """Gemini's review of one Claude annotation (Module I).

    Matches the JSON schema defined in SEOArch.md §Module I.
    """

    selector: str
    gemini_verdict: GeminiVerdict
    gemini_note: str = ""
    competitor_evidence: dict[str, str] = Field(
        default_factory=dict,
        description="competitor_name → their H1 / meta / etc.",
    )
    revised_suggestion: str = ""


class ClaudeAnalysis(BaseModel):
    """Complete response from Claude for one page (Module H)."""

    page_score: int = Field(..., ge=0, le=100)
    annotations: list[Annotation] = Field(default_factory=list)
    top_priority_action: str = ""
    raw_response: str = ""


class GeminiAnalysis(BaseModel):
    """Complete response from Gemini for one page (Module I)."""

    reviews: list[GeminiReview] = Field(default_factory=list)
    additional_annotations: list[Annotation] = Field(default_factory=list)
    raw_response: str = ""
