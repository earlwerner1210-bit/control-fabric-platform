"""Wave 3 action domain types — evidence-gated action release constructs."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any, NewType

from pydantic import BaseModel, Field

from app.core.types import (
    ConfidenceScore,
    ControlObjectId,
    EvidenceRef,
    deterministic_hash,
)
from app.core.validation.domain_types import (
    ValidationDecision,
    ValidationReportHash,
    ValidationRunId,
)

W3ActionId = NewType("W3ActionId", uuid.UUID)
W3ActionReleaseId = NewType("W3ActionReleaseId", uuid.UUID)


def new_action_id() -> W3ActionId:
    return W3ActionId(uuid.uuid4())


def new_release_id() -> W3ActionReleaseId:
    return W3ActionReleaseId(uuid.uuid4())


class W3ActionType(str, enum.Enum):
    CREDIT_NOTE = "credit-note"
    INVOICE_ADJUSTMENT = "invoice-adjustment"
    PENALTY_CHARGE = "penalty-charge"
    SLA_ESCALATION = "sla-escalation"
    WORK_ORDER_DISPATCH = "work-order-dispatch"
    BILLING_HOLD = "billing-hold"
    RATE_CORRECTION = "rate-correction"
    RECOVERY_RECOMMENDATION = "recovery-recommendation"


class W3ActionStatus(str, enum.Enum):
    PROPOSED = "proposed"
    VALIDATION_PENDING = "validation-pending"
    VALIDATED = "validated"
    PENDING_APPROVAL = "pending-approval"
    APPROVED = "approved"
    RELEASED = "released"
    REJECTED = "rejected"


class W3ActionExecutionMode(str, enum.Enum):
    DRY_RUN = "dry-run"
    APPROVAL_GATED = "approval-gated"
    DETERMINISTIC_AUTO_RELEASE = "deterministic-auto-release"


class W3ActionFailureCode(str, enum.Enum):
    VALIDATION_NOT_PASSED = "validation-not-passed"
    EVIDENCE_MISSING = "evidence-missing"
    APPROVAL_DENIED = "approval-denied"
    POLICY_BLOCKED = "policy-blocked"
    TARGET_NOT_ELIGIBLE = "target-not-eligible"
    HASH_MISMATCH = "hash-mismatch"


class W3ActionEvidenceManifest(BaseModel):
    """Evidence manifest attached to every action release."""

    action_id: W3ActionId
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    validation_run_id: ValidationRunId | None = None
    validation_decision: ValidationDecision | None = None
    report_hash: ValidationReportHash = ValidationReportHash("")
    target_object_ids: list[ControlObjectId] = Field(default_factory=list)
    manifest_hash: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def compute_hash(self) -> str:
        data = {
            "action_id": str(self.action_id),
            "evidence_refs": sorted(str(e.evidence_id) for e in self.evidence_refs),
            "validation_run_id": str(self.validation_run_id) if self.validation_run_id else "",
            "validation_decision": self.validation_decision.value if self.validation_decision else "",
            "report_hash": str(self.report_hash),
            "target_object_ids": sorted(str(oid) for oid in self.target_object_ids),
        }
        self.manifest_hash = deterministic_hash(data)
        return self.manifest_hash


class W3ActionProposal(BaseModel):
    """A proposed action with full evidence and validation gating."""

    id: W3ActionId = Field(default_factory=new_action_id)
    tenant_id: uuid.UUID
    action_type: W3ActionType
    execution_mode: W3ActionExecutionMode = W3ActionExecutionMode.APPROVAL_GATED
    status: W3ActionStatus = W3ActionStatus.PROPOSED
    target_object_ids: list[ControlObjectId] = Field(default_factory=list)
    validation_run_id: ValidationRunId | None = None
    validation_decision: ValidationDecision | None = None
    report_hash: ValidationReportHash = ValidationReportHash("")
    evidence_manifest: W3ActionEvidenceManifest | None = None
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: ConfidenceScore = ConfidenceScore(1.0)
    financial_impact: float = 0.0
    approved_by: str | None = None
    rejected_reason: str | None = None
    decision_hash: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    released_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_decision_hash(self) -> str:
        data = {
            "action_type": self.action_type.value,
            "target_object_ids": sorted(str(oid) for oid in self.target_object_ids),
            "validation_decision": self.validation_decision.value if self.validation_decision else "",
            "report_hash": str(self.report_hash),
            "parameters": self.parameters,
        }
        self.decision_hash = deterministic_hash(data)
        return self.decision_hash

    @property
    def is_releasable(self) -> bool:
        if self.status == W3ActionStatus.REJECTED:
            return False
        if self.validation_decision != ValidationDecision.ELIGIBLE:
            return False
        if self.execution_mode == W3ActionExecutionMode.DRY_RUN:
            return False
        if self.execution_mode == W3ActionExecutionMode.APPROVAL_GATED:
            return self.status == W3ActionStatus.APPROVED
        if self.execution_mode == W3ActionExecutionMode.DETERMINISTIC_AUTO_RELEASE:
            return self.status == W3ActionStatus.VALIDATED
        return False


class W3ActionRelease(BaseModel):
    """A released action with full traceability."""

    id: W3ActionReleaseId = Field(default_factory=new_release_id)
    action_id: W3ActionId
    tenant_id: uuid.UUID
    action_type: W3ActionType
    evidence_manifest: W3ActionEvidenceManifest
    decision_hash: str = ""
    released_by: str = "system"
    released_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class W3ActionPolicy(BaseModel):
    """Policy governing action release behavior."""

    require_validation_pass: bool = True
    require_evidence: bool = True
    min_evidence_count: int = 1
    require_report_hash: bool = True
    allowed_decisions_for_release: list[ValidationDecision] = Field(
        default_factory=lambda: [ValidationDecision.ELIGIBLE]
    )
    auto_release_on_eligible: bool = False
