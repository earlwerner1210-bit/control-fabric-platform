"""Domain types for the Severity and Prioritisation Engine."""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class RouteCategory(str, enum.Enum):
    MUST_BLOCK = "must_block"
    REQUIRES_REVIEW = "requires_review"
    MONITOR = "monitor"
    SUPPRESS = "suppress"


class OperatorUrgency(str, enum.Enum):
    IMMEDIATE = "immediate"
    SAME_DAY = "same_day"
    THIS_WEEK = "this_week"
    BACKLOG = "backlog"


class SeverityWeight(BaseModel, frozen=True):
    """Configurable weight for a scoring dimension."""

    dimension: str
    weight: float = Field(ge=0.0, le=1.0)
    description: str = ""


class SeverityInput(BaseModel):
    """Input payload for severity scoring."""

    case_id: str
    case_type: str
    severity_raw: str = "medium"
    financial_impact: float = 0.0
    affected_objects: int = 1
    rule_criticality: str = "medium"
    domain_pack: str = "core"
    is_duplicate: bool = False
    cluster_id: str | None = None


class ScoredCase(BaseModel, frozen=True):
    """Output of the severity engine — immutable scored result."""

    case_id: str
    composite_score: float = Field(ge=0.0, le=100.0)
    route: RouteCategory
    urgency: OperatorUrgency
    rank: int = 0
    scoring_factors: dict[str, float] = Field(default_factory=dict)
    scored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
