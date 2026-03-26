"""Control object and control link schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class ControlObjectTypeEnum(StrEnum):
    """All recognised control-object types in the platform."""

    OBLIGATION = "obligation"
    SLA_TARGET = "sla_target"
    PENALTY_CLAUSE = "penalty_clause"
    RATE_CARD_ITEM = "rate_card_item"
    BILLABLE_EVENT = "billable_event"
    WORK_ORDER = "work_order"
    INCIDENT = "incident"
    RESOLUTION_ACTION = "resolution_action"
    APPROVAL_GATE = "approval_gate"
    EVIDENCE = "evidence"


# ── Creation ──────────────────────────────────────────────────────────────


class ControlObjectCreate(BaseSchema):
    """Payload for creating a new control object."""

    control_type: ControlObjectTypeEnum
    domain: str = Field(..., examples=["contract-margin", "telco-ops", "utilities-field"])
    label: str = Field(..., min_length=1, max_length=512)
    description: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    source_document_id: UUID | None = None
    source_clause_ref: str | None = Field(
        default=None,
        description="Reference to the originating clause / section in the source document",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Extraction / classification confidence score",
    )


class ControlObjectResponse(BaseSchema):
    """Full representation of a persisted control object."""

    id: UUID
    tenant_id: UUID
    control_type: ControlObjectTypeEnum
    domain: str
    label: str
    description: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    source_document_id: UUID | None = None
    source_clause_ref: str | None = None
    confidence: float | None = None
    workflow_case_id: UUID | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


# ── Links ─────────────────────────────────────────────────────────────────


class ControlLinkCreate(BaseSchema):
    """Payload for creating a directional link between two control objects."""

    source_object_id: UUID
    target_object_id: UUID
    link_type: str = Field(
        ...,
        examples=["derived_from", "enforces", "mitigates", "evidences"],
    )
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ControlLinkResponse(BaseSchema):
    """Persisted control link between two objects."""

    id: UUID
    source_object_id: UUID
    target_object_id: UUID
    link_type: str
    weight: float
    created_at: datetime
