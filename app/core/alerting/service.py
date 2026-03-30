"""
Alert service — notifies operators when CRITICAL cases are detected.
Channels: Slack webhook, email (SMTP), generic webhook.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

import httpx

logger = logging.getLogger(__name__)


class AlertChannel:
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"


class AlertPayload:
    def __init__(
        self,
        severity: str,
        title: str,
        case_id: str,
        affected_planes: list[str],
        remediation: list[str],
        tenant_id: str = "default",
    ) -> None:
        self.severity = severity
        self.title = title
        self.case_id = case_id
        self.affected_planes = affected_planes
        self.remediation = remediation
        self.tenant_id = tenant_id


class AlertService:
    """Sends alerts when governance cases breach configured severity thresholds."""

    def __init__(self) -> None:
        self._configs: list[dict] = []
        self._history: list[dict] = []
        self._load_env_configs()

    def add_config(
        self,
        channel: str,
        destination: str,
        min_severity: str = "critical",
        name: str = "",
    ) -> None:
        self._configs.append(
            {
                "channel": channel,
                "destination": destination,
                "min_severity": min_severity,
                "name": name or f"{channel}-{len(self._configs)}",
            }
        )

    async def alert(self, payload: AlertPayload) -> list[dict]:
        """Send alert to all configured channels that match the severity threshold."""
        severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        results = []
        for config in self._configs:
            if severity_rank.get(payload.severity, 0) >= severity_rank.get(
                config["min_severity"], 4
            ):
                result = await self._dispatch(config, payload)
                results.append(result)
                self._history.append(
                    {
                        "config": config["name"],
                        "severity": payload.severity,
                        "case_id": payload.case_id,
                        "success": result.get("success", False),
                    }
                )
        return results

    async def _dispatch(self, config: dict, payload: AlertPayload) -> dict:
        try:
            if config["channel"] == AlertChannel.SLACK:
                return await self._send_slack(config["destination"], payload)
            if config["channel"] == AlertChannel.EMAIL:
                return self._send_email(config["destination"], payload)
            if config["channel"] == AlertChannel.WEBHOOK:
                return await self._send_webhook(config["destination"], payload)
            return {"success": False, "error": f"Unknown channel: {config['channel']}"}
        except Exception as e:
            logger.error("Alert dispatch failed: %s — %s", config["name"], e)
            return {"success": False, "error": str(e)}

    async def _send_slack(self, webhook_url: str, payload: AlertPayload) -> dict:
        emoji = {
            "critical": ":red_circle:",
            "high": ":orange_circle:",
            "medium": ":yellow_circle:",
            "low": ":white_circle:",
        }.get(payload.severity, ":grey_question:")
        message = {
            "text": f"{emoji} *[{payload.severity.upper()}] Governance case detected*",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} {payload.severity.upper()}: Governance Alert",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Case:*\n{payload.title}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Planes:*\n{', '.join(payload.affected_planes)}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Case ID:*\n`{payload.case_id[:12]}...`",
                        },
                        {"type": "mrkdwn", "text": f"*Tenant:*\n{payload.tenant_id}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Suggested action:*\n"
                            f"{payload.remediation[0] if payload.remediation else 'Review in operator console'}"
                        ),
                    },
                },
            ],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=message)
            return {"success": resp.status_code == 200, "status_code": resp.status_code}

    def _send_email(self, to_address: str, payload: AlertPayload) -> dict:
        host = os.getenv("SMTP_HOST", "")
        if not host:
            return {"success": False, "error": "SMTP not configured"}
        msg = EmailMessage()
        msg["Subject"] = f"[{payload.severity.upper()}] Control Fabric Alert: {payload.title}"
        msg["From"] = os.getenv("SMTP_USER", "alerts@platform.local")
        msg["To"] = to_address
        msg.set_content(
            f"Control Fabric Platform — Governance Alert\n"
            f"Severity: {payload.severity.upper()}\n"
            f"Case: {payload.title}\n"
            f"Case ID: {payload.case_id}\n"
            f"Planes: {', '.join(payload.affected_planes)}\n"
            f"Suggested action: "
            f"{payload.remediation[0] if payload.remediation else 'Review in operator console'}\n"
        )
        try:
            with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587"))) as s:
                s.starttls()
                s.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASSWORD", ""))
                s.send_message(msg)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _send_webhook(self, url: str, payload: AlertPayload) -> dict:
        body = {
            "severity": payload.severity,
            "title": payload.title,
            "case_id": payload.case_id,
            "affected_planes": payload.affected_planes,
            "remediation": payload.remediation,
            "tenant_id": payload.tenant_id,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=body)
            return {"success": resp.status_code < 300, "status_code": resp.status_code}

    def _load_env_configs(self) -> None:
        if url := os.getenv("SLACK_WEBHOOK_URL"):
            self.add_config(AlertChannel.SLACK, url, "critical", "slack-critical")
        if to := os.getenv("ALERT_EMAIL_TO"):
            self.add_config(AlertChannel.EMAIL, to, "critical", "email-critical")

    def get_history(self) -> list[dict]:
        return list(self._history)


alert_service = AlertService()
