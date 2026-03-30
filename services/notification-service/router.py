"""Notification service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.security.auth import get_current_user

from .schemas import NotificationResponse, SendNotificationRequest
from .service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _notif_to_response(n) -> NotificationResponse:
    return NotificationResponse(
        id=n.id,
        tenant_id=n.tenant_id,
        channel=n.channel,
        recipient=n.recipient,
        subject=n.subject,
        body=n.body,
        status=n.status,
        created_at=n.created_at,
    )


@router.post("/send", response_model=NotificationResponse, status_code=201)
async def send_notification(
    body: SendNotificationRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = NotificationService(db)
    notif = await svc.send_notification(
        tenant_id=ctx.tenant_id,
        channel=body.channel,
        recipient=body.recipient,
        subject=body.subject,
        body=body.body,
        metadata=body.metadata,
    )
    return _notif_to_response(notif)


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = NotificationService(db)
    notifications = await svc.list_notifications(ctx.tenant_id, skip, limit)
    return [_notif_to_response(n) for n in notifications]
