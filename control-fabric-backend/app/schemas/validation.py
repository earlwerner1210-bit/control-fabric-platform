"""Validation result schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class ValidationResultResponse(BaseSchema):
    """A single validation-rule execution result."""

    id: UUID
    target_type: str = Field(
        ...,
        description="Type of entity that was validated",
        examples=["contract_compile", "margin_diagnosis", "billability_decision"],
    )
    target_id: UUID = Field(..., description="ID of the entity that was validated")
    rule_name: str = Field(..., description="Machine-readable rule identifier")
    passed: bool
    severity: str = Field(
        ...,
        examples=["info", "warning", "error", "critical"],
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Rule-specific detail payload (reason, evidence, thresholds, etc.)",
    )
    created_at: datetime
