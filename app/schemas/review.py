"""Operator review workflow schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReviewOutcome(str, enum.Enum):
    ACCEPT = "accept"
    WARN = "warn"
    REJECT = "reject"
    ESCALATE = "escalate"
    REQUEST_MORE_EVIDENCE = "request_more_evidence"


class ReviewRequest(BaseModel):
    model_output_summary: dict[str, Any] = Field(default_factory=dict)
    validation_result_summary: dict[str, Any] = Field(default_factory=dict)
    evidence_bundle_id: uuid.UUID | None = None
    notes: str | None = None


class ReviewDecisionCreate(BaseModel):
    outcome: ReviewOutcome
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    reasoning: str = Field(..., min_length=1)
    business_impact_notes: str | None = None
    confidence_commentary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    reviewer_id: uuid.UUID
    outcome: ReviewOutcome
    confidence: float
    reasoning: str
    business_impact_notes: str | None
    confidence_commentary: str | None
    metadata: dict[str, Any]
    created_at: datetime


class ReviewerNoteCreate(BaseModel):
    note_type: str = Field(default="general", description="general, concern, suggestion, question")
    content: str = Field(..., min_length=1)
    references: list[uuid.UUID] = Field(
        default_factory=list, description="IDs of related artifacts/evidence"
    )


class ReviewerNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    reviewer_id: uuid.UUID
    note_type: str
    content: str
    references: list[uuid.UUID]
    created_at: datetime


class ReviewResponse(BaseModel):
    pilot_case_id: uuid.UUID
    model_output_summary: dict[str, Any]
    validation_result_summary: dict[str, Any]
    evidence_bundle_id: uuid.UUID | None
    decisions: list[ReviewDecisionResponse]
    notes: list[ReviewerNoteResponse]
    created_at: datetime


class ReviewSummary(BaseModel):
    pilot_case_id: uuid.UUID
    total_decisions: int
    latest_outcome: ReviewOutcome | None
    reviewer_id: uuid.UUID | None
    confidence: float | None
    has_notes: bool
    created_at: datetime | None
