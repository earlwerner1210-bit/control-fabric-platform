"""Audit service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.security.auth import get_current_user

from .schemas import AuditEventItem, AuditLogRequest, ModelRunLogRequest
from .service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


def _event_to_item(e) -> AuditEventItem:
    return AuditEventItem(
        id=e.id,
        tenant_id=e.tenant_id,
        event_type=e.event_type,
        actor_id=e.actor_id,
        resource_type=e.resource_type,
        resource_id=e.resource_id,
        action=e.action,
        detail=e.detail or {},
        created_at=e.created_at,
    )


@router.post("/log", response_model=AuditEventItem, status_code=201)
async def log_event(
    body: AuditLogRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AuditService(db)
    event = await svc.log_event(
        tenant_id=ctx.tenant_id,
        actor_id=ctx.user_id,
        event_type=body.event_type,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        action=body.action,
        detail=body.detail,
    )
    return _event_to_item(event)


@router.post("/model-run", status_code=201)
async def log_model_run(
    body: ModelRunLogRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AuditService(db)
    run = await svc.log_model_run(
        tenant_id=ctx.tenant_id,
        model_name=body.model_name,
        model_provider=body.model_provider,
        input_tokens=body.input_tokens,
        output_tokens=body.output_tokens,
        latency_ms=body.latency_ms,
        cost_usd=body.cost_usd,
        input_payload=body.input_payload,
        output_payload=body.output_payload,
    )
    return {"id": str(run.id), "status": "logged"}


@router.get("/{case_id}", response_model=list[AuditEventItem])
async def get_case_audit(
    case_id: str,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AuditService(db)
    events = await svc.get_case_audit_trail(case_id, ctx.tenant_id)
    return [_event_to_item(e) for e in events]


@router.get("", response_model=list[AuditEventItem])
async def list_audit_events(
    event_type: str | None = Query(None),
    resource_type: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AuditService(db)
    events = await svc.get_workflow_events(ctx.tenant_id, event_type, resource_type, skip, limit)
    return [_event_to_item(e) for e in events]
