"""Notification service business logic."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import NotificationEvent
from shared.telemetry.logging import get_logger

logger = get_logger("notification_service")


class NotificationService:
    """Handles sending notifications via multiple channels."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def send_notification(
        self,
        tenant_id: uuid.UUID,
        channel: str,
        recipient: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationEvent:
        """Create and dispatch a notification."""
        notification = NotificationEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            channel=channel,
            recipient=recipient,
            subject=subject,
            body=body,
            status="pending",
            metadata_=metadata or {},
        )
        self.db.add(notification)
        await self.db.flush()

        # Dispatch to the appropriate channel
        try:
            if channel == "email":
                await self.send_email_stub(recipient, subject, body)
            elif channel == "webhook":
                await self.send_webhook_stub(recipient, subject, body)
            else:
                logger.info("In-app notification created for %s", recipient)

            notification.status = "sent"
        except Exception as exc:
            notification.status = "failed"
            notification.error_detail = str(exc)
            logger.error("Failed to send %s notification to %s: %s", channel, recipient, exc)

        await self.db.flush()
        logger.info(
            "Notification %s (%s) to %s: %s",
            notification.id,
            channel,
            recipient,
            notification.status,
        )
        return notification

    @staticmethod
    async def send_email_stub(recipient: str, subject: str, body: str) -> None:
        """Stub for sending email. Replace with real SMTP/SES integration."""
        logger.info("EMAIL STUB: To=%s, Subject=%s, Body=%d chars", recipient, subject, len(body))

    @staticmethod
    async def send_webhook_stub(url: str, subject: str, body: str) -> None:
        """Stub for sending webhook. Replace with real HTTP POST."""
        logger.info("WEBHOOK STUB: URL=%s, Subject=%s, Body=%d chars", url, subject, len(body))

    async def list_notifications(
        self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[NotificationEvent]:
        """List notifications for a tenant."""
        result = await self.db.execute(
            select(NotificationEvent)
            .where(NotificationEvent.tenant_id == tenant_id)
            .order_by(NotificationEvent.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
