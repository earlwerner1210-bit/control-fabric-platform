"""KPI and pilot metrics schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KpiMeasurementCreate(BaseModel):
    metric_name: str
    metric_value: float
    metric_unit: str | None = None
    dimension: str | None = Field(None, description="workflow_type, reviewer, domain_pack, etc.")
    dimension_value: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KpiMeasurementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    metric_name: str
    metric_value: float
    metric_unit: str | None
    dimension: str | None
    dimension_value: str | None
    metadata: dict[str, Any]
    created_at: datetime


class PilotKpiSummary(BaseModel):
    total_cases: int = 0
    cases_by_state: dict[str, int] = Field(default_factory=dict)
    cases_by_workflow_type: dict[str, int] = Field(default_factory=dict)
    approval_rate: float = 0.0
    override_rate: float = 0.0
    escalation_rate: float = 0.0
    exact_match_rate: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    avg_evidence_completeness: float = 0.0
    avg_rule_confidence: float = 0.0
    avg_reviewer_confidence: float = 0.0
    avg_time_to_decision_hours: float = 0.0
    avg_time_to_review_hours: float = 0.0


class WorkflowKpiBreakdown(BaseModel):
    workflow_type: str
    total_cases: int
    approved: int
    overridden: int
    escalated: int
    rejected: int
    avg_confidence: float
    avg_evidence_completeness: float
    exact_match_rate: float
    false_positive_count: int
    false_negative_count: int
