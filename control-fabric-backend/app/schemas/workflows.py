"""Workflow case, input/output, and verdict schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema

# ── Enums ─────────────────────────────────────────────────────────────────


class WorkflowStatusEnum(StrEnum):
    """Lifecycle states of a workflow case."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CaseVerdictEnum(StrEnum):
    """High-level outcome verdicts for a completed workflow case."""

    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    ESCALATED = "escalated"


class ReadinessVerdict(StrEnum):
    """Readiness check outcome."""

    READY = "ready"
    BLOCKED = "blocked"
    WARN = "warn"
    ESCALATE = "escalate"


class MarginVerdict(StrEnum):
    """Margin reconciliation outcome for a billable item."""

    BILLABLE = "billable"
    NON_BILLABLE = "non_billable"
    UNDER_RECOVERY = "under_recovery"
    PENALTY_RISK = "penalty_risk"
    UNKNOWN = "unknown"


class ValidationStatus(StrEnum):
    """Aggregate validation outcome."""

    APPROVED = "approved"
    WARN = "warn"
    BLOCKED = "blocked"
    ESCALATE = "escalate"


# ── Contract-Compile workflow ─────────────────────────────────────────────


class ContractCompileInput(BaseSchema):
    """Input payload for the contract-compile workflow."""

    contract_document_id: UUID
    sla_document_ids: list[UUID] = Field(default_factory=list)
    rate_card_document_ids: list[UUID] = Field(default_factory=list)


class ContractCompileOutput(BaseSchema):
    """Output payload for a completed contract-compile workflow."""

    case_id: UUID
    status: WorkflowStatusEnum
    contract_summary: str | None = None
    obligation_count: int = Field(default=0, ge=0)
    penalty_count: int = Field(default=0, ge=0)
    billable_event_count: int = Field(default=0, ge=0)
    control_object_ids: list[UUID] = Field(default_factory=list)
    validation_status: ValidationStatus | None = None
    errors: list[str] = Field(default_factory=list)


# ── Margin-Diagnosis workflow ─────────────────────────────────────────────


class MarginDiagnosisInput(BaseSchema):
    """Input payload for the margin-diagnosis workflow."""

    contract_document_id: UUID
    contract_case_id: UUID | None = None
    work_order_document_id: UUID | None = None
    incident_document_id: UUID | None = None
    execution_history: list[dict[str, Any]] = Field(default_factory=list)


class MarginDiagnosisOutput(BaseSchema):
    """Output payload for a completed margin-diagnosis workflow."""

    case_id: UUID
    verdict: MarginVerdict
    leakage_drivers: list[str] = Field(default_factory=list)
    recovery_recommendations: list[str] = Field(default_factory=list)
    evidence_object_ids: list[UUID] = Field(default_factory=list)
    executive_summary: str | None = None
    billability_details: dict[str, Any] = Field(default_factory=dict)
    penalty_exposure: dict[str, Any] = Field(default_factory=dict)


# ── Generic workflow case ─────────────────────────────────────────────────


class WorkflowCaseCreate(BaseSchema):
    """Payload for creating a new workflow case."""

    workflow_type: str = Field(
        ...,
        examples=["contract_compile", "margin_diagnosis"],
    )
    input_payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowCaseResponse(BaseSchema):
    """Persisted workflow case."""

    id: UUID
    tenant_id: UUID
    workflow_type: str
    status: WorkflowStatusEnum
    verdict: CaseVerdictEnum | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
