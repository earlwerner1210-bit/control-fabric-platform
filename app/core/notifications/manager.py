"""
Notification Manager

Manages user notification preferences and dispatches notifications.
Integrates with the alerting service for delivery.
"""

from __future__ import annotations

import logging

from app.core.notifications.preferences import (
    NotificationChannel,
    NotificationEvent,
    NotificationPreference,
    NotificationRecord,
)

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Manages notification preferences and dispatches platform notifications.
    """

    def __init__(self) -> None:
        self._preferences: list[NotificationPreference] = []
        self._records: list[NotificationRecord] = []

    def set_preference(
        self,
        user_id: str,
        tenant_id: str,
        event: NotificationEvent,
        channel: NotificationChannel,
        destination: str,
        enabled: bool = True,
        min_severity: str = "critical",
    ) -> NotificationPreference:
        # Remove existing preference for same user+event+channel
        self._preferences = [
            p
            for p in self._preferences
            if not (p.user_id == user_id and p.event == event and p.channel == channel)
        ]
        pref = NotificationPreference(
            user_id=user_id,
            tenant_id=tenant_id,
            event=event,
            channel=channel,
            destination=destination,
            enabled=enabled,
            min_severity=min_severity,
        )
        self._preferences.append(pref)
        logger.info(
            "Notification preference set: user=%s event=%s channel=%s",
            user_id,
            event.value,
            channel.value,
        )
        return pref

    def get_preferences(
        self, user_id: str, tenant_id: str | None = None
    ) -> list[NotificationPreference]:
        prefs = [p for p in self._preferences if p.user_id == user_id]
        if tenant_id:
            prefs = [p for p in prefs if p.tenant_id == tenant_id]
        return prefs

    def get_subscribers(
        self, event: NotificationEvent, tenant_id: str | None = None
    ) -> list[NotificationPreference]:
        prefs = [p for p in self._preferences if p.event == event and p.enabled]
        if tenant_id:
            prefs = [p for p in prefs if p.tenant_id == tenant_id]
        return prefs

    async def notify(
        self,
        event: NotificationEvent,
        tenant_id: str,
        subject: str,
        body: str,
        severity: str = "high",
    ) -> list[NotificationRecord]:
        subscribers = self.get_subscribers(event, tenant_id)
        records = []
        for pref in subscribers:
            if not self._severity_meets_threshold(severity, pref.min_severity):
                continue
            record = NotificationRecord(
                user_id=pref.user_id,
                tenant_id=tenant_id,
                event=event.value,
                channel=pref.channel.value,
                destination=pref.destination,
                subject=subject,
                body_preview=body[:200],
            )
            try:
                await self._dispatch(pref, subject, body)
                record.delivered = True
            except Exception as e:
                record.error = str(e)
                logger.error("Notification dispatch failed: %s", e)
            self._records.append(record)
            records.append(record)
        return records

    async def _dispatch(self, pref: NotificationPreference, subject: str, body: str) -> None:
        from app.core.alerting.service import AlertChannel, AlertPayload, AlertService

        svc = AlertService()
        if pref.channel == NotificationChannel.EMAIL:
            svc.add_config(AlertChannel.EMAIL, pref.destination, pref.min_severity)
        elif pref.channel == NotificationChannel.SLACK:
            svc.add_config(AlertChannel.SLACK, pref.destination, pref.min_severity)
        elif pref.channel == NotificationChannel.WEBHOOK:
            svc.add_config(AlertChannel.WEBHOOK, pref.destination, pref.min_severity)
        else:
            return  # IN_APP stored in records only
        payload = AlertPayload(
            severity=pref.min_severity,
            title=subject,
            case_id="notification",
            affected_planes=[],
            remediation=[body[:200]],
            tenant_id=pref.tenant_id,
        )
        await svc.alert(payload)

    def get_notification_history(
        self, user_id: str | None = None, limit: int = 50
    ) -> list[NotificationRecord]:
        records = self._records
        if user_id:
            records = [r for r in records if r.user_id == user_id]
        return records[-limit:]

    def delete_preference(self, pref_id: str, user_id: str) -> bool:
        before = len(self._preferences)
        self._preferences = [
            p for p in self._preferences if not (p.pref_id == pref_id and p.user_id == user_id)
        ]
        return len(self._preferences) < before

    @staticmethod
    def _severity_meets_threshold(severity: str, threshold: str) -> bool:
        rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        return rank.get(severity, 0) >= rank.get(threshold, 4)


# Singleton
notification_manager = NotificationManager()
