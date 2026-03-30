"""Reconciler service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.security.auth import get_current_user

from .schemas import ReconcileRequest, ReconcileResponse
from .service import ReconcilerService

router = APIRouter(tags=["reconciler"])


@router.post("/reconcile", response_model=ReconcileResponse, status_code=200)
async def reconcile(
    body: ReconcileRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ReconcilerService(db)
    result = await svc.reconcile_objects(body.case_id, body.object_ids, ctx.tenant_id)
    return ReconcileResponse(**result)
