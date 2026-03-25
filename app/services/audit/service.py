"""Audit service – append-only event logging."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import AuditEvent

logger = get_logger("audit")


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log_event(
        self,
        tenant_id: uuid.UUID,
        event_type: str,
        workflow_case_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        actor_type: str = "system",
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        detail: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_case_id=workflow_case_id,
            event_type=event_type,
            actor_id=actor_id,
            actor_type=actor_type,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            payload=payload,
        )
        self.db.add(event)
        await self.db.flush()
        logger.info("audit_event", event_type=event_type, case_id=str(workflow_case_id))
        return event

    async def get_case_audit_trail(
        self, workflow_case_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[AuditEvent]:
        result = await self.db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.workflow_case_id == workflow_case_id,
                AuditEvent.tenant_id == tenant_id,
            )
            .order_by(AuditEvent.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_events(
        self,
        tenant_id: uuid.UUID,
        event_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditEvent], int]:
        stmt = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
        if event_type:
            stmt = stmt.where(AuditEvent.event_type == event_type)

        count_result = await self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        )
        total = count_result.scalar() or 0

        stmt = stmt.offset((page - 1) * page_size).limit(page_size).order_by(AuditEvent.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
