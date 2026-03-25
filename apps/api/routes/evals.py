"""Eval routes — trigger evaluation runs and query results."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user, get_db, get_tenant_context

router = APIRouter(prefix="/evals", tags=["evals"])


# ── Schemas ───────────────────────────────────────────────────────────────


class EvalRunRequest(BaseModel):
    case_ids: list[str] = Field(..., min_length=1)
    eval_suite: str = "default"
    options: dict[str, Any] = Field(default_factory=dict)


class EvalRunResponse(BaseModel):
    run_id: str
    status: str
    case_count: int


class EvalResultItem(BaseModel):
    id: str
    case_id: str
    metrics: dict[str, float]
    passed: bool
    expected: dict[str, Any]
    actual: dict[str, Any]


class EvalRunDetail(BaseModel):
    run_id: str
    status: str
    results: list[EvalResultItem]
    summary: dict[str, Any]


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("/run", response_model=EvalRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_eval_run(
    body: EvalRunRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_context),
) -> EvalRunResponse:
    """Trigger an evaluation run against one or more cases."""
    run_id = str(uuid.uuid4())

    await db.execute(
        text(
            "INSERT INTO eval_runs (id, status, eval_suite, case_count, tenant_id) "
            "VALUES (:id, :status, :eval_suite, :case_count, :tenant_id)"
        ),
        {
            "id": run_id,
            "status": "running",
            "eval_suite": body.eval_suite,
            "case_count": len(body.case_ids),
            "tenant_id": tenant_id,
        },
    )

    return EvalRunResponse(
        run_id=run_id,
        status="running",
        case_count=len(body.case_ids),
    )


@router.get("/{run_id}", response_model=EvalRunDetail)
async def get_eval_results(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> EvalRunDetail:
    """Get the results of an evaluation run."""
    run_result = await db.execute(
        text("SELECT id, status FROM eval_runs WHERE id = :id"),
        {"id": run_id},
    )
    run_row = run_result.mappings().first()
    if run_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval run not found")

    results_result = await db.execute(
        text(
            "SELECT id, case_id, metrics, passed, expected, actual "
            "FROM eval_results WHERE run_id = :run_id"
        ),
        {"run_id": run_id},
    )
    items = [
        EvalResultItem(
            id=r["id"],
            case_id=r["case_id"],
            metrics=r["metrics"] if r["metrics"] else {},
            passed=r["passed"],
            expected=r["expected"] if r["expected"] else {},
            actual=r["actual"] if r["actual"] else {},
        )
        for r in results_result.mappings().all()
    ]

    total = len(items)
    passed = sum(1 for i in items if i.passed)
    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": (passed / total * 100) if total > 0 else 0.0,
    }

    return EvalRunDetail(
        run_id=run_id,
        status=run_row["status"],
        results=items,
        summary=summary,
    )
