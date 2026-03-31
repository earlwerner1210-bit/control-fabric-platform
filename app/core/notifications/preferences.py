"""
Notification Preferences

Per-user, per-tenant notification subscriptions.
Users choose which events they want to be notified about
and by which channel (email, Slack, webhook).

Events:
  critical_case_detected     — CRITICAL severity reconciliation case
  case_assigned_to_me        — case assigned to the user
  exception_decision         — exception approved or rejected
  release_blocked            — action blocked by the gate
  release_approved           — action released with evidence
  sla_breach                 — case breaches SLA without resolution
  health_score_drop          — tenant health score drops >15 points
  weekly_digest              — scheduled weekly governance summary
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class NotificationEvent(str, Enum):
    CRITICAL_CASE_DETECTED = "critical_case_detected"
    CASE_ASSIGNED_TO_ME = "case_assigned_to_me"
    EXCEPTION_DECISION = "exception_decision"
    RELEASE_BLOCKED = "release_blocked"
    RELEASE_APPROVED = "release_approved"
    SLA_BREACH = "sla_breach"
    HEALTH_SCORE_DROP = "health_score_drop"
    WEEKLY_DIGEST = "weekly_digest"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


@dataclass
class NotificationPreference:
    pref_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    tenant_id: str = "default"
    event: NotificationEvent = NotificationEvent.CRITICAL_CASE_DETECTED
    channel: NotificationChannel = NotificationChannel.EMAIL
    destination: str = ""  # email address, slack webhook, or webhook URL
    enabled: bool = True
    min_severity: str = "critical"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class NotificationRecord:
    notification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    tenant_id: str = "default"
    event: str = ""
    channel: str = ""
    destination: str = ""
    subject: str = ""
    body_preview: str = ""
    sent_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    delivered: bool = False
    error: str = ""
