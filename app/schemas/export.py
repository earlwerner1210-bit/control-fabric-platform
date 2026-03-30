"""Extended export schemas."""

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


class ExportType(str, enum.Enum):
    CASE_SUMMARY = "case_summary"
    DECISION_SUMMARY = "decision_summary"
    REVIEW_SUMMARY = "review_summary"
    MARGIN_DIAGNOSIS = "margin_diagnosis"
    WORK_ORDER_READINESS = "work_order_readiness"
    INCIDENT_RECONCILIATION = "incident_reconciliation"
    PILOT_KPI = "pilot_kpi"
    PILOT_REPORT = "pilot_report"


class CaseExportRequest(BaseModel):
    format: ExportFormat = ExportFormat.JSON
    export_type: ExportType = ExportType.CASE_SUMMARY
    include_evidence: bool = True
    include_review: bool = True
    include_kpis: bool = True
    include_feedback: bool = False
    include_baseline: bool = True
    include_audit_trail: bool = False
    include_model_lineage: bool = False


class CaseExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    format: ExportFormat
    export_type: ExportType
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
    escalation_route: str | None = None
    evidence_completeness: float = 0.0
    confidence: float = 0.0
    baseline_match_type: str | None = None


class ReviewSummaryExport(BaseModel):
    pilot_case_id: uuid.UUID
    reviewer_id: uuid.UUID | None = None
    outcome: str | None = None
    confidence: float | None = None
    reasoning: str | None = None
    notes_count: int = 0
    override_reason: str | None = None
    escalation_route: str | None = None
    time_to_review_hours: float | None = None


class PilotReportExport(BaseModel):
    generated_at: datetime
    report_type: str
    title: str
    total_cases: int
    cases_by_state: dict[str, int] = Field(default_factory=dict)
    cases_by_workflow: dict[str, int] = Field(default_factory=dict)
    decision_summaries: list[DecisionSummaryExport] = Field(default_factory=list)
    review_summaries: list[ReviewSummaryExport] = Field(default_factory=list)
    kpi_summary: dict[str, Any] = Field(default_factory=dict)
    baseline_summary: dict[str, Any] = Field(default_factory=dict)
    feedback_summary: dict[str, Any] = Field(default_factory=dict)
    override_summary: dict[str, Any] = Field(default_factory=dict)
    escalation_summary: dict[str, Any] = Field(default_factory=dict)
