"""Reconciliation value types — mismatch categories, scoring, evidence bundles."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.types import (
    ConfidenceScore,
    ControlObjectId,
    EvidenceRef,
    PlaneType,
    deterministic_hash,
)


class MismatchCategory(str, enum.Enum):
    """Categories of cross-plane mismatch detected during reconciliation."""

    RATE_DEVIATION = "rate_deviation"
    SCOPE_MISMATCH = "scope_mismatch"
    QUANTITY_DISCREPANCY = "quantity_discrepancy"
    DATE_DISCREPANCY = "date_discrepancy"
    OBLIGATION_UNMET = "obligation_unmet"
    PENALTY_TRIGGERED = "penalty_triggered"
    DUPLICATE_CHARGE = "duplicate_charge"
    MISSING_EVIDENCE = "missing_evidence"
    SLA_BREACH = "sla_breach"
    WORK_NOT_COMPLETED = "work_not_completed"
    BILLING_WITHOUT_COMPLETION = "billing_without_completion"
    SCOPE_CREEP = "scope_creep"
    CONTRADICTORY_STATE = "contradictory_state"
    PROVENANCE_GAP = "provenance_gap"


class MismatchSeverity(str, enum.Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReconciliationMode(str, enum.Enum):
    DETERMINISTIC = "deterministic"
    ASSISTED = "assisted"


class ReconciliationStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DISPUTED = "disputed"


class Mismatch(BaseModel):
    """A single mismatch found during reconciliation."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    category: MismatchCategory
    severity: MismatchSeverity
    source_object_id: ControlObjectId
    target_object_id: ControlObjectId
    source_plane: PlaneType
    target_plane: PlaneType
    description: str
    expected_value: Any = None
    actual_value: Any = None
    deviation: float | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    rule_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def financial_impact(self) -> float:
        return self.metadata.get("financial_impact", 0.0)


class EvidenceBundle(BaseModel):
    """A bundle of evidence supporting a reconciliation finding."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    mismatches: list[Mismatch] = Field(default_factory=list)
    supporting_evidence: list[EvidenceRef] = Field(default_factory=list)
    source_objects: list[ControlObjectId] = Field(default_factory=list)
    target_objects: list[ControlObjectId] = Field(default_factory=list)
    summary: str = ""

    @property
    def mismatch_count(self) -> int:
        return len(self.mismatches)

    @property
    def total_evidence(self) -> int:
        return len(self.supporting_evidence) + sum(len(m.evidence) for m in self.mismatches)


class ReconciliationScore(BaseModel):
    """Quantified score for a reconciliation result."""

    overall_score: float = Field(ge=0.0, le=1.0)
    confidence: ConfidenceScore = ConfidenceScore(1.0)
    mismatch_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    financial_impact_total: float = 0.0

    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0

    @property
    def is_clean(self) -> bool:
        return self.mismatch_count == 0


class ReconciliationResult(BaseModel):
    """Full result of a reconciliation run."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    run_at: datetime
    status: ReconciliationStatus = ReconciliationStatus.COMPLETED
    mode: ReconciliationMode = ReconciliationMode.DETERMINISTIC
    source_plane: PlaneType
    target_plane: PlaneType
    domain: str
    evidence_bundle: EvidenceBundle = Field(default_factory=EvidenceBundle)
    score: ReconciliationScore = Field(
        default_factory=lambda: ReconciliationScore(overall_score=1.0)
    )
    decision_hash: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_hash(self) -> str:
        data = {
            "tenant_id": str(self.tenant_id),
            "source_plane": self.source_plane.value,
            "target_plane": self.target_plane.value,
            "domain": self.domain,
            "mismatches": [
                {
                    "category": m.category.value,
                    "source_object_id": str(m.source_object_id),
                    "target_object_id": str(m.target_object_id),
                    "expected_value": str(m.expected_value),
                    "actual_value": str(m.actual_value),
                }
                for m in self.evidence_bundle.mismatches
            ],
        }
        self.decision_hash = deterministic_hash(data)
        return self.decision_hash
