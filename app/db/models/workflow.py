"""WorkflowCase model – tracks each workflow execution."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, TenantMixin, UUIDPrimaryKeyMixin


class WorkflowStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class CaseVerdict(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"
    needs_review = "needs_review"
    escalated = "escalated"


class WorkflowCase(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "workflow_cases"

    workflow_type: Mapped[str] = mapped_column(String(63), nullable=False, index=True)
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status"),
        default=WorkflowStatus.pending,
        nullable=False,
    )
    verdict: Mapped[CaseVerdict | None] = mapped_column(
        Enum(CaseVerdict, name="case_verdict"),
        nullable=True,
    )
    input_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    temporal_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    initiated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
