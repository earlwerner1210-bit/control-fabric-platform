"""Eval routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.security import TenantContext
from app.db.session import get_db
from app.schemas.eval import EvalRunRequest, EvalRunResponse, EvalSummary
from app.services.eval.service import EvalService

router = APIRouter(prefix="/evals", tags=["evals"])


@router.post("/run", response_model=EvalSummary)
async def run_evals(
    body: EvalRunRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    svc = EvalService(db)
    runs = await svc.run_eval_batch(
        tenant_id=ctx.tenant_id,
        domain=body.domain,
        workflow_type=body.workflow_type,
        case_ids=body.case_ids,
    )
    summary = await svc.get_eval_summary(ctx.tenant_id, [r.id for r in runs])
    return EvalSummary(
        total_cases=summary["total_cases"],
        passed=summary["passed"],
        failed=summary["failed"],
        pass_rate=summary["pass_rate"],
        avg_score=summary["avg_score"],
        results=[EvalRunResponse.model_validate(r) for r in runs],
    )
