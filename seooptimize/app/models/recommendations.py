"""Recommendation card models — consensus output and UI state."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .annotations import Impact, Priority


class UserAction(str, Enum):
    """User's decision on a recommendation card."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited"


class RecommendationCard(BaseModel):
    """Fully merged recommendation as displayed in the UI (Module J output).

    Produced by the Consensus Engine from Claude + Gemini outputs.
    """

    # Identity
    card_id: str = Field(..., description="Unique identifier within a page analysis")
    page_url: str

    # Classification
    priority: Priority
    impact: Impact
    confidence: float = Field(..., ge=0.0, le=1.0)

    # Selector link for canvas overlay
    selector: str
    label: str

    # Content sections (maps to the card UI layout in SEOArch.md §5)
    problem: str
    why_it_matters: str
    suggested_fix: str
    original_value: str = ""

    # Competitor evidence (added by Gemini — positive gaps only)
    competitor_evidence: dict[str, str] = Field(default_factory=dict)

    # Expected impact statement (AI-generated narrative)
    expected_impact: str = ""

    # Agreement between Claude and Gemini
    agreement_level: str = ""   # "full_agreement" | "partial" | "disagreement"
    gemini_note: str = ""

    # User state
    user_action: UserAction = UserAction.PENDING
    user_edited_fix: str = ""

    @property
    def is_visible_by_default(self) -> bool:
        """Cards with confidence < 0.65 are hidden until the user toggles."""
        return self.confidence >= 0.65

    @property
    def display_fix(self) -> str:
        """Return user-edited fix if set, else the AI suggestion."""
        return self.user_edited_fix if self.user_edited_fix else self.suggested_fix


class PageRecommendations(BaseModel):
    """All recommendation cards for one page."""

    page_url: str
    page_score: int = Field(default=0, ge=0, le=100)
    top_priority_action: str = ""
    cards: list[RecommendationCard] = Field(default_factory=list)

    def critical_cards(self) -> list[RecommendationCard]:
        return [c for c in self.cards if c.priority == Priority.CRITICAL]

    def warning_cards(self) -> list[RecommendationCard]:
        return [c for c in self.cards if c.priority == Priority.WARNING]

    def quick_win_cards(self) -> list[RecommendationCard]:
        return [c for c in self.cards if c.priority == Priority.QUICK_WIN]

    def visible_cards(self) -> list[RecommendationCard]:
        return [c for c in self.cards if c.is_visible_by_default]
