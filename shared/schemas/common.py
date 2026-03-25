"""Common Pydantic v2 schemas used across all services."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema with ORM-mode enabled."""

    model_config = ConfigDict(from_attributes=True)


class TenantContext(BaseModel):
    """Represents the authenticated tenant + user context."""

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    roles: list[str] = Field(default_factory=list)


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response wrapper."""

    items: list[T]
    total: int
    page: int = 1
    page_size: int = 50


class ErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str
    code: str = "INTERNAL_ERROR"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Service health-check response."""

    status: str = "ok"
    version: str = "0.1.0"
    services: dict[str, Any] = Field(default_factory=dict)
