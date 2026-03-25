"""Notification service request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema


class SendNotificationRequest(BaseModel):
    channel: str = Field(default="email", description="email, webhook, or in-app")
    recipient: str
    subject: str
    body: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationResponse(BaseSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    channel: str
    recipient: str
    subject: str
    body: str
    status: str
    created_at: datetime
