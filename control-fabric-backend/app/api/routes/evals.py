"""Evaluation / regression-test endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.deps.auth import require_role
from app.core.security import TenantContext
from app.core.telemetry import metrics
from app.schemas.eval import EvalRunRequest, EvalRunResponse

router = APIRouter(prefix="/api/v1/evals", tags=["evals"])


@router.post("/run", response_model=EvalRunResponse, status_code=201)
async def run_eval(
    body: EvalRunRequest,
    ctx: TenantContext = Depends(require_role("admin", "analyst")),
) -> EvalRunResponse:
    """Execute an evaluation suite and return aggregated results.

    In production this dispatches to the eval runner service.
    Stub: returns an empty successful run.
    """
    metrics.increment("evals.runs")

    return EvalRunResponse(
        run_id=uuid.uuid4(),
        suite=body.suite,
        total=0,
        passed=0,
        failed=0,
        results=[],
    )
