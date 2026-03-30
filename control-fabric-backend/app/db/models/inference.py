"""ModelRun model for tracking inference calls."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ModelRun(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "model_runs"

    provider = Column(String(63), nullable=False)
    model_name = Column(String(127), nullable=False)
    operation = Column(String(63), nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    workflow_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_cases.id", ondelete="SET NULL"),
        nullable=True,
    )
