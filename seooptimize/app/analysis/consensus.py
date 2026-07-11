"""Consensus Engine — Module J.

Merges Claude and Gemini outputs into final RecommendationCards.

Merge logic table (SEOArch.md §Module J):

    Claude verdict  | Gemini verdict      | Consensus
    critical        | agree               | Critical — high confidence
    critical        | reject              | Warning  — flag disagreement
    warning         | agree               | Warning
    warning         | strengthen          | Critical
    quick_win       | agree               | Quick Win
    ok              | ok                  | Passed — no action needed
    any             | adds evidence       | Attach competitor card

Only cards with final confidence >= 0.65 are shown by default.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.logging import get_logger
from app.models.annotations import (
    Annotation,
    ClaudeAnalysis,
    GeminiAnalysis,
    GeminiVerdict,
    Impact,
    Priority,
)
from app.models.recommendations import PageRecommendations, RecommendationCard

logger = get_logger(__name__)


class ConsensusEngine:
    """Merges Claude and Gemini outputs into final recommendation cards."""

    def merge(
        self,
        page_url: str,
        claude: ClaudeAnalysis,
        gemini: GeminiAnalysis,
    ) -> PageRecommendations:
        """Produce the final PageRecommendations from both AI outputs.

        Args:
            page_url: URL of the page being analysed.
            claude: Primary analysis from Claude.
            gemini: Independent review from Gemini.

        Returns:
            PageRecommendations with merged, confidence-scored cards.
        """
        # Build a lookup: selector → GeminiReview
        gemini_by_selector: dict[str, Any] = {
            r.selector: r for r in gemini.reviews
        }

        cards: list[RecommendationCard] = []

        # ── Process Claude annotations ─────────────────────────────────────
        for ann in claude.annotations:
            gemini_review = gemini_by_selector.get(ann.selector)

            # Determine final priority
            final_priority, agreement_level, confidence = self._merge_priority(
                ann, gemini_review
            )

            # Skip if consensus engine rejects (confidence 0 means hard reject)
            if confidence <= 0:
                continue

            # Merge suggestions
            suggested_fix = ann.suggested_fix
            if gemini_review and gemini_review.revised_suggestion:
                suggested_fix = gemini_review.revised_suggestion

            # Attach competitor evidence
            competitor_evidence: dict[str, str] = {}
            if gemini_review and gemini_review.competitor_evidence:
                competitor_evidence = gemini_review.competitor_evidence

            card = RecommendationCard(
                card_id=str(uuid.uuid4())[:8],
                page_url=page_url,
                priority=final_priority,
                impact=ann.impact,
                confidence=confidence,
                selector=ann.selector,
                label=ann.label,
                problem=ann.issue,
                why_it_matters=ann.why_it_matters,
                suggested_fix=suggested_fix,
                original_value="",
                competitor_evidence=competitor_evidence,
                expected_impact=self._generate_impact_statement(
                    final_priority, ann.impact
                ),
                agreement_level=agreement_level,
                gemini_note=(
                    gemini_review.gemini_note if gemini_review else ""
                ),
            )
            cards.append(card)

        # ── Add Gemini-only annotations (missed by Claude) ─────────────────
        claude_selectors = {ann.selector for ann in claude.annotations}
        for extra_ann in gemini.additional_annotations:
            if extra_ann.selector not in claude_selectors:
                card = RecommendationCard(
                    card_id=str(uuid.uuid4())[:8],
                    page_url=page_url,
                    priority=extra_ann.priority,
                    impact=extra_ann.impact,
                    confidence=extra_ann.confidence * 0.85,  # Slight discount for Gemini-only
                    selector=extra_ann.selector,
                    label=extra_ann.label,
                    problem=extra_ann.issue,
                    why_it_matters=extra_ann.why_it_matters,
                    suggested_fix=extra_ann.suggested_fix,
                    expected_impact=self._generate_impact_statement(
                        extra_ann.priority, extra_ann.impact
                    ),
                    agreement_level="gemini_only",
                    gemini_note="Finding identified by Gemini competitor analysis",
                )
                cards.append(card)

        # ── Sort by priority then confidence ─────────────────────────────────
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.WARNING: 1,
            Priority.QUICK_WIN: 2,
            Priority.OK: 3,
        }
        cards.sort(
            key=lambda c: (priority_order.get(c.priority, 9), -c.confidence)
        )

        logger.info(
            "Consensus complete for %s: %d cards (critical=%d, warning=%d, quick_win=%d)",
            page_url,
            len(cards),
            sum(1 for c in cards if c.priority == Priority.CRITICAL),
            sum(1 for c in cards if c.priority == Priority.WARNING),
            sum(1 for c in cards if c.priority == Priority.QUICK_WIN),
        )

        return PageRecommendations(
            page_url=page_url,
            page_score=claude.page_score,
            top_priority_action=claude.top_priority_action,
            cards=cards,
        )

    def _merge_priority(
        self,
        ann: Annotation,
        gemini_review: Any | None,
    ) -> tuple[Priority, str, float]:
        """Apply the Module J merge table.

        Returns:
            (final_priority, agreement_level, confidence)
        """
        claude_priority = ann.priority
        claude_confidence = ann.confidence

        if gemini_review is None:
            # No Gemini review — trust Claude directly
            return claude_priority, "claude_only", claude_confidence * 0.85

        verdict = gemini_review.gemini_verdict

        # Merge table
        if claude_priority == Priority.CRITICAL:
            if verdict == GeminiVerdict.AGREE:
                return Priority.CRITICAL, "full_agreement", min(1.0, claude_confidence * 1.1)
            elif verdict == GeminiVerdict.STRENGTHEN:
                return Priority.CRITICAL, "full_agreement", min(1.0, claude_confidence * 1.1)
            elif verdict == GeminiVerdict.REJECT:
                return Priority.WARNING, "disagreement", claude_confidence * 0.6
            else:  # ADD
                return Priority.CRITICAL, "partial", claude_confidence

        elif claude_priority == Priority.WARNING:
            if verdict == GeminiVerdict.AGREE:
                return Priority.WARNING, "full_agreement", min(1.0, claude_confidence * 1.05)
            elif verdict == GeminiVerdict.STRENGTHEN:
                return Priority.CRITICAL, "strengthened", min(1.0, claude_confidence * 1.15)
            elif verdict == GeminiVerdict.REJECT:
                return Priority.QUICK_WIN, "disagreement", claude_confidence * 0.55
            else:
                return Priority.WARNING, "partial", claude_confidence

        elif claude_priority == Priority.QUICK_WIN:
            if verdict in (GeminiVerdict.AGREE, GeminiVerdict.STRENGTHEN):
                return Priority.QUICK_WIN, "full_agreement", min(1.0, claude_confidence * 1.05)
            elif verdict == GeminiVerdict.REJECT:
                return Priority.OK, "disagreement", claude_confidence * 0.4
            else:
                return Priority.QUICK_WIN, "partial", claude_confidence

        else:  # OK
            if verdict == GeminiVerdict.AGREE:
                return Priority.OK, "full_agreement", claude_confidence
            elif verdict == GeminiVerdict.STRENGTHEN:
                return Priority.QUICK_WIN, "strengthened", claude_confidence
            else:
                return Priority.OK, "partial", claude_confidence

    @staticmethod
    def _generate_impact_statement(priority: Priority, impact: Impact) -> str:
        """Generate a human-readable expected impact statement."""
        impact_map = {
            (Priority.CRITICAL, Impact.HIGH): (
                "Estimated 25–40% improvement in local search ranking for primary service "
                "keyword within 4–8 weeks."
            ),
            (Priority.CRITICAL, Impact.MEDIUM): (
                "Estimated 15–25% improvement in local search visibility within 4–12 weeks."
            ),
            (Priority.CRITICAL, Impact.LOW): (
                "Important for compliance and user trust — indirect ranking benefit."
            ),
            (Priority.WARNING, Impact.HIGH): (
                "Estimated 10–20% improvement in organic click-through rate within 4–8 weeks."
            ),
            (Priority.WARNING, Impact.MEDIUM): (
                "Moderate improvement in page quality signals — benefit visible in 2–3 months."
            ),
            (Priority.QUICK_WIN, Impact.HIGH): (
                "High ROI: low effort change with meaningful visibility improvement within 2–4 weeks."
            ),
            (Priority.QUICK_WIN, Impact.MEDIUM): (
                "Quick improvement: can be implemented in under 1 hour, benefit within 2–4 weeks."
            ),
        }
        return impact_map.get(
            (priority, impact),
            "Improvement will contribute to overall SEO health and user experience.",
        )
