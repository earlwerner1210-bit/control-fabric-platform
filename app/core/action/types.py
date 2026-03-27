"""Action engine value types — manifests, eligibility, release modes."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.types import (
    ActionEligibility,
    ConfidenceScore,
    ControlObjectId,
    EvidenceRef,
    deterministic_hash,
)
from app.core.validation.types import ValidationChainResult


class ActionType(str, enum.Enum):
    CREDIT_NOTE = "credit_note"
    INVOICE_ADJUSTMENT = "invoice_adjustment"
    PENALTY_CHARGE = "penalty_charge"
    SLA_ESCALATION = "sla_escalation"
    WORK_ORDER_DISPATCH = "work_order_dispatch"
    BILLING_HOLD = "billing_hold"
    RATE_CORRECTION = "rate_correction"
    RECOVERY_RECOMMENDATION = "recovery_recommendation"
    DISPUTE_FILING = "dispute_filing"
    CUSTOM = "custom"


class ActionMode(str, enum.Enum):
    DRY_RUN = "dry_run"
    APPROVAL_GATED = "approval_gated"
    AUTO_RELEASE = "auto_release"


class ActionStatus(str, enum.Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    RELEASED = "released"
    EXECUTED = "executed"
    REJECTED = "rejected"
    FAILED = "failed"
    DRY_RUN_COMPLETE = "dry_run_complete"


class ActionManifest(BaseModel):
    """Reproducible manifest for an action — all inputs, evidence, and decisions."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    action_type: ActionType
    target_object_ids: list[ControlObjectId] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    validation_result_id: uuid.UUID | None = None
    reasoning_result_id: uuid.UUID | None = None
    reconciliation_result_id: uuid.UUID | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    decision_hash: str = ""

    def compute_hash(self) -> str:
        data = {
            "action_type": self.action_type.value,
            "target_object_ids": sorted(str(oid) for oid in self.target_object_ids),
            "evidence_refs": sorted(str(e.evidence_id) for e in self.evidence_refs),
            "parameters": self.parameters,
        }
        self.decision_hash = deterministic_hash(data)
        return self.decision_hash


class ActionProposal(BaseModel):
    """A proposed action with full traceability."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    action_type: ActionType
    mode: ActionMode = ActionMode.APPROVAL_GATED
    status: ActionStatus = ActionStatus.PROPOSED
    manifest: ActionManifest
    validation_result: ValidationChainResult | None = None
    eligibility: ActionEligibility = ActionEligibility.PENDING_VALIDATION
    description: str = ""
    financial_impact: float = 0.0
    confidence: ConfidenceScore = ConfidenceScore(1.0)
    created_at: datetime | None = None
    released_at: datetime | None = None
    approved_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_releasable(self) -> bool:
        if self.status == ActionStatus.REJECTED:
            return False
        if self.eligibility != ActionEligibility.ELIGIBLE:
            return False
        if self.mode == ActionMode.APPROVAL_GATED:
            return self.status == ActionStatus.APPROVED
        if self.mode == ActionMode.AUTO_RELEASE:
            return self.status == ActionStatus.VALIDATED
        if self.mode == ActionMode.DRY_RUN:
            return False
        return False
