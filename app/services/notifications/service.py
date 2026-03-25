"""Notification service – email/webhook stubs."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import NotificationEvent

logger = get_logger("notifications")


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def send_notification(
        self,
        tenant_id: uuid.UUID,
        channel: str,
        recipient: str,
        subject: str,
        body: str,
        workflow_case_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> NotificationEvent:
        event = NotificationEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_case_id=workflow_case_id,
            channel=channel,
            recipient=recipient,
            subject=subject,
            body=body,
            status="pending",
            payload=payload,
        )
        self.db.add(event)
        await self.db.flush()

        # Dispatch based on channel
        if channel == "email":
            await self._send_email(event)
        elif channel == "webhook":
            await self._send_webhook(event)
        elif channel == "slack":
            await self._send_slack(event)

        return event

    async def _send_email(self, event: NotificationEvent) -> None:
        # TODO: Integrate with actual email provider (SendGrid, SES, etc.)
        logger.info("email_sent_stub", recipient=event.recipient, subject=event.subject)
        event.status = "sent"

    async def _send_webhook(self, event: NotificationEvent) -> None:
        # TODO: POST to webhook URL
        logger.info("webhook_sent_stub", recipient=event.recipient)
        event.status = "sent"

    async def _send_slack(self, event: NotificationEvent) -> None:
        # TODO: Integrate with Slack API
        logger.info("slack_sent_stub", recipient=event.recipient)
        event.status = "sent"

    async def notify_workflow_status(
        self,
        tenant_id: uuid.UUID,
        workflow_case_id: uuid.UUID,
        status: str,
        workflow_type: str,
    ) -> None:
        """Send notification about workflow status change."""
        await self.send_notification(
            tenant_id=tenant_id,
            channel="webhook",
            recipient="default",
            subject=f"Workflow {workflow_type} - {status}",
            body=f"Workflow case {workflow_case_id} is now {status}.",
            workflow_case_id=workflow_case_id,
        )

    async def notify_escalation(
        self,
        tenant_id: uuid.UUID,
        workflow_case_id: uuid.UUID,
        escalation_level: str,
        reason: str,
    ) -> None:
        """Send escalation notification."""
        await self.send_notification(
            tenant_id=tenant_id,
            channel="email",
            recipient="escalation-team@company.com",
            subject=f"Escalation: Level {escalation_level}",
            body=f"Escalation triggered for case {workflow_case_id}. Reason: {reason}",
            workflow_case_id=workflow_case_id,
        )
