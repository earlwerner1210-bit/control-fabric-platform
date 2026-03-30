"""Domain types for the Policy Administration Layer."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class PolicyStatus(str, enum.Enum):
    DRAFT = "draft"
    SIMULATING = "simulating"
    PUBLISHED = "published"
    ROLLED_BACK = "rolled_back"
    ARCHIVED = "archived"


class PolicyDefinition(BaseModel):
    """Mutable policy with lifecycle state."""

    policy_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str
    description: str = ""
    status: PolicyStatus = PolicyStatus.DRAFT
    rules: list[str] = Field(default_factory=list)
    target_packs: list[str] = Field(default_factory=list)
    created_by: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None
    version: int = 1


class PolicySimulationResult(BaseModel, frozen=True):
    """Immutable result of a policy simulation run."""

    policy_id: str
    simulated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    cases_evaluated: int = 0
    cases_affected: int = 0
    false_positives: int = 0
    impact_summary: str = ""
    safe_to_publish: bool = False


class PolicyConflict(BaseModel, frozen=True):
    """Detected conflict between two policies."""

    policy_a: str
    policy_b: str
    conflict_type: str
    description: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
