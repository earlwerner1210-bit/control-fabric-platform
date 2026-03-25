"""Standalone escalation rule engine for testing -- no domain-pack schema dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class EscalationAction:
    action: str
    target_level: int
    reason: str
    urgency: str = "normal"


@dataclass
class EscalationResult:
    should_escalate: bool
    current_level: int
    recommended_level: int
    actions: list[EscalationAction] = field(default_factory=list)
    sla_status: str = "within_sla"


class EscalationRuleEngine:
    """Evaluates incident data to determine if escalation is needed."""

    DEFAULT_SLA_TARGETS: dict[str, dict[str, int]] = {
        "P1": {"response": 60, "resolution": 240},
        "P2": {"response": 120, "resolution": 480},
        "P3": {"response": 240, "resolution": 1440},
        "P4": {"response": 480, "resolution": 4320},
    }

    def evaluate(
        self, incident: dict[str, Any],
        sla_targets: dict[str, dict[str, int]] | None = None,
        current_time: datetime | None = None,
    ) -> EscalationResult:
        targets = sla_targets or self.DEFAULT_SLA_TARGETS
        now = current_time or datetime.now(timezone.utc)
        priority = incident.get("priority", "P3")
        current_level = incident.get("escalation_level", 0)
        actions: list[EscalationAction] = []
        sla_status = "within_sla"

        p1 = self._check_p1(priority, current_level)
        if p1:
            actions.append(p1)

        sla_actions, sla_st = self._check_sla(incident, targets, now, current_level)
        actions.extend(sla_actions)
        if sla_st != "within_sla":
            sla_status = sla_st

        vip = self._check_vip(incident, current_level)
        if vip:
            actions.append(vip)

        unack = self._check_unack(incident, targets, now, current_level)
        if unack:
            actions.append(unack)

        recommended = max((a.target_level for a in actions), default=current_level)
        return EscalationResult(
            should_escalate=recommended > current_level,
            current_level=current_level,
            recommended_level=recommended,
            actions=actions, sla_status=sla_status,
        )

    def _check_p1(self, priority: str, level: int) -> EscalationAction | None:
        if priority == "P1" and level < 2:
            return EscalationAction("auto_escalate_to_senior_engineer", 2,
                "P1 incident requires automatic escalation", "critical")
        return None

    def _check_sla(self, incident: dict, targets: dict, now: datetime, level: int):
        actions = []
        sla_status = "within_sla"
        priority = incident.get("priority", "P3")
        target = targets.get(priority)
        if not target:
            return actions, sla_status
        reported_str = incident.get("reported_at")
        if not reported_str:
            return actions, sla_status
        reported = datetime.fromisoformat(reported_str.replace("Z", "+00:00"))
        if reported.tzinfo is None:
            reported = reported.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        elapsed = (now - reported).total_seconds() / 60
        res_target = target.get("resolution", 480)
        pct = elapsed / res_target if res_target > 0 else 1.0
        if pct >= 1.0:
            sla_status = "breached"
            if level < 3:
                actions.append(EscalationAction("escalate_to_operations_manager", 3,
                    f"SLA breached ({elapsed:.0f}/{res_target} min)", "critical"))
        elif pct >= 0.75:
            sla_status = "at_risk"
            if level < 3:
                actions.append(EscalationAction("escalate_to_operations_manager", 3,
                    f"SLA at {pct*100:.0f}% elapsed", "urgent"))
        elif pct >= 0.5:
            sla_status = "at_risk"
            if level < 2:
                actions.append(EscalationAction("escalate_to_senior_engineer", 2,
                    f"SLA at {pct*100:.0f}% elapsed", "urgent"))
        return actions, sla_status

    def _check_vip(self, incident: dict, level: int) -> EscalationAction | None:
        if not incident.get("vip"):
            return None
        total = sum(s.get("customer_count", 0) for s in incident.get("affected_services", []) if isinstance(s, dict))
        if total > 100 and level < 3:
            return EscalationAction("escalate_to_management", 3,
                f"VIP customer with {total} affected services", "critical")
        return None

    def _check_unack(self, incident: dict, targets: dict, now: datetime, level: int):
        if incident.get("acknowledged_at") or incident.get("status") != "open":
            return None
        priority = incident.get("priority", "P3")
        target = targets.get(priority)
        if not target:
            return None
        reported_str = incident.get("reported_at")
        if not reported_str:
            return None
        reported = datetime.fromisoformat(reported_str.replace("Z", "+00:00"))
        if reported.tzinfo is None:
            reported = reported.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        elapsed = (now - reported).total_seconds() / 60
        resp_target = target.get("response", 120)
        remaining = resp_target - elapsed
        if remaining <= 30 and level < 1:
            return EscalationAction("escalate_to_team_lead", 1,
                f"Response deadline within {remaining:.0f} min, unacknowledged", "urgent")
        return None
