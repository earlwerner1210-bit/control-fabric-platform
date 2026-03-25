"""Workflow-case and domain-specific workflow I/O schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shared.schemas.common import BaseSchema


# ── Enums ──────────────────────────────────────────────────────────────


class WorkflowStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class CaseVerdict(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"
    needs_review = "needs_review"
    escalated = "escalated"


class ReadinessVerdict(str, enum.Enum):
    ready = "ready"
    blocked = "blocked"
    warn = "warn"
    escalate = "escalate"


class MarginVerdict(str, enum.Enum):
    billable = "billable"
    non_billable = "non_billable"
    under_recovery = "under_recovery"
    penalty_risk = "penalty_risk"
    unknown = "unknown"


# ── Generic workflow case ──────────────────────────────────────────────


class WorkflowCaseCreate(BaseSchema):
    """Create a new workflow case."""

    workflow_type: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowCaseResponse(BaseSchema):
    """Returned workflow case."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    workflow_type: str
    status: WorkflowStatus
    verdict: CaseVerdict | None = None
    input_payload: dict[str, Any]
    output_payload: dict[str, Any] | None = None
    error_detail: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


# ── Contract Compile ───────────────────────────────────────────────────


class ContractCompileInput(BaseSchema):
    """Input for the contract-compile workflow."""

    document_id: uuid.UUID
    domain_pack: str = "contract-margin"
    extract_obligations: bool = True
    extract_penalties: bool = True
    extract_billing: bool = True


class ContractCompileOutput(BaseSchema):
    """Output of the contract-compile workflow."""

    document_id: uuid.UUID
    control_object_ids: list[uuid.UUID] = Field(default_factory=list)
    entity_ids: list[uuid.UUID] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str | None = None


# ── Work Order Readiness ───────────────────────────────────────────────


class WorkOrderReadinessInput(BaseSchema):
    """Input for work-order readiness check."""

    work_order_id: str
    control_object_ids: list[uuid.UUID] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    dispatch_region: str | None = None


class WorkOrderReadinessOutput(BaseSchema):
    """Output of the work-order readiness check."""

    work_order_id: str
    verdict: ReadinessVerdict
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)


# ── Incident Dispatch ─────────────────────────────────────────────────


class IncidentDispatchInput(BaseSchema):
    """Input for incident-dispatch workflow."""

    incident_id: str
    severity: int = Field(ge=1, le=5)
    category: str
    region: str | None = None
    description: str | None = None


class IncidentDispatchOutput(BaseSchema):
    """Output of the incident-dispatch workflow."""

    incident_id: str
    assigned_team: str | None = None
    escalation_level: int = 0
    recommended_actions: list[str] = Field(default_factory=list)
    sla_target_minutes: int | None = None


# ── Margin Diagnosis ──────────────────────────────────────────────────


class MarginDiagnosisInput(BaseSchema):
    """Input for margin-diagnosis workflow."""

    billing_record_id: str
    contract_id: uuid.UUID | None = None
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    period_start: datetime | None = None
    period_end: datetime | None = None


class MarginDiagnosisOutput(BaseSchema):
    """Output of the margin-diagnosis workflow."""

    billing_record_id: str
    verdict: MarginVerdict
    leakage_amount: float | None = None
    leakage_reasons: list[str] = Field(default_factory=list)
    matched_obligations: list[uuid.UUID] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
