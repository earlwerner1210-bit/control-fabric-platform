"""Tests for the review service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.review import (
    ReviewDecisionCreate,
    ReviewerNoteCreate,
    ReviewOutcome,
    ReviewRequest,
)
from app.services.review import ReviewService


@pytest.fixture
def svc() -> ReviewService:
    return ReviewService()


CASE_ID = uuid.uuid4()
REVIEWER = uuid.uuid4()


class TestCreateReview:
    def test_create_review(self, svc: ReviewService):
        data = ReviewRequest(
            model_output_summary={"verdict": "billable", "confidence": 0.92},
            validation_result_summary={"status": "passed", "rules": 8},
        )
        review = svc.create_review(CASE_ID, data)
        assert review.pilot_case_id == CASE_ID
        assert review.model_output_summary["verdict"] == "billable"
        assert review.decisions == []
        assert review.notes == []

    def test_create_review_with_evidence_bundle(self, svc: ReviewService):
        bundle_id = uuid.uuid4()
        data = ReviewRequest(evidence_bundle_id=bundle_id)
        review = svc.create_review(CASE_ID, data)
        assert review.evidence_bundle_id == bundle_id


class TestGetReview:
    def test_get_existing(self, svc: ReviewService):
        svc.create_review(CASE_ID, ReviewRequest())
        review = svc.get_review(CASE_ID)
        assert review is not None

    def test_get_missing(self, svc: ReviewService):
        assert svc.get_review(uuid.uuid4()) is None


class TestAddDecision:
    def test_accept_decision(self, svc: ReviewService):
        svc.create_review(CASE_ID, ReviewRequest())
        decision = svc.add_decision(
            CASE_ID,
            REVIEWER,
            ReviewDecisionCreate(
                outcome=ReviewOutcome.ACCEPT,
                reasoning="Correct billability determination",
                confidence=0.95,
            ),
        )
        assert decision.outcome == ReviewOutcome.ACCEPT
        assert decision.confidence == 0.95
        assert decision.reviewer_id == REVIEWER

    def test_reject_decision(self, svc: ReviewService):
        svc.create_review(CASE_ID, ReviewRequest())
        decision = svc.add_decision(
            CASE_ID,
            REVIEWER,
            ReviewDecisionCreate(
                outcome=ReviewOutcome.REJECT,
                reasoning="Incorrect scope determination",
                business_impact_notes="Would result in over-billing",
            ),
        )
        assert decision.outcome == ReviewOutcome.REJECT
        assert decision.business_impact_notes == "Would result in over-billing"

    def test_escalate_decision(self, svc: ReviewService):
        svc.create_review(CASE_ID, ReviewRequest())
        decision = svc.add_decision(
            CASE_ID,
            REVIEWER,
            ReviewDecisionCreate(
                outcome=ReviewOutcome.ESCALATE,
                reasoning="Requires commercial lead review",
            ),
        )
        assert decision.outcome == ReviewOutcome.ESCALATE

    def test_decision_on_missing_review(self, svc: ReviewService):
        with pytest.raises(ValueError, match="No review exists"):
            svc.add_decision(
                uuid.uuid4(),
                REVIEWER,
                ReviewDecisionCreate(outcome=ReviewOutcome.ACCEPT, reasoning="Test"),
            )

    def test_multiple_decisions(self, svc: ReviewService):
        svc.create_review(CASE_ID, ReviewRequest())
        svc.add_decision(
            CASE_ID,
            REVIEWER,
            ReviewDecisionCreate(outcome=ReviewOutcome.WARN, reasoning="Initial review"),
        )
        svc.add_decision(
            CASE_ID,
            REVIEWER,
            ReviewDecisionCreate(outcome=ReviewOutcome.ACCEPT, reasoning="After clarification"),
        )
        review = svc.get_review(CASE_ID)
        assert len(review.decisions) == 2


class TestAddNote:
    def test_add_general_note(self, svc: ReviewService):
        svc.create_review(CASE_ID, ReviewRequest())
        note = svc.add_note(
            CASE_ID,
            REVIEWER,
            ReviewerNoteCreate(content="Need to verify field completion date"),
        )
        assert note.content == "Need to verify field completion date"
        assert note.note_type == "general"

    def test_add_concern_note(self, svc: ReviewService):
        svc.create_review(CASE_ID, ReviewRequest())
        note = svc.add_note(
            CASE_ID,
            REVIEWER,
            ReviewerNoteCreate(
                note_type="concern",
                content="Rate card may be expired",
                references=[uuid.uuid4()],
            ),
        )
        assert note.note_type == "concern"
        assert len(note.references) == 1

    def test_note_on_missing_review(self, svc: ReviewService):
        with pytest.raises(ValueError, match="No review exists"):
            svc.add_note(uuid.uuid4(), REVIEWER, ReviewerNoteCreate(content="Test"))


class TestGetSummary:
    def test_summary_no_decisions(self, svc: ReviewService):
        svc.create_review(CASE_ID, ReviewRequest())
        summary = svc.get_summary(CASE_ID)
        assert summary.total_decisions == 0
        assert summary.latest_outcome is None

    def test_summary_with_decisions(self, svc: ReviewService):
        svc.create_review(CASE_ID, ReviewRequest())
        svc.add_decision(
            CASE_ID, REVIEWER, ReviewDecisionCreate(outcome=ReviewOutcome.WARN, reasoning="Initial")
        )
        svc.add_decision(
            CASE_ID, REVIEWER, ReviewDecisionCreate(outcome=ReviewOutcome.ACCEPT, reasoning="Final")
        )
        summary = svc.get_summary(CASE_ID)
        assert summary.total_decisions == 2
        assert summary.latest_outcome == ReviewOutcome.ACCEPT

    def test_summary_missing(self, svc: ReviewService):
        assert svc.get_summary(uuid.uuid4()) is None
