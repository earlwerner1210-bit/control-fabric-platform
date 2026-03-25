"""Workflow input/output schemas for all four workflows."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema


# ── Enums ──────────────────────────────────────────────────────────


class WorkflowStatusEnum(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class CaseVerdictEnum(str, enum.Enum):
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


# ── Case ───────────────────────────────────────────────────────────


class WorkflowCaseCreate(BaseSchema):
    workflow_type: str
    input_payload: dict


class WorkflowCaseResponse(BaseSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    workflow_type: str
    status: WorkflowStatusEnum
    verdict: CaseVerdictEnum | None = None
    input_payload: dict
    output_payload: dict | None = None
    error_message: str | None = None
    temporal_workflow_id: str | None = None
    created_at: datetime
    updated_at: datetime


# ── 1. Contract Compile ────────────────────────────────────────────


class ContractCompileInput(BaseSchema):
    contract_document_id: uuid.UUID
    annexure_document_ids: list[uuid.UUID] = []
    sla_document_ids: list[uuid.UUID] = []
    rate_card_document_ids: list[uuid.UUID] = []


class ContractCompileOutput(BaseSchema):
    case_id: uuid.UUID
    status: str
    contract_summary: dict | None = None
    obligation_count: int = 0
    penalty_count: int = 0
    billable_event_count: int = 0
    control_object_ids: list[uuid.UUID] = []
    validation_status: str | None = None
    errors: list[str] = []


# ── 2. Work Order Readiness ────────────────────────────────────────


class WorkOrderReadinessInput(BaseSchema):
    work_order_document_id: uuid.UUID
    engineer_profile_document_id: uuid.UUID
    permit_document_ids: list[uuid.UUID] = []
    linked_contract_id: uuid.UUID | None = None


class WorkOrderReadinessOutput(BaseSchema):
    case_id: uuid.UUID
    verdict: ReadinessVerdict
    reasons: list[str] = []
    missing_prerequisites: list[str] = []
    skill_fit_summary: str | None = None
    compliance_blockers: list[str] = []
    evidence_ids: list[uuid.UUID] = []
    recommended_next_action: str | None = None
    explanation: str | None = None


# ── 3. Incident-Dispatch Reconciliation ────────────────────────────


class IncidentDispatchInput(BaseSchema):
    incident_document_id: uuid.UUID
    runbook_document_id: uuid.UUID | None = None
    work_order_document_id: uuid.UUID | None = None
    service_state_payload: dict | None = None


class IncidentDispatchOutput(BaseSchema):
    case_id: uuid.UUID
    next_action: str
    owner: str | None = None
    dispatch_required: bool = False
    rationale: str | None = None
    escalation_level: str | None = None
    escalation_reason: str | None = None
    evidence_ids: list[uuid.UUID] = []
    service_state_explanation: str | None = None


# ── 4. Margin Diagnosis ────────────────────────────────────────────


class MarginDiagnosisInput(BaseSchema):
    contract_document_id: uuid.UUID | None = None
    contract_case_id: uuid.UUID | None = None
    work_order_document_id: uuid.UUID | None = None
    incident_document_id: uuid.UUID | None = None
    execution_history: dict | None = None


class MarginDiagnosisOutput(BaseSchema):
    case_id: uuid.UUID
    verdict: MarginVerdict
    leakage_drivers: list[str] = []
    recovery_recommendations: list[str] = []
    evidence_object_ids: list[uuid.UUID] = []
    executive_summary: str | None = None
    billability_details: dict | None = None
    penalty_exposure: dict | None = None
