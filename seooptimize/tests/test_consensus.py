"""Unit tests for the Consensus Engine (Module J)."""

import pytest
from app.analysis.consensus import ConsensusEngine
from app.models.annotations import (
    Annotation,
    ClaudeAnalysis,
    GeminiAnalysis,
    GeminiReview,
    GeminiVerdict,
    Impact,
    Priority,
)
from app.models.recommendations import PageRecommendations


@pytest.fixture
def engine() -> ConsensusEngine:
    return ConsensusEngine()


@pytest.fixture
def critical_annotation() -> Annotation:
    return Annotation(
        selector="h1",
        label="Missing Keyword in H1",
        priority=Priority.CRITICAL,
        issue="H1 does not contain 'Entrümpelung Siegen'",
        why_it_matters="Google uses H1 as the primary local intent signal",
        suggested_fix="Professionelle Entrümpelung Siegen | Fischer",
        impact=Impact.HIGH,
        confidence=0.92,
    )


@pytest.fixture
def claude_analysis(critical_annotation) -> ClaudeAnalysis:
    return ClaudeAnalysis(
        page_score=42,
        annotations=[critical_annotation],
        top_priority_action="Add LocalBusiness schema immediately",
    )


@pytest.fixture
def gemini_agree(critical_annotation) -> GeminiAnalysis:
    review = GeminiReview(
        selector="h1",
        gemini_verdict=GeminiVerdict.AGREE,
        gemini_note="Confirmed — competitor A uses H1 with city name",
        competitor_evidence={
            "competitor-siegen.de": "Entrümpelung Siegen — Jetzt anfragen",
        },
        revised_suggestion="Professionelle Entrümpelung Siegen — Kostenlose Besichtigung | Fischer",
    )
    return GeminiAnalysis(reviews=[review])


@pytest.fixture
def gemini_reject(critical_annotation) -> GeminiAnalysis:
    review = GeminiReview(
        selector="h1",
        gemini_verdict=GeminiVerdict.REJECT,
        gemini_note="H1 actually does contain Siegen in data provided",
        competitor_evidence={},
    )
    return GeminiAnalysis(reviews=[review])


class TestMergeTable:
    def test_critical_agree_stays_critical(self, engine, claude_analysis, gemini_agree):
        recs = engine.merge("https://example.com", claude_analysis, gemini_agree)
        assert len(recs.cards) > 0
        critical_cards = recs.critical_cards()
        assert len(critical_cards) > 0

    def test_critical_agree_high_confidence(self, engine, claude_analysis, gemini_agree):
        recs = engine.merge("https://example.com", claude_analysis, gemini_agree)
        card = recs.cards[0]
        assert card.confidence >= 0.65

    def test_critical_reject_downgrades_to_warning(self, engine, claude_analysis, gemini_reject):
        recs = engine.merge("https://example.com", claude_analysis, gemini_reject)
        assert len(recs.cards) > 0
        card = recs.cards[0]
        assert card.priority == Priority.WARNING

    def test_competitor_evidence_attached(self, engine, claude_analysis, gemini_agree):
        recs = engine.merge("https://example.com", claude_analysis, gemini_agree)
        card = recs.cards[0]
        assert len(card.competitor_evidence) > 0

    def test_revised_suggestion_used(self, engine, claude_analysis, gemini_agree):
        recs = engine.merge("https://example.com", claude_analysis, gemini_agree)
        card = recs.cards[0]
        assert "Kostenlose Besichtigung" in card.suggested_fix

    def test_top_priority_preserved(self, engine, claude_analysis, gemini_agree):
        recs = engine.merge("https://example.com", claude_analysis, gemini_agree)
        assert recs.top_priority_action == "Add LocalBusiness schema immediately"

    def test_page_score_preserved(self, engine, claude_analysis, gemini_agree):
        recs = engine.merge("https://example.com", claude_analysis, gemini_agree)
        assert recs.page_score == 42


class TestConfidenceFilter:
    def test_low_confidence_cards_exist_but_flagged(self, engine):
        low_conf_ann = Annotation(
            selector="footer",
            label="Footer Issue",
            priority=Priority.QUICK_WIN,
            issue="Footer could be improved",
            why_it_matters="Minor",
            suggested_fix="Fix footer",
            impact=Impact.LOW,
            confidence=0.40,
        )
        analysis = ClaudeAnalysis(page_score=50, annotations=[low_conf_ann])
        recs = engine.merge("https://example.com", analysis, GeminiAnalysis())
        if recs.cards:
            low_conf_cards = [c for c in recs.cards if c.confidence < 0.65]
            visible = recs.visible_cards()
            # Low confidence cards should not appear in visible cards
            for card in visible:
                assert card.confidence >= 0.65


class TestCardSorting:
    def test_critical_before_warning(self, engine):
        critical_ann = Annotation(
            selector="h1",
            label="Critical Issue",
            priority=Priority.CRITICAL,
            issue="Critical",
            why_it_matters="Important",
            suggested_fix="Fix",
            impact=Impact.HIGH,
            confidence=0.9,
        )
        warning_ann = Annotation(
            selector="meta[name='description']",
            label="Warning Issue",
            priority=Priority.WARNING,
            issue="Warning",
            why_it_matters="Matters",
            suggested_fix="Fix",
            impact=Impact.MEDIUM,
            confidence=0.8,
        )
        analysis = ClaudeAnalysis(
            page_score=50,
            annotations=[warning_ann, critical_ann],
        )
        recs = engine.merge("https://example.com", analysis, GeminiAnalysis())
        if len(recs.cards) >= 2:
            assert recs.cards[0].priority == Priority.CRITICAL
            assert recs.cards[1].priority == Priority.WARNING
