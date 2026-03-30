"""Validation-related Pydantic schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shared.schemas.common import BaseSchema


class ValidationSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class ValidationRuleResult(BaseSchema):
    """Result of a single validation rule."""

    rule_name: str
    passed: bool
    message: str
    severity: ValidationSeverity = ValidationSeverity.info
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationResultCreate(BaseSchema):
    """Payload for creating a validation result."""

    target_type: str
    target_id: uuid.UUID
    status: str  # passed | warned | blocked | escalated
    rule_results: list[ValidationRuleResult] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationResultResponse(BaseSchema):
    """Returned validation result."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    status: str
    rules_passed: int
    rules_warned: int
    rules_blocked: int
    rule_results: list[ValidationRuleResult]
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
