"""Validation Chain schemas — 8-stage deterministic release gate."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ValidationStage(str, enum.Enum):
    SCHEMA = "schema"
    EVIDENCE = "evidence"
    BOUNDARY = "boundary"
    RULE = "rule"
    CROSS_PLANE = "cross_plane"
    POLICY = "policy"
    CONFIDENCE = "confidence"
    RELEASE = "release"


VALIDATION_STAGE_ORDER = [
    ValidationStage.SCHEMA,
    ValidationStage.EVIDENCE,
    ValidationStage.BOUNDARY,
    ValidationStage.RULE,
    ValidationStage.CROSS_PLANE,
    ValidationStage.POLICY,
    ValidationStage.CONFIDENCE,
    ValidationStage.RELEASE,
]


class StepVerdict(str, enum.Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


class ChainOutcome(str, enum.Enum):
    RELEASED = "released"
    BLOCKED = "blocked"
    WARN_RELEASED = "warn_released"
    ESCALATED = "escalated"


class ValidationStepInput(BaseModel):
    stage: ValidationStage
    payload: dict[str, Any] = Field(default_factory=dict)
    skip: bool = False
    skip_reason: str | None = None


class ValidationStepResult(BaseModel):
    stage: ValidationStage
    verdict: StepVerdict
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    skipped: bool = False
    skip_reason: str | None = None


class ValidationChainRequest(BaseModel):
    pilot_case_id: uuid.UUID
    tenant_id: uuid.UUID
    candidate_action_id: uuid.UUID | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    evidence_bundle_id: uuid.UUID | None = None
    graph_slice_id: uuid.UUID | None = None
    skip_stages: list[ValidationStage] = Field(default_factory=list)
    fail_fast: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationChainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    tenant_id: uuid.UUID
    outcome: ChainOutcome
    steps: list[ValidationStepResult]
    total_steps: int
    passed_steps: int
    warned_steps: int
    failed_steps: int
    skipped_steps: int
    blocking_stage: ValidationStage | None
    blocking_message: str | None
    duration_ms: float
    metadata: dict[str, Any]
    created_at: datetime


class ValidationChainSummary(BaseModel):
    total_runs: int = 0
    released: int = 0
    blocked: int = 0
    warn_released: int = 0
    escalated: int = 0
    most_common_blocking_stage: str | None = None
    block_rate: float = 0.0
    avg_duration_ms: float = 0.0
    by_stage_verdict: dict[str, dict[str, int]] = Field(default_factory=dict)
