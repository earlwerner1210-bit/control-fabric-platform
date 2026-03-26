"""Extended baseline comparison schemas with rich comparison fields."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaselineMatchType(str, enum.Enum):
    EXACT_MATCH = "exact_match"
    PARTIAL_MATCH = "partial_match"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    USEFUL_BUT_NOT_CORRECT = "useful_but_not_correct"
    CORRECT_BUT_LOW_CONFIDENCE = "correct_but_low_confidence"
    UNRESOLVED = "unresolved"


class BaselineExpectationCreate(BaseModel):
    expected_outcome: str
    expected_confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    expected_reasoning: str | None = None
    expected_status: str | None = None
    expected_billability: str | None = None
    expected_next_action: str | None = None
    expected_owner: str | None = None
    expected_escalation: str | None = None
    expected_recovery_action: str | None = None
    expected_evidence_refs: list[str] = Field(default_factory=list)
    source: str | None = Field(None, description="human_expert, historical_decision, sme_panel")
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaselineExpectationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    expected_outcome: str
    expected_confidence: float
    expected_reasoning: str | None
    expected_status: str | None
    expected_billability: str | None
    expected_next_action: str | None
    expected_owner: str | None
    expected_escalation: str | None
    expected_recovery_action: str | None
    expected_evidence_refs: list[str]
    source: str | None
    metadata: dict[str, Any]
    created_at: datetime


class BaselineComparisonRequest(BaseModel):
    platform_outcome: str | None = None
    platform_status: str | None = None
    platform_confidence: float | None = None
    reviewer_outcome: str | None = None
    reviewer_status: str | None = None
    reviewer_confidence: float | None = None
    mismatch_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaselineComparisonResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    expected_outcome: str
    platform_outcome: str | None
    platform_status: str | None
    reviewer_outcome: str | None
    reviewer_status: str | None
    match_type: BaselineMatchType
    confidence_delta: float | None
    mismatch_reasons: list[str]
    notes: str | None
    metadata: dict[str, Any]
    created_at: datetime


class BaselineComparisonSummary(BaseModel):
    total_compared: int
    exact_matches: int
    partial_matches: int
    false_positives: int
    false_negatives: int
    useful_not_correct: int
    correct_low_confidence: int
    unresolved: int = 0
    accuracy_rate: float
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    by_workflow_type: dict[str, dict[str, int]] = Field(default_factory=dict)


class ReviewerVsPlatformComparison(BaseModel):
    pilot_case_id: uuid.UUID
    platform_outcome: str | None
    reviewer_outcome: str | None
    match_type: BaselineMatchType
    reviewer_confidence: float | None
    platform_confidence: float | None
    mismatch_reasons: list[str] = Field(default_factory=list)
