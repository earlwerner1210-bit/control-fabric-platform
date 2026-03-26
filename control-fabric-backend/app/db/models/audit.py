"""AuditEvent model."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "audit_events"

    event_type = Column(String(127), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    resource_type = Column(String(63), nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    payload = Column(JSON, nullable=True)
    workflow_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_cases.id", ondelete="SET NULL"),
        nullable=True,
    )
