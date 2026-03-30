"""Domain types for the Onboarding Modelling Studio."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class StepOutcome(BaseModel, frozen=True):
    step_name: str
    status: StepStatus
    artifacts: dict[str, str] = Field(default_factory=dict)
    completed_at: datetime | None = None
    error: str | None = None


ONBOARDING_STEPS: list[str] = [
    "domain_discovery",
    "schema_mapping",
    "rule_authoring",
    "evidence_binding",
    "pack_assembly",
    "validation_dry_run",
    "activation",
]


class OnboardingStep(BaseModel, frozen=True):
    """Definition of a single onboarding step."""

    name: str
    order: int
    description: str
    required: bool = True


class OnboardingSession(BaseModel):
    """Mutable session tracking a domain-onboarding journey."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_name: str
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    current_step: int = 0
    steps: list[StepOutcome] = Field(default_factory=list)
    completed: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)
