"""Action Engine schemas — evidence-gated candidate action release."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, enum.Enum):
    BILLING_ADJUSTMENT = "billing_adjustment"
    CONTRACT_FLAG = "contract_flag"
    DISPATCH_ORDER = "dispatch_order"
    ESCALATION = "escalation"
    NOTIFICATION = "notification"
    WORKFLOW_TRIGGER = "workflow_trigger"
    REMEDIATION = "remediation"
    AUDIT_ENTRY = "audit_entry"


class ActionStatus(str, enum.Enum):
    CANDIDATE = "candidate"
    VALIDATING = "validating"
    RELEASED = "released"
    BLOCKED = "blocked"
    ESCALATED = "escalated"
    EXECUTED = "executed"
    ROLLED_BACK = "rolled_back"
    EXPIRED = "expired"


class CandidateActionCreate(BaseModel):
    pilot_case_id: uuid.UUID
    action_type: ActionType
    label: str
    description: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[uuid.UUID] = Field(default_factory=list)
    source_object_ids: list[uuid.UUID] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    priority: int = Field(ge=0, le=10, default=5)
    requires_approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    tenant_id: uuid.UUID
    action_type: ActionType
    label: str
    description: str | None
    payload: dict[str, Any]
    status: ActionStatus
    evidence_refs: list[uuid.UUID]
    source_object_ids: list[uuid.UUID]
    confidence: float
    priority: int
    requires_approval: bool
    validation_chain_id: uuid.UUID | None
    blocking_reason: str | None
    released_at: datetime | None
    executed_at: datetime | None
    metadata: dict[str, Any]
    created_at: datetime


class ActionReleaseRequest(BaseModel):
    released_by: uuid.UUID
    reasoning: str | None = None
    override: bool = False


class ActionBlockRequest(BaseModel):
    blocked_by: uuid.UUID
    blocking_reason: str
    escalate: bool = False


class ActionExecutionResult(BaseModel):
    action_id: uuid.UUID
    success: bool
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    executed_at: datetime


class ActionEngineSummary(BaseModel):
    total_candidates: int = 0
    released: int = 0
    blocked: int = 0
    escalated: int = 0
    executed: int = 0
    rolled_back: int = 0
    release_rate: float = 0.0
    block_rate: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    avg_confidence: float = 0.0
