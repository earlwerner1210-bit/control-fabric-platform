"""Shared Pydantic v2 schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TenantContext(BaseSchema):
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    roles: list[str] = []


class PaginatedResponse(BaseSchema, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 50


class ErrorResponse(BaseSchema):
    detail: str
    code: str
    timestamp: datetime | None = None
    extra: dict[str, Any] | None = None


class HealthResponse(BaseSchema):
    status: str
    version: str
    environment: str


class ReadinessResponse(BaseSchema):
    ready: bool
    checks: dict[str, str]


class MetricsResponse(BaseSchema):
    total_requests: int
    total_errors: int
    avg_latency_ms: float
    error_rate: float
