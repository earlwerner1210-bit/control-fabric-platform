"""Reporting schemas for pilot proof layer."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PilotCaseReport(BaseModel):
    pilot_case_id: uuid.UUID
    title: str
    workflow_type: str
    state: str
    severity: str
    business_impact: str
    evidence_completeness: float = 0.0
    review_outcome: str | None = None
    reviewer_confidence: float | None = None
    approval_type: str | None = None
    override_reason: str | None = None
    escalation_route: str | None = None
    baseline_match_type: str | None = None
    kpi_measurements: list[dict[str, Any]] = Field(default_factory=list)
    feedback_count: int = 0
    timeline_events: int = 0
    created_at: datetime | None = None


class PilotSummaryReport(BaseModel):
    generated_at: datetime
    total_cases: int
    cases_by_state: dict[str, int] = Field(default_factory=dict)
    cases_by_workflow: dict[str, int] = Field(default_factory=dict)
    cases_by_severity: dict[str, int] = Field(default_factory=dict)
    approval_rate: float = 0.0
    override_rate: float = 0.0
    escalation_rate: float = 0.0
    avg_evidence_completeness: float = 0.0
    avg_reviewer_confidence: float = 0.0
    avg_time_to_decision_hours: float = 0.0


class WorkflowBreakdownReport(BaseModel):
    workflow_type: str
    total_cases: int
    approved: int = 0
    overridden: int = 0
    escalated: int = 0
    rejected: int = 0
    pending_review: int = 0
    avg_confidence: float = 0.0
    avg_evidence_completeness: float = 0.0
    exact_match_rate: float = 0.0
    false_positive_count: int = 0
    false_negative_count: int = 0
    avg_time_to_decision_hours: float = 0.0


class OverrideEscalationReport(BaseModel):
    generated_at: datetime
    total_overrides: int = 0
    total_escalations: int = 0
    overrides_by_reason: dict[str, int] = Field(default_factory=dict)
    escalations_by_route: dict[str, int] = Field(default_factory=dict)
    override_cases: list[dict[str, Any]] = Field(default_factory=list)
    escalation_cases: list[dict[str, Any]] = Field(default_factory=list)
    override_rate: float = 0.0
    escalation_rate: float = 0.0


class BaselineComparisonReport(BaseModel):
    generated_at: datetime
    total_compared: int
    exact_matches: int = 0
    partial_matches: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    useful_not_correct: int = 0
    accuracy_rate: float = 0.0
    by_workflow_type: dict[str, dict[str, int]] = Field(default_factory=dict)
    worst_performing_workflows: list[str] = Field(default_factory=list)
    best_performing_workflows: list[str] = Field(default_factory=list)


class ReviewerKpiBreakdown(BaseModel):
    reviewer_id: uuid.UUID
    total_reviews: int = 0
    accepted: int = 0
    rejected: int = 0
    escalated: int = 0
    avg_confidence: float = 0.0
    avg_time_to_review_hours: float = 0.0
    override_count: int = 0
    agreement_rate: float = 0.0


class PilotReportSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_type: str
    title: str
    total_cases: int
    cases_by_state: dict[str, int]
    cases_by_workflow: dict[str, int]
    kpi_summary: dict[str, Any]
    baseline_summary: dict[str, Any]
    feedback_summary: dict[str, Any]
    content: dict[str, Any]
    created_at: datetime
