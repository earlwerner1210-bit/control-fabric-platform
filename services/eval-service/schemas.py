"""Eval service request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema


class RunEvalRequest(BaseModel):
    eval_case_ids: list[uuid.UUID] = Field(..., min_length=1)
    model_provider: str = "vllm"


class CreateEvalCaseRequest(BaseModel):
    eval_type: str
    input_data: dict[str, Any]
    expected_output: dict[str, Any]
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalCaseResponse(BaseSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    eval_type: str
    input_data: dict[str, Any]
    expected_output: dict[str, Any]
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class EvalRunResponse(BaseSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    eval_case_id: uuid.UUID
    actual_output: dict[str, Any]
    score: float | None = None
    passed: bool | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class EvalBatchResponse(BaseSchema):
    run_id: uuid.UUID
    total: int
    passed: int
    failed: int
    metrics: dict[str, float] = Field(default_factory=dict)
    results: list[EvalRunResponse]
