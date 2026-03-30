"""
Exception and Override Framework — Domain Types

Core rules (non-negotiable):
  1. Overrides cannot be silent
  2. Overrides must expire
  3. Overrides must bind to specific policy/version/evidence context
  4. Overrides must create review tasks automatically
  5. Override audit ledger is append-only and immutable

Patent relevance: Demonstrates that the platform governs exceptions
through the same deterministic validation chain — not a backdoor.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ExceptionType(str, Enum):
    EMERGENCY_OVERRIDE = "emergency_override"
    TIME_BOUND_EXCEPTION = "time_bound_exception"
    COMPENSATING_CONTROL = "compensating_control"
    ESCALATION_BYPASS = "escalation_bypass"


class ExceptionStatus(str, Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    REJECTED = "rejected"


class ExceptionRisk(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExceptionRequest(BaseModel):
    """
    A formally submitted request to override or except a platform decision.
    Cannot be created silently — all fields required at submission.
    """

    exception_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exception_type: ExceptionType
    requested_by: str
    justification: str = Field(
        min_length=50, description="Must be substantive — minimum 50 characters"
    )
    affected_object_ids: list[str]
    affected_action_type: str
    policy_context_id: str = Field(description="Specific policy version being overridden")
    compensating_controls: list[str] = Field(
        default_factory=list,
        description="Controls that compensate for this exception",
    )
    expires_at: datetime = Field(description="All exceptions must expire — none are permanent")
    risk_assessment: ExceptionRisk
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_hash: str = Field(default="")

    @model_validator(mode="after")
    def compute_hash(self) -> ExceptionRequest:
        payload = (
            f"{self.exception_id}{self.exception_type}{self.requested_by}"
            f"{self.affected_action_type}{self.policy_context_id}"
            f"{self.expires_at.isoformat()}{self.requested_at.isoformat()}"
        )
        self.request_hash = hashlib.sha256(payload.encode()).hexdigest()
        return self


class ExceptionDecision(BaseModel):
    """Immutable approval or rejection of an exception request."""

    model_config = {"frozen": True}

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exception_id: str
    decided_by: str
    decision: ExceptionStatus
    decision_rationale: str = Field(min_length=20)
    conditions: list[str] = Field(
        default_factory=list, description="Conditions attached to approval"
    )
    review_task_id: str = Field(
        description="Auto-created review task — cannot be empty on approval"
    )
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decision_hash: str = Field(default="")

    @model_validator(mode="after")
    def compute_hash(self) -> ExceptionDecision:
        payload = (
            f"{self.decision_id}{self.exception_id}{self.decided_by}"
            f"{self.decision}{self.decided_at.isoformat()}"
        )
        object.__setattr__(
            self,
            "decision_hash",
            hashlib.sha256(payload.encode()).hexdigest(),
        )
        return self


class ExceptionAuditEntry(BaseModel):
    """Immutable audit ledger entry — append-only."""

    model_config = {"frozen": True}

    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exception_id: str
    event_type: str
    event_detail: str
    performed_by: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    entry_hash: str = Field(default="")

    @model_validator(mode="after")
    def compute_hash(self) -> ExceptionAuditEntry:
        payload = (
            f"{self.entry_id}{self.exception_id}{self.event_type}"
            f"{self.performed_by}{self.occurred_at.isoformat()}"
        )
        object.__setattr__(
            self,
            "entry_hash",
            hashlib.sha256(payload.encode()).hexdigest(),
        )
        return self
