"""Audit event schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import BaseSchema


class AuditEventCreate(BaseSchema):
    workflow_case_id: uuid.UUID | None = None
    event_type: str
    actor_id: uuid.UUID | None = None
    actor_type: str = "system"
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    detail: str | None = None
    payload: dict[str, Any] | None = None


class AuditEventResponse(BaseSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    workflow_case_id: uuid.UUID | None = None
    event_type: str
    actor_type: str
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    detail: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime
