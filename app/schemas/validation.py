"""Validation schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from app.schemas.common import BaseSchema


class ValidationStatusEnum(str, enum.Enum):
    passed = "passed"
    warned = "warned"
    blocked = "blocked"
    escalated = "escalated"


class RuleResult(BaseSchema):
    rule_name: str
    passed: bool
    message: str
    severity: str = "info"  # info, warning, error, critical


class ValidationResultCreate(BaseSchema):
    workflow_case_id: uuid.UUID
    validator_name: str
    domain: str
    rule_results: list[RuleResult]


class ValidationResultResponse(BaseSchema):
    id: uuid.UUID
    workflow_case_id: uuid.UUID
    validator_name: str
    status: ValidationStatusEnum
    domain: str
    rule_results: dict
    summary: str | None = None
    created_at: datetime
