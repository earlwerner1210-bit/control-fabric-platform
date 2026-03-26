"""Evaluation / regression-test schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class EvalRunRequest(BaseSchema):
    """Request to execute an evaluation suite."""

    suite: str = Field(
        ...,
        description="Name of the eval suite to run",
        examples=["contract_compile_v1", "margin_basic"],
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional tags to filter which cases within the suite to run",
    )


class EvalCaseResult(BaseSchema):
    """Result of a single evaluation case."""

    name: str = Field(..., description="Unique case name within the suite")
    passed: bool
    expected: Any = None
    actual: Any = None
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional comparison / diagnostic information",
    )


class EvalRunResponse(BaseSchema):
    """Aggregated result of a full evaluation run."""

    run_id: UUID
    suite: str
    total: int = Field(..., ge=0)
    passed: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    results: list[EvalCaseResult] = Field(default_factory=list)
