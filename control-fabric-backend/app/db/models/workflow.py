"""WorkflowCase model."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSON

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowCase(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "workflow_cases"

    workflow_type = Column(String(63), nullable=False, index=True)
    status = Column(String(31), nullable=False, default="pending")
    verdict = Column(String(31), nullable=True)
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    temporal_workflow_id = Column(String(255), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
