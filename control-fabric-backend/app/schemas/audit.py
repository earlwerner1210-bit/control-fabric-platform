"""Audit trail schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class AuditEventResponse(BaseSchema):
    """A single audit event."""

    id: UUID
    event_type: str = Field(
        ...,
        examples=[
            "document.uploaded",
            "document.parsed",
            "workflow.started",
            "workflow.completed",
            "model.run",
            "validation.completed",
        ],
    )
    actor_id: UUID | None = Field(
        default=None, description="User or service that triggered the event"
    )
    resource_type: str = Field(..., examples=["document", "control_object", "workflow_case"])
    resource_id: UUID
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AuditTimelineResponse(BaseSchema):
    """Ordered list of audit events for a resource or case."""

    events: list[AuditEventResponse] = Field(default_factory=list)
    total: int = Field(..., ge=0)
