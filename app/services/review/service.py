"""Operator review workflow service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.review import (
    ReviewDecisionCreate,
    ReviewDecisionResponse,
    ReviewerNoteCreate,
    ReviewerNoteResponse,
    ReviewOutcome,
    ReviewRequest,
    ReviewResponse,
    ReviewSummary,
)


class ReviewService:
    """Manages operator review workflow for pilot cases."""

    def __init__(self) -> None:
        self._reviews: dict[uuid.UUID, dict[str, Any]] = {}
        self._decisions: dict[uuid.UUID, list[dict[str, Any]]] = {}
        self._notes: dict[uuid.UUID, list[dict[str, Any]]] = {}

    def create_review(
        self,
        pilot_case_id: uuid.UUID,
        data: ReviewRequest,
    ) -> ReviewResponse:
        now = datetime.now(UTC)
        review = {
            "pilot_case_id": pilot_case_id,
            "model_output_summary": data.model_output_summary,
            "validation_result_summary": data.validation_result_summary,
            "evidence_bundle_id": data.evidence_bundle_id,
            "created_at": now,
        }
        self._reviews[pilot_case_id] = review
        self._decisions.setdefault(pilot_case_id, [])
        self._notes.setdefault(pilot_case_id, [])

        return ReviewResponse(
            pilot_case_id=pilot_case_id,
            model_output_summary=data.model_output_summary,
            validation_result_summary=data.validation_result_summary,
            evidence_bundle_id=data.evidence_bundle_id,
            decisions=[],
            notes=[],
            created_at=now,
        )

    def get_review(self, pilot_case_id: uuid.UUID) -> ReviewResponse | None:
        review = self._reviews.get(pilot_case_id)
        if review is None:
            return None

        decisions = [
            ReviewDecisionResponse(**d)
            for d in self._decisions.get(pilot_case_id, [])
        ]
        notes = [
            ReviewerNoteResponse(**n)
            for n in self._notes.get(pilot_case_id, [])
        ]

        return ReviewResponse(
            pilot_case_id=pilot_case_id,
            model_output_summary=review["model_output_summary"],
            validation_result_summary=review["validation_result_summary"],
            evidence_bundle_id=review["evidence_bundle_id"],
            decisions=decisions,
            notes=notes,
            created_at=review["created_at"],
        )

    def add_decision(
        self,
        pilot_case_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        data: ReviewDecisionCreate,
    ) -> ReviewDecisionResponse:
        if pilot_case_id not in self._reviews:
            raise ValueError(f"No review exists for case {pilot_case_id}")

        decision = {
            "id": uuid.uuid4(),
            "pilot_case_id": pilot_case_id,
            "reviewer_id": reviewer_id,
            "outcome": data.outcome,
            "confidence": data.confidence,
            "reasoning": data.reasoning,
            "business_impact_notes": data.business_impact_notes,
            "confidence_commentary": data.confidence_commentary,
            "metadata": data.metadata,
            "created_at": datetime.now(UTC),
        }
        self._decisions.setdefault(pilot_case_id, []).append(decision)
        return ReviewDecisionResponse(**decision)

    def add_note(
        self,
        pilot_case_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        data: ReviewerNoteCreate,
    ) -> ReviewerNoteResponse:
        if pilot_case_id not in self._reviews:
            raise ValueError(f"No review exists for case {pilot_case_id}")

        note = {
            "id": uuid.uuid4(),
            "pilot_case_id": pilot_case_id,
            "reviewer_id": reviewer_id,
            "note_type": data.note_type,
            "content": data.content,
            "references": [str(r) for r in data.references],
            "created_at": datetime.now(UTC),
        }
        self._notes.setdefault(pilot_case_id, []).append(note)
        return ReviewerNoteResponse(**note)

    def get_summary(self, pilot_case_id: uuid.UUID) -> ReviewSummary | None:
        review = self._reviews.get(pilot_case_id)
        if review is None:
            return None

        decisions = self._decisions.get(pilot_case_id, [])
        latest = decisions[-1] if decisions else None

        return ReviewSummary(
            pilot_case_id=pilot_case_id,
            total_decisions=len(decisions),
            latest_outcome=ReviewOutcome(latest["outcome"]) if latest else None,
            reviewer_id=latest["reviewer_id"] if latest else None,
            confidence=latest["confidence"] if latest else None,
            has_notes=len(self._notes.get(pilot_case_id, [])) > 0,
            created_at=review["created_at"],
        )
