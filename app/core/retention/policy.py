"""
Data retention policy enforcement.
Configurable per data type. Celery task runs cleanup on schedule.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class RetentionRule:
    data_type: str
    retain_days: int
    soft_delete: bool = True
    description: str = ""


DEFAULT_RETENTION_RULES = [
    RetentionRule(
        "evidence_packages",
        retain_days=2555,
        description="7 years — financial/compliance standard",
    ),
    RetentionRule("audit_log", retain_days=2555, description="7 years — regulatory requirement"),
    RetentionRule(
        "reconciliation_cases",
        retain_days=365,
        description="1 year — operational",
    ),
    RetentionRule(
        "exception_requests",
        retain_days=730,
        description="2 years — governance record",
    ),
    RetentionRule(
        "control_objects",
        retain_days=1825,
        description="5 years — asset lifecycle",
    ),
    RetentionRule("access_log", retain_days=365, description="1 year — security audit"),
    RetentionRule("onboarding_sessions", retain_days=90, description="3 months — temporary"),
]


class RetentionPolicyManager:
    def __init__(self, rules: list[RetentionRule] | None = None) -> None:
        self._rules = {r.data_type: r for r in (rules or DEFAULT_RETENTION_RULES)}

    def get_cutoff(self, data_type: str) -> datetime | None:
        rule = self._rules.get(data_type)
        if not rule:
            return None
        return datetime.now(UTC) - timedelta(days=rule.retain_days)

    def get_all_rules(self) -> list[dict]:
        return [
            {
                "data_type": r.data_type,
                "retain_days": r.retain_days,
                "retain_years": round(r.retain_days / 365, 1),
                "soft_delete": r.soft_delete,
                "description": r.description,
                "cutoff_date": (datetime.now(UTC) - timedelta(days=r.retain_days)).isoformat(),
            }
            for r in self._rules.values()
        ]

    def update_rule(self, data_type: str, retain_days: int) -> RetentionRule:
        rule = RetentionRule(data_type=data_type, retain_days=retain_days)
        self._rules[data_type] = rule
        return rule

    def run_cleanup_simulation(self) -> dict:
        """Simulate what would be deleted without actually deleting anything."""
        result = {}
        for data_type, rule in self._rules.items():
            cutoff = datetime.now(UTC) - timedelta(days=rule.retain_days)
            result[data_type] = {
                "cutoff": cutoff.isoformat(),
                "retain_days": rule.retain_days,
                "action": "soft_delete" if rule.soft_delete else "hard_delete",
            }
        return result
