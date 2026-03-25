"""Control object schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from app.schemas.common import BaseSchema


class ControlObjectTypeEnum(str, enum.Enum):
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
    control_type: ControlObjectTypeEnum
    domain: str
    label: str
    description: str | None = None
    payload: dict = {}
    source_document_id: uuid.UUID | None = None
    source_chunk_id: uuid.UUID | None = None
    source_clause_ref: str | None = None
    confidence: float = 1.0


class ControlObjectResponse(BaseSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    control_type: ControlObjectTypeEnum
    domain: str
    label: str
    description: str | None = None
    payload: dict
    source_document_id: uuid.UUID | None = None
    source_clause_ref: str | None = None
    confidence: float
    workflow_case_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class ControlLinkCreate(BaseSchema):
    source_object_id: uuid.UUID
    target_object_id: uuid.UUID
    link_type: str
    weight: float = 1.0
    metadata: dict | None = None


class ControlLinkResponse(BaseSchema):
    id: uuid.UUID
    source_object_id: uuid.UUID
    target_object_id: uuid.UUID
    link_type: str
    weight: float
    created_at: datetime
