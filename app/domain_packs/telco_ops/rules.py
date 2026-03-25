"""Telco Ops business rules – escalation, action, ownership."""

from __future__ import annotations

import uuid
from typing import Any

from app.domain_packs.telco_ops.schemas import (
    EscalationDecision,
    EscalationLevel,
    IncidentSeverity,
    IncidentState,
    NextAction,
    ParsedIncident,
    ServiceState,
)
from app.schemas.validation import RuleResult


class EscalationRuleEngine:
    """Determine escalation requirements for incidents."""

    def evaluate(
        self,
        incident: ParsedIncident,
        service_state: ServiceState | None = None,
        sla_breached: bool = False,
        repeat_count: int = 0,
    ) -> EscalationDecision:
        should_escalate = False
        level: EscalationLevel | None = None
        reason = ""

        # Rule 1: Severity-based escalation
        if incident.severity in (IncidentSeverity.p1,):
            should_escalate = True
            level = EscalationLevel.l3
            reason = "P1 incident requires immediate L3 escalation"
        elif incident.severity == IncidentSeverity.p2:
            should_escalate = True
            level = EscalationLevel.l2
            reason = "P2 incident requires L2 escalation"

        # Rule 2: SLA breach escalation
        if sla_breached:
            should_escalate = True
            level = EscalationLevel.management if level == EscalationLevel.l3 else EscalationLevel.l3
            reason = f"SLA breach detected. {reason}"

        # Rule 3: Repeated incident
        if repeat_count >= 3:
            should_escalate = True
            if level is None or level.value < EscalationLevel.l2.value:
                level = EscalationLevel.l2
            reason = f"Repeated incident (count: {repeat_count}). {reason}"

        # Rule 4: Cross-domain impact
        if service_state == ServiceState.outage:
            should_escalate = True
            level = EscalationLevel.l3
            reason = f"Service outage detected. {reason}"

        owner = self._determine_owner(level) if should_escalate else ""

        return EscalationDecision(
            escalate=should_escalate,
            level=level,
            owner=owner,
            reason=reason.strip(),
        )

    def _determine_owner(self, level: EscalationLevel | None) -> str:
        owners = {
            EscalationLevel.l1: "service_desk",
            EscalationLevel.l2: "engineering_team",
            EscalationLevel.l3: "senior_engineering",
            EscalationLevel.management: "service_delivery_manager",
        }
        return owners.get(level, "unassigned") if level else "unassigned"


class ActionRuleEngine:
    """Determine next best action for an incident."""

    VALID_TRANSITIONS: dict[str, list[str]] = {
        "new": ["investigate", "assign_engineer", "escalate"],
        "acknowledged": ["investigate", "dispatch", "escalate"],
        "investigating": ["dispatch", "resolve", "escalate", "monitor"],
        "resolved": ["close", "reopen", "monitor"],
        "closed": ["reopen"],
    }

    def evaluate(
        self,
        incident_state: IncidentState,
        service_state: ServiceState | None = None,
        has_runbook: bool = False,
        has_assigned_owner: bool = False,
    ) -> NextAction:
        valid_actions = self.VALID_TRANSITIONS.get(incident_state.value, ["investigate"])

        # Determine best action
        if incident_state == IncidentState.new:
            if not has_assigned_owner:
                action = "assign_engineer"
                reason = "Incident not yet assigned"
            else:
                action = "investigate"
                reason = "Begin investigation"
        elif incident_state == IncidentState.investigating:
            if service_state == ServiceState.outage:
                action = "escalate"
                reason = "Service outage requires escalation"
            elif has_runbook:
                action = "dispatch"
                reason = "Runbook available, dispatch for resolution"
            else:
                action = "investigate"
                reason = "Continue investigation"
        elif incident_state == IncidentState.resolved:
            action = "close"
            reason = "Incident resolved, ready for closure"
        else:
            action = valid_actions[0] if valid_actions else "investigate"
            reason = "Default action for current state"

        return NextAction(
            action=action,
            reason=reason,
            priority="high" if service_state == ServiceState.outage else "normal",
        )


class OwnershipRuleEngine:
    """Determine incident ownership based on service and severity."""

    def determine_owner(
        self,
        severity: IncidentSeverity,
        affected_services: list[str],
        escalation_level: EscalationLevel | None = None,
    ) -> str:
        if escalation_level == EscalationLevel.management:
            return "service_delivery_manager"
        if escalation_level == EscalationLevel.l3:
            return "senior_engineering"
        if severity == IncidentSeverity.p1:
            return "on_call_engineer"
        if severity == IncidentSeverity.p2:
            return "engineering_team"
        return "service_desk"
