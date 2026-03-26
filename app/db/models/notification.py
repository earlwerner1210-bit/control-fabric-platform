"""NotificationEvent model."""

from __future__ import annotations

import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class NotificationEvent(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "notification_events"

    workflow_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(31), nullable=False)  # email, webhook, slack
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    status: Mapped[str] = mapped_column(String(31), default="pending")  # pending, sent, failed
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
