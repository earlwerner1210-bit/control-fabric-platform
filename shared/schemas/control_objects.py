"""Control-object and control-link schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shared.schemas.common import BaseSchema


class ControlObjectType(str, enum.Enum):
    obligation = "obligation"
    billable_event = "billable_event"
    penalty_condition = "penalty_condition"
    dispatch_precondition = "dispatch_precondition"
    skill_requirement = "skill_requirement"
    incident_state = "incident_state"
    escalation_rule = "escalation_rule"
    service_state = "service_state"
    readiness_check = "readiness_check"
    leakage_trigger = "leakage_trigger"


class ControlObjectCreate(BaseSchema):
    """Payload for creating a new control object."""

    control_type: ControlObjectType
    label: str
    description: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    source_document_id: uuid.UUID | None = None
    source_chunk_id: uuid.UUID | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ControlObjectResponse(BaseSchema):
    """Returned control object."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    control_type: ControlObjectType
    label: str
    description: str | None = None
    payload: dict[str, Any]
    source_document_id: uuid.UUID | None = None
    source_chunk_id: uuid.UUID | None = None
    confidence: float | None = None
    is_active: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ControlLinkCreate(BaseSchema):
    """Payload for linking two control objects."""

    source_id: uuid.UUID
    target_id: uuid.UUID
    relation_type: str
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ControlLinkResponse(BaseSchema):
    """Returned control link."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    relation_type: str
    weight: float | None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
