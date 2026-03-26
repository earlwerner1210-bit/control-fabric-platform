"""Common / shared Pydantic schemas used across the platform."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema with ORM-mode and alias population enabled."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PaginatedResponse(BaseSchema, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int = Field(..., ge=0, description="Total number of matching records")
    page: int = Field(..., ge=1, description="Current page number (1-based)")
    page_size: int = Field(..., ge=1, le=500, description="Items per page")


class ErrorResponse(BaseSchema):
    """Standard error response returned by all endpoints on failure."""

    detail: str = Field(..., description="Human-readable error message")
    code: str = Field(..., description="Machine-readable error code, e.g. 'VALIDATION_ERROR'")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of when the error occurred",
    )
    extra: dict | None = Field(
        default=None,
        description="Optional bag of additional context (field errors, trace ids, etc.)",
    )


class HealthResponse(BaseSchema):
    """Response for the /health endpoint."""

    status: str = Field(..., examples=["ok", "degraded", "down"])
    version: str = Field(..., examples=["0.1.0"])
    environment: str = Field(..., examples=["dev", "staging", "prod"])
