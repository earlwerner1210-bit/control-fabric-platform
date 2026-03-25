"""Eval service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.security.auth import get_current_user

from .schemas import (
    CreateEvalCaseRequest,
    EvalBatchResponse,
    EvalCaseResponse,
    EvalRunResponse,
    RunEvalRequest,
)
from .service import EvalService

router = APIRouter(prefix="/evals", tags=["evals"])


def _run_to_response(r) -> EvalRunResponse:
    return EvalRunResponse(
        id=r.id,
        tenant_id=r.tenant_id,
        eval_case_id=r.eval_case_id,
        actual_output=r.actual_output or {},
        score=r.score,
        passed=r.passed,
        detail=r.detail or {},
        created_at=r.created_at,
    )


def _case_to_response(c) -> EvalCaseResponse:
    tags = c.tags if isinstance(c.tags, list) else []
    return EvalCaseResponse(
        id=c.id,
        tenant_id=c.tenant_id,
        eval_type=c.eval_type,
        input_data=c.input_data or {},
        expected_output=c.expected_output or {},
        tags=tags,
        metadata=c.metadata_ or {},
        created_at=c.created_at,
    )


@router.post("/run", response_model=EvalBatchResponse, status_code=201)
async def run_eval(
    body: RunEvalRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = EvalService(db)
    result = await svc.run_eval_batch(body.eval_case_ids, ctx.tenant_id, body.model_provider)
    return EvalBatchResponse(
        run_id=result["run_id"],
        total=result["total"],
        passed=result["passed"],
        failed=result["failed"],
        metrics=result["metrics"],
        results=[_run_to_response(r) for r in result["results"]],
    )


@router.get("/{run_id}", response_model=list[EvalRunResponse])
async def get_eval_run(
    run_id: str,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = EvalService(db)
    runs = await svc.get_eval_run(run_id, ctx.tenant_id)
    return [_run_to_response(r) for r in runs]


@router.get("/cases", response_model=list[EvalCaseResponse])
async def list_eval_cases(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = EvalService(db)
    cases = await svc.list_eval_cases(ctx.tenant_id, skip, limit)
    return [_case_to_response(c) for c in cases]


@router.post("/cases", response_model=EvalCaseResponse, status_code=201)
async def create_eval_case(
    body: CreateEvalCaseRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = EvalService(db)
    case = await svc.create_eval_case(
        tenant_id=ctx.tenant_id,
        eval_type=body.eval_type,
        input_data=body.input_data,
        expected_output=body.expected_output,
        tags=body.tags,
        metadata=body.metadata,
    )
    return _case_to_response(case)
