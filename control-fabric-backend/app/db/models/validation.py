"""ValidationResult model."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ValidationResult(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "validation_results"

    target_type = Column(String(63), nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    rule_name = Column(String(127), nullable=False)
    passed = Column(Boolean, nullable=False)
    severity = Column(String(31), nullable=False)
    details = Column(JSON, nullable=True)
    workflow_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_cases.id", ondelete="SET NULL"),
        nullable=True,
    )
