"""ValidationResult model."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, TenantMixin, UUIDPrimaryKeyMixin


class ValidationStatus(str, enum.Enum):
    passed = "passed"
    warned = "warned"
    blocked = "blocked"
    escalated = "escalated"


class ValidationResult(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "validation_results"

    workflow_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_cases.id"), nullable=False, index=True
    )
    validator_name: Mapped[str] = mapped_column(String(127), nullable=False)
    status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status"), nullable=False
    )
    domain: Mapped[str] = mapped_column(String(63), nullable=False)
    rule_results: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[str | None] = mapped_column(String(1024), nullable=True)
