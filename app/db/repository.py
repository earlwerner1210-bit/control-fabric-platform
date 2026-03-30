"""
Repository pattern — database-backed implementations of platform stores.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_v2 import (
    AuditLogDB,
    ControlObjectDB,
    ReconciliationCaseDB,
)

logger = logging.getLogger(__name__)


class ObjectRepository:
    def __init__(self, session: AsyncSession, tenant_id: str = "default") -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def save(self, obj_dict: dict) -> None:
        db_obj = ControlObjectDB(
            tenant_id=self.tenant_id,
            **{k: v for k, v in obj_dict.items() if hasattr(ControlObjectDB, k)},
        )
        self.session.add(db_obj)
        await self.session.flush()

    async def get(self, object_id: str) -> dict | None:
        result = await self.session.execute(
            select(ControlObjectDB).where(
                ControlObjectDB.id == object_id,
                ControlObjectDB.tenant_id == self.tenant_id,
                ControlObjectDB.is_deleted.is_(False),
            )
        )
        row = result.scalar_one_or_none()
        return self._to_dict(row) if row else None

    async def list_by_plane(self, plane: str) -> list[dict]:
        result = await self.session.execute(
            select(ControlObjectDB).where(
                ControlObjectDB.operational_plane == plane,
                ControlObjectDB.tenant_id == self.tenant_id,
                ControlObjectDB.is_deleted.is_(False),
            )
        )
        return [self._to_dict(r) for r in result.scalars()]

    async def soft_delete(self, object_id: str) -> None:
        await self.session.execute(
            update(ControlObjectDB)
            .where(
                ControlObjectDB.id == object_id,
                ControlObjectDB.tenant_id == self.tenant_id,
            )
            .values(is_deleted=True, deleted_at=datetime.now(UTC))
        )

    @staticmethod
    def _to_dict(obj: ControlObjectDB) -> dict:
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


class CaseRepository:
    def __init__(self, session: AsyncSession, tenant_id: str = "default") -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def save(self, case_dict: dict) -> None:
        db_case = ReconciliationCaseDB(
            tenant_id=self.tenant_id,
            **{k: v for k, v in case_dict.items() if hasattr(ReconciliationCaseDB, k)},
        )
        self.session.add(db_case)
        await self.session.flush()

    async def get_open(self) -> list[dict]:
        result = await self.session.execute(
            select(ReconciliationCaseDB)
            .where(
                ReconciliationCaseDB.tenant_id == self.tenant_id,
                ReconciliationCaseDB.status == "open",
                ReconciliationCaseDB.is_deleted.is_(False),
            )
            .order_by(ReconciliationCaseDB.severity_score.desc())
        )
        return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in result.scalars()]

    async def resolve(self, case_id: str, resolved_by: str, note: str) -> None:
        await self.session.execute(
            update(ReconciliationCaseDB)
            .where(
                ReconciliationCaseDB.id == case_id,
                ReconciliationCaseDB.tenant_id == self.tenant_id,
            )
            .values(
                status="resolved",
                resolved_at=datetime.now(UTC),
                resolved_by=resolved_by,
                resolution_note=note,
            )
        )


class AuditRepository:
    def __init__(self, session: AsyncSession, tenant_id: str = "default") -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def log(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        performed_by: str,
        detail: str,
        data: dict | None = None,
    ) -> None:
        payload = f"{event_type}{entity_id}{performed_by}{datetime.now(UTC).isoformat()}"
        entry = AuditLogDB(
            tenant_id=self.tenant_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            performed_by=performed_by,
            event_detail=detail,
            event_data=data or {},
            event_hash=hashlib.sha256(payload.encode()).hexdigest(),
        )
        self.session.add(entry)
        await self.session.flush()

    async def export(
        self,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 10000,
    ) -> list[dict]:
        q = select(AuditLogDB).where(AuditLogDB.tenant_id == self.tenant_id)
        if from_dt:
            q = q.where(AuditLogDB.occurred_at >= from_dt)
        if to_dt:
            q = q.where(AuditLogDB.occurred_at <= to_dt)
        q = q.order_by(AuditLogDB.occurred_at.desc()).limit(limit)
        result = await self.session.execute(q)
        return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in result.scalars()]
