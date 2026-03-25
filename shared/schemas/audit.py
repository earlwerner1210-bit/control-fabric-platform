"""Audit-event Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shared.schemas.common import BaseSchema


class AuditEventCreate(BaseSchema):
    """Payload for recording an audit event."""

    event_type: str
    actor_id: uuid.UUID | None = None
    resource_type: str
    resource_id: str
    action: str
    detail: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None


class AuditEventResponse(BaseSchema):
    """Returned audit event."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    event_type: str
    actor_id: uuid.UUID | None = None
    resource_type: str
    resource_id: str
    action: str
    detail: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
