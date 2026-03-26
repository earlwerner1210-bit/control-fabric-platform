"""ModelRun model – logs every inference invocation."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ModelRun(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "model_runs"

    workflow_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(63), nullable=False)  # vllm, openai, mlx, fake
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    operation: Mapped[str] = mapped_column(
        String(63), nullable=False
    )  # generate, summarize, classify, explain
    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    input_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    success: Mapped[bool] = mapped_column(default=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
