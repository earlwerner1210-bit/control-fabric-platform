"""Audit service business logic."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import AuditEvent, ModelRun
from shared.telemetry.logging import get_logger

logger = get_logger("audit_service")


class AuditService:
    """Append-only audit logging for all control decisions and inference calls."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log_event(
        self,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID | None,
        event_type: str,
        resource_type: str,
        resource_id: str,
        action: str,
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Append an audit event (immutable log entry)."""
        event = AuditEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            event_type=event_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            detail=detail or {},
        )
        self.db.add(event)
        await self.db.flush()
        logger.info("Audit event: %s %s %s/%s", event_type, action, resource_type, resource_id)
        return event

    async def log_model_run(
        self,
        tenant_id: uuid.UUID,
        model_name: str,
        model_provider: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
        cost_usd: float | None = None,
        input_payload: dict[str, Any] | None = None,
        output_payload: dict[str, Any] | None = None,
    ) -> ModelRun:
        """Log a model inference run."""
        run = ModelRun(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            model_name=model_name,
            model_provider=model_provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            input_payload=input_payload or {},
            output_payload=output_payload,
        )
        self.db.add(run)
        await self.db.flush()
        logger.info(
            "Model run logged: %s/%s (%d tokens)",
            model_provider,
            model_name,
            input_tokens + output_tokens,
        )
        return run

    async def get_case_audit_trail(
        self, case_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[AuditEvent]:
        """Get all audit events related to a case (by resource_id match)."""
        result = await self.db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.resource_id == str(case_id),
            )
            .order_by(AuditEvent.created_at)
        )
        return list(result.scalars().all())

    async def get_workflow_events(
        self,
        tenant_id: uuid.UUID,
        event_type: str | None = None,
        resource_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AuditEvent]:
        """List audit events with optional filters."""
        stmt = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
        if event_type:
            stmt = stmt.where(AuditEvent.event_type == event_type)
        if resource_type:
            stmt = stmt.where(AuditEvent.resource_type == resource_type)
        stmt = stmt.order_by(AuditEvent.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
