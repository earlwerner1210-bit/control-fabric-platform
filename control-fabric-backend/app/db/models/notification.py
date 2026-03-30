"""NotificationEvent model."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class NotificationEvent(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "notification_events"

    channel = Column(String(31), nullable=False)
    recipient = Column(String(500), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(31), nullable=False, default="pending")
    sent_at = Column(DateTime(timezone=True), nullable=True)
