"""Notification service – email, webhook, and Slack delivery with workflow alerts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import NotificationEvent

logger = get_logger("notifications")

# Supported delivery channels
SUPPORTED_CHANNELS: set[str] = {"email", "webhook", "slack"}


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Core send ─────────────────────────────────────────────────

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
        """Create and dispatch a notification on *channel*.

        Supported channels: ``email``, ``webhook``, ``slack``.
        Delivery is currently stubbed — each channel logger records the
        attempt and marks the event as ``sent``.  If the channel is
        unrecognised the event remains in ``pending`` status.
        """
        if channel not in SUPPORTED_CHANNELS:
            logger.warning("unsupported_channel", channel=channel, recipient=recipient)

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

    # ── Workflow alert ────────────────────────────────────────────

    async def send_workflow_alert(
        self,
        tenant_id: uuid.UUID,
        workflow_id: uuid.UUID,
        alert_type: str,
        details: dict[str, Any] | None = None,
    ) -> NotificationEvent:
        """Send a workflow-level alert (e.g. failure, timeout, completion).

        Dispatched over the ``webhook`` channel by default so that
        external orchestrators can react programmatically.
        """
        subject = f"Workflow alert: {alert_type}"
        body = (
            f"Workflow {workflow_id} triggered alert '{alert_type}'. "
            f"Details: {details or 'none'}"
        )
        return await self.send_notification(
            tenant_id=tenant_id,
            channel="webhook",
            recipient="default",
            subject=subject,
            body=body,
            workflow_case_id=workflow_id,
            payload={"alert_type": alert_type, **(details or {})},
        )

    # ── SLA breach alert ──────────────────────────────────────────

    async def send_sla_breach_alert(
        self,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        sla_metric: str,
        breach_details: dict[str, Any] | None = None,
    ) -> NotificationEvent:
        """Send an urgent SLA-breach notification.

        Dispatched via ``email`` to the escalation team.  The *sla_metric*
        identifies which SLA was breached (e.g. ``response_time``,
        ``resolution_time``).
        """
        subject = f"SLA Breach: {sla_metric} for incident {incident_id}"
        body = (
            f"SLA metric '{sla_metric}' has been breached for incident "
            f"{incident_id}. Breach details: {breach_details or 'N/A'}"
        )
        return await self.send_notification(
            tenant_id=tenant_id,
            channel="email",
            recipient="sla-alerts@company.com",
            subject=subject,
            body=body,
            payload={
                "incident_id": str(incident_id),
                "sla_metric": sla_metric,
                **(breach_details or {}),
            },
        )

    # ── Pending / delivery management ─────────────────────────────

    async def get_pending_notifications(
        self,
        tenant_id: uuid.UUID,
    ) -> list[NotificationEvent]:
        """Return all notifications in ``pending`` status for a tenant."""
        result = await self.db.execute(
            select(NotificationEvent).where(
                NotificationEvent.tenant_id == tenant_id,
                NotificationEvent.status == "pending",
            ).order_by(NotificationEvent.created_at.asc())
        )
        return list(result.scalars().all())

    async def mark_delivered(self, notification_id: uuid.UUID) -> None:
        """Mark a notification as ``delivered``.

        This is intended to be called by delivery confirmation callbacks
        (e.g. webhook acknowledgement, email delivery receipt).
        """
        await self.db.execute(
            update(NotificationEvent)
            .where(NotificationEvent.id == notification_id)
            .values(status="delivered")
        )
        await self.db.flush()
        logger.info("notification_delivered", notification_id=str(notification_id))

    # ── Channel stubs ─────────────────────────────────────────────

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

    # ── Convenience helpers (original) ────────────────────────────

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
