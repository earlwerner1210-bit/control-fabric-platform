"""Reasoning value types — scope, policy, results."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.types import (
    ConfidenceScore,
    ControlObjectId,
    DeterminismLevel,
    EvidenceRef,
    PlaneType,
    ReasoningScope,
    deterministic_hash,
)


class ReasoningMode(str, enum.Enum):
    DETERMINISTIC_RULES = "deterministic_rules"
    MODEL_ASSISTED = "model_assisted"
    HYBRID = "hybrid"


class ReasoningStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SCOPE_VIOLATION = "scope_violation"


class ReasoningPolicy(BaseModel):
    """Defines the bounds within which reasoning may operate."""

    allowed_scopes: list[ReasoningScope] = Field(
        default_factory=lambda: [ReasoningScope.SINGLE_OBJECT]
    )
    allowed_planes: list[PlaneType] = Field(default_factory=lambda: list(PlaneType))
    max_objects: int = 100
    max_depth: int = 5
    allowed_modes: list[ReasoningMode] = Field(
        default_factory=lambda: [ReasoningMode.DETERMINISTIC_RULES]
    )
    require_evidence: bool = True
    max_confidence_for_auto: float = 0.95
    domain: str | None = None


class ReasoningRequest(BaseModel):
    """Request to the bounded reasoning engine."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    scope: ReasoningScope
    mode: ReasoningMode = ReasoningMode.DETERMINISTIC_RULES
    target_object_ids: list[ControlObjectId] = Field(default_factory=list)
    plane: PlaneType | None = None
    domain: str | None = None
    question: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    policy: ReasoningPolicy = Field(default_factory=ReasoningPolicy)


class ReasoningStep(BaseModel):
    """A single step in a reasoning chain."""

    step_number: int
    action: str
    input_summary: str = ""
    output_summary: str = ""
    determinism_level: DeterminismLevel = DeterminismLevel.DETERMINISTIC
    evidence_used: list[EvidenceRef] = Field(default_factory=list)
    objects_consulted: list[ControlObjectId] = Field(default_factory=list)
    confidence: ConfidenceScore = ConfidenceScore(1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReasoningResult(BaseModel):
    """Full result of a reasoning invocation."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    request_id: uuid.UUID
    tenant_id: uuid.UUID
    status: ReasoningStatus = ReasoningStatus.COMPLETED
    mode: ReasoningMode = ReasoningMode.DETERMINISTIC_RULES
    scope: ReasoningScope = ReasoningScope.SINGLE_OBJECT
    conclusion: str = ""
    confidence: ConfidenceScore = ConfidenceScore(1.0)
    determinism_level: DeterminismLevel = DeterminismLevel.DETERMINISTIC
    steps: list[ReasoningStep] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    objects_consulted: list[ControlObjectId] = Field(default_factory=list)
    decision_hash: str = ""
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_hash(self) -> str:
        data = {
            "request_id": str(self.request_id),
            "conclusion": self.conclusion,
            "steps": [{"action": s.action, "output_summary": s.output_summary} for s in self.steps],
        }
        self.decision_hash = deterministic_hash(data)
        return self.decision_hash
