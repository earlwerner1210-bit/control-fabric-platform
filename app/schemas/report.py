"""Export and reporting schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExportFormat(str, enum.Enum):
    JSON = "json"
    MARKDOWN = "markdown"
    STRUCTURED = "structured"


class CaseExportRequest(BaseModel):
    format: ExportFormat = ExportFormat.JSON
    include_evidence: bool = True
    include_review: bool = True
    include_kpis: bool = True
    include_feedback: bool = False
    include_baseline: bool = True


class CaseExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    format: ExportFormat
    exported_by: uuid.UUID
    content: dict[str, Any]
    created_at: datetime


class DecisionSummaryExport(BaseModel):
    pilot_case_id: uuid.UUID
    title: str
    workflow_type: str
    state: str
    platform_decision: dict[str, Any] = Field(default_factory=dict)
    review_outcome: str | None = None
    reviewer_reasoning: str | None = None
    final_outcome: str | None = None
    override_reason: str | None = None
    evidence_completeness: float = 0.0
    confidence: float = 0.0


class ReviewSummaryExport(BaseModel):
    pilot_case_id: uuid.UUID
    reviewer_id: uuid.UUID | None = None
    outcome: str | None = None
    confidence: float | None = None
    reasoning: str | None = None
    notes_count: int = 0
    time_to_review_hours: float | None = None


class PilotReportSummary(BaseModel):
    generated_at: datetime
    total_cases: int
    cases_by_state: dict[str, int] = Field(default_factory=dict)
    cases_by_workflow: dict[str, int] = Field(default_factory=dict)
    decision_summaries: list[DecisionSummaryExport] = Field(default_factory=list)
    review_summaries: list[ReviewSummaryExport] = Field(default_factory=list)
    kpi_summary: dict[str, Any] = Field(default_factory=dict)
    feedback_summary: dict[str, Any] = Field(default_factory=dict)


class BaselineExpectation(BaseModel):
    expected_outcome: str
    expected_confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    expected_reasoning: str | None = None
    source: str | None = Field(None, description="human_expert, historical_decision, sme_panel")
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaselineMatchType(str, enum.Enum):
    EXACT_MATCH = "exact_match"
    PARTIAL_MATCH = "partial_match"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    USEFUL_BUT_NOT_CORRECT = "useful_but_not_correct"
    CORRECT_BUT_LOW_CONFIDENCE = "correct_but_low_confidence"


class BaselineComparisonResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    expected_outcome: str
    platform_outcome: str | None
    reviewer_outcome: str | None
    match_type: BaselineMatchType
    confidence_delta: float | None
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
    accuracy_rate: float
