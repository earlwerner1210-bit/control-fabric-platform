"""Audit service request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema


class AuditLogRequest(BaseModel):
    event_type: str
    resource_type: str
    resource_id: str
    action: str
    case_id: uuid.UUID | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class ModelRunLogRequest(BaseModel):
    model_name: str
    model_provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] | None = None
    case_id: uuid.UUID | None = None


class AuditEventItem(BaseSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    event_type: str
    actor_id: uuid.UUID | None = None
    resource_type: str
    resource_id: str
    action: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
