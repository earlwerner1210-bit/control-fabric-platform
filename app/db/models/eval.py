"""EvalCase and EvalRun models."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EvalCase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "eval_cases"

    domain: Mapped[str] = mapped_column(String(63), nullable=False, index=True)
    workflow_type: Mapped[str] = mapped_column(String(63), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    expected_output: Mapped[dict] = mapped_column(JSON, nullable=False)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class EvalRun(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "eval_runs"

    eval_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_cases.id"), nullable=False, index=True
    )
    workflow_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actual_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    passed: Mapped[bool] = mapped_column(default=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
