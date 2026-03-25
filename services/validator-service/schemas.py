"""Validator service request/response schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema
from shared.schemas.validation import ValidationResultResponse, ValidationRuleResult


class ValidateRequest(BaseModel):
    control_object_ids: list[uuid.UUID] = Field(..., min_length=1)
    domain: str
    rules: list[str] = Field(default_factory=list, description="Rule names to apply; empty = all")
    case_id: uuid.UUID | None = None


class ValidateResponse(BaseSchema):
    case_id: uuid.UUID
    results: list[ValidationResultResponse]
    overall_status: str
