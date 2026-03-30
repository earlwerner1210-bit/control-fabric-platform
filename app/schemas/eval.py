"""Eval schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.schemas.common import BaseSchema


class EvalCaseCreate(BaseSchema):
    domain: str
    workflow_type: str
    name: str
    description: str | None = None
    input_payload: dict
    expected_output: dict
    tags: dict | None = None


class EvalCaseResponse(BaseSchema):
    id: uuid.UUID
    domain: str
    workflow_type: str
    name: str
    description: str | None = None
    input_payload: dict
    expected_output: dict
    created_at: datetime


class EvalRunRequest(BaseSchema):
    domain: str | None = None
    workflow_type: str | None = None
    case_ids: list[uuid.UUID] | None = None


class EvalRunResponse(BaseSchema):
    id: uuid.UUID
    eval_case_id: uuid.UUID
    passed: bool
    score: float | None = None
    actual_output: dict | None = None
    details: dict | None = None
    created_at: datetime


class EvalSummary(BaseSchema):
    total_cases: int
    passed: int
    failed: int
    pass_rate: float
    avg_score: float | None = None
    results: list[EvalRunResponse] = []
