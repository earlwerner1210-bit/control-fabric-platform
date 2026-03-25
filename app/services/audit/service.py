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

    async def log_workflow_event(
        self,
        tenant_id: uuid.UUID,
        case_id: uuid.UUID,
        event_type: str,
        stage: str,
        detail: str = "",
        metadata: dict | None = None,
        actor_id: uuid.UUID | None = None,
        actor_type: str = "system",
        source_type: str = "workflow_case",
        source_id: uuid.UUID | None = None,
    ) -> AuditEvent:
        """Log a structured workflow audit event with stage tracking."""
        payload: dict[str, Any] = {
            "stage": stage,
            "source_type": source_type,
        }
        if metadata:
            payload["metadata"] = metadata
        if source_id:
            payload["source_id"] = str(source_id)

        event = AuditEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_case_id=case_id,
            event_type=event_type,
            actor_id=actor_id,
            actor_type=actor_type,
            resource_type=source_type,
            resource_id=source_id,
            detail=detail or f"{event_type} at stage {stage}",
            payload=payload,
        )
        self.db.add(event)
        await self.db.flush()
        logger.info(
            "workflow_audit_event",
            event_type=event_type,
            stage=stage,
            case_id=str(case_id),
        )
        return event

    async def log_validation_event(
        self,
        tenant_id: uuid.UUID,
        case_id: uuid.UUID,
        validation_result_id: uuid.UUID,
        status: str,
        rule_count: int = 0,
        failed_count: int = 0,
        detail: str = "",
    ) -> AuditEvent:
        """Log a validation completion audit event."""
        payload: dict[str, Any] = {
            "validation_result_id": str(validation_result_id),
            "status": status,
            "rule_count": rule_count,
            "failed_count": failed_count,
        }

        event = AuditEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_case_id=case_id,
            event_type="validation_completed",
            actor_id=None,
            actor_type="system",
            resource_type="validation_result",
            resource_id=validation_result_id,
            detail=detail or f"Validation {status}: {rule_count} rules, {failed_count} failed",
            payload=payload,
        )
        self.db.add(event)
        await self.db.flush()
        logger.info(
            "validation_audit_event",
            case_id=str(case_id),
            status=status,
        )
        return event

    async def log_reconciliation_event(
        self,
        tenant_id: uuid.UUID,
        case_id: uuid.UUID,
        links_found: int = 0,
        conflicts_found: int = 0,
        leakage_patterns: int = 0,
        verdict: str = "",
    ) -> AuditEvent:
        """Log a reconciliation completion audit event."""
        payload: dict[str, Any] = {
            "links_found": links_found,
            "conflicts_found": conflicts_found,
            "leakage_patterns": leakage_patterns,
            "verdict": verdict,
        }

        event = AuditEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_case_id=case_id,
            event_type="reconciliation_completed",
            actor_id=None,
            actor_type="system",
            resource_type="reconciliation",
            resource_id=None,
            detail=f"Reconciliation {verdict}: {links_found} links, {conflicts_found} conflicts, {leakage_patterns} leakage patterns",
            payload=payload,
        )
        self.db.add(event)
        await self.db.flush()
        logger.info(
            "reconciliation_audit_event",
            case_id=str(case_id),
            verdict=verdict,
        )
        return event

    async def get_workflow_timeline(
        self,
        case_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[dict]:
        """Get ordered timeline of all audit events for a workflow case.
        Returns list of dicts with: timestamp, event_type, stage, detail, actor.
        """
        result = await self.db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.workflow_case_id == case_id,
                AuditEvent.tenant_id == tenant_id,
            )
            .order_by(AuditEvent.created_at.asc())
        )
        events = result.scalars().all()

        timeline: list[dict] = []
        for event in events:
            payload = event.payload or {}
            timeline.append({
                "timestamp": event.created_at.isoformat() if event.created_at else None,
                "event_type": event.event_type,
                "stage": payload.get("stage", ""),
                "detail": event.detail or "",
                "actor": f"{event.actor_type}:{event.actor_id}" if event.actor_id else event.actor_type,
            })
        return timeline

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
