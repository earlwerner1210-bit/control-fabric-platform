"""Validation chain value types — dimensions, verdicts, chain outcome."""

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
    ValidationStatus,
    deterministic_hash,
)


class ValidationDimension(str, enum.Enum):
    """The 10 validation dimensions every action must pass."""

    SCHEMA = "schema"
    GRAPH_COMPLETENESS = "graph_completeness"
    EVIDENCE_SUFFICIENCY = "evidence_sufficiency"
    PROVENANCE = "provenance"
    RECONCILIATION_STATE = "reconciliation_state"
    POLICY = "policy"
    DETERMINISM = "determinism"
    CONFIDENCE = "confidence"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    ACTION_PRECONDITIONS = "action_preconditions"


class DimensionVerdict(str, enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


class ValidationStepResult(BaseModel):
    """Result of a single validation dimension check."""

    dimension: ValidationDimension
    verdict: DimensionVerdict
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    evidence_used: list[EvidenceRef] = Field(default_factory=list)


class ChainOutcome(str, enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"


class ValidationChainResult(BaseModel):
    """Full result of a validation chain execution."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    target_object_ids: list[ControlObjectId] = Field(default_factory=list)
    action_type: str = ""
    outcome: ChainOutcome = ChainOutcome.FAILED
    steps: list[ValidationStepResult] = Field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    skipped_count: int = 0
    decision_hash: str = ""
    validated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        return self.outcome in (ChainOutcome.PASSED, ChainOutcome.PASSED_WITH_WARNINGS)

    def compute_hash(self) -> str:
        data = {
            "target_object_ids": [str(oid) for oid in self.target_object_ids],
            "action_type": self.action_type,
            "steps": [
                {"dimension": s.dimension.value, "verdict": s.verdict.value} for s in self.steps
            ],
        }
        self.decision_hash = deterministic_hash(data)
        return self.decision_hash
