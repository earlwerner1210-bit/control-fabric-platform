"""
Telco Ops Pack - Incident rule engine that evaluates state transitions,
SLA compliance, escalation needs, and operational evidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.domain_packs.telco_ops.parsers.incident_parser import IncidentParser
from app.domain_packs.telco_ops.schemas.telco_schemas import (
    EscalationTier,
    IncidentObject,
    IncidentSeverity,
    IncidentStatus,
    ServiceStateObject,
    SLA_TARGETS,
)


# ---------------------------------------------------------------------------
# Valid state transitions (from -> set of valid targets)
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, set[str]] = {
    IncidentStatus.open.value: {IncidentStatus.acknowledged.value},
    IncidentStatus.acknowledged.value: {IncidentStatus.investigating.value},
    IncidentStatus.investigating.value: {IncidentStatus.resolving.value},
    IncidentStatus.resolving.value: {IncidentStatus.resolved.value},
    IncidentStatus.resolved.value: {IncidentStatus.closed.value},
    IncidentStatus.closed.value: set(),  # terminal state
}


# ---------------------------------------------------------------------------
# Incident Rule Engine
# ---------------------------------------------------------------------------

class IncidentRuleEngine:
    """Evaluates incident state, SLA compliance, and next-action
    recommendations for telco operations incidents.
    """

    def evaluate_next_action(
        self,
        incident: IncidentObject,
        service_state: Optional[ServiceStateObject] = None,
    ) -> dict[str, Any]:
        """Determine the recommended next action for an incident.

        Returns a dict with:
            - ``action``: recommended next step
            - ``reason``: explanation for the recommendation
            - ``escalation_required``: bool
            - ``details``: supporting data (SLA info, validation, etc.)
        """
        details: dict[str, Any] = {}

        # Current status as string
        status = incident.status
        if isinstance(status, IncidentStatus):
            status = status.value

        # -- SLA compliance --------------------------------------------------
        sla_result = self.check_sla_compliance(incident)
        details["sla"] = sla_result

        # -- Escalation check ------------------------------------------------
        elapsed = self._minutes_since_reported(incident)
        esc_required, esc_tier, esc_reason = self.check_escalation_required(
            incident, elapsed
        )
        details["escalation"] = {
            "required": esc_required,
            "tier": esc_tier,
            "reason": esc_reason,
            "elapsed_minutes": elapsed,
        }

        # -- Owner assigned --------------------------------------------------
        owner_ok, owner_reason = self.check_owner_assigned(incident)
        details["owner_assigned"] = {"passed": owner_ok, "reason": owner_reason}

        # -- Evidence check --------------------------------------------------
        evidence_ok, evidence_reason = self.check_operational_evidence(incident)
        details["evidence"] = {"passed": evidence_ok, "reason": evidence_reason}

        # -- Determine recommended action ------------------------------------
        action, reason = self._determine_action(
            status, sla_result, esc_required, esc_tier, owner_ok, evidence_ok, service_state,
        )

        return {
            "action": action,
            "reason": reason,
            "escalation_required": esc_required,
            "details": details,
        }

    # ------------------------------------------------------------------
    # Individual rule methods
    # ------------------------------------------------------------------

    @staticmethod
    def validate_state_transition(
        current: str | IncidentStatus,
        proposed: str | IncidentStatus,
    ) -> tuple[bool, str]:
        """Validate whether a state transition is allowed.

        Returns (valid, reason).
        """
        current_val = current.value if isinstance(current, IncidentStatus) else current
        proposed_val = proposed.value if isinstance(proposed, IncidentStatus) else proposed

        allowed = _VALID_TRANSITIONS.get(current_val)
        if allowed is None:
            return False, f"Unknown current state: {current_val}"
        if proposed_val in allowed:
            return True, f"Transition {current_val} -> {proposed_val} is valid"
        if proposed_val == current_val:
            return False, f"Incident is already in state '{current_val}'"
        return False, (
            f"Transition {current_val} -> {proposed_val} is not allowed. "
            f"Valid targets: {', '.join(sorted(allowed)) if allowed else 'none (terminal state)'}"
        )

    @staticmethod
    def check_owner_assigned(incident: IncidentObject) -> tuple[bool, str]:
        """Check that the incident has been acknowledged (implying owner assignment).

        An incident past the 'open' state should have an acknowledged_at timestamp.
        """
        status = incident.status
        if isinstance(status, IncidentStatus):
            status = status.value

        if status == IncidentStatus.open.value:
            return True, "Incident is still open - owner assignment not yet required"

        if incident.acknowledged_at is not None:
            return True, "Incident has been acknowledged with timestamp"
        return False, "Incident is past 'open' state but has no acknowledged_at timestamp"

    @staticmethod
    def check_operational_evidence(incident: IncidentObject) -> tuple[bool, str]:
        """Check that resolved/closed incidents have operational evidence.

        Expects root_cause and resolution_summary to be populated for
        resolved or closed incidents.
        """
        status = incident.status
        if isinstance(status, IncidentStatus):
            status = status.value

        terminal_states = {IncidentStatus.resolved.value, IncidentStatus.closed.value}
        if status not in terminal_states:
            return True, "Operational evidence not yet required at this stage"

        issues: list[str] = []
        if not incident.root_cause:
            issues.append("root_cause is missing")
        if not incident.resolution_summary:
            issues.append("resolution_summary is missing")
        if issues:
            return False, f"Resolved incident missing evidence: {', '.join(issues)}"
        return True, "Root cause and resolution summary are present"

    @staticmethod
    def check_sla_compliance(incident: IncidentObject) -> dict[str, Any]:
        """Check whether the incident is within SLA response and resolution targets.

        Returns a dict with:
            - ``within_sla``: bool (True if both response and resolution are within target)
            - ``response_breach``: bool
            - ``resolution_breach``: bool
            - ``breach_minutes``: int (worst breach in minutes, 0 if compliant)
        """
        severity = incident.severity
        if isinstance(severity, IncidentSeverity):
            severity = severity.value

        targets = SLA_TARGETS.get(severity, SLA_TARGETS[IncidentSeverity.P4.value])
        now = datetime.utcnow()

        response_breach = False
        resolution_breach = False
        breach_minutes = 0

        # Response SLA: time between reported_at and acknowledged_at
        if incident.reported_at:
            ack_time = incident.acknowledged_at or now
            response_elapsed = (ack_time - incident.reported_at).total_seconds() / 60.0
            if response_elapsed > targets["response_minutes"]:
                response_breach = True
                breach_minutes = max(
                    breach_minutes,
                    int(response_elapsed - targets["response_minutes"]),
                )

            # Resolution SLA: time between reported_at and resolved_at
            resolve_time = incident.resolved_at or now
            resolution_elapsed = (resolve_time - incident.reported_at).total_seconds() / 60.0
            if resolution_elapsed > targets["resolution_minutes"]:
                resolution_breach = True
                breach_minutes = max(
                    breach_minutes,
                    int(resolution_elapsed - targets["resolution_minutes"]),
                )

        within_sla = not response_breach and not resolution_breach

        return {
            "within_sla": within_sla,
            "response_breach": response_breach,
            "resolution_breach": resolution_breach,
            "breach_minutes": breach_minutes,
        }

    @staticmethod
    def check_escalation_required(
        incident: IncidentObject,
        elapsed_minutes: float,
    ) -> tuple[bool, str, str]:
        """Determine whether escalation is required based on elapsed time.

        Returns (required, tier, reason).
        """
        severity = incident.severity
        if isinstance(severity, IncidentSeverity):
            severity = severity.value

        status = incident.status
        if isinstance(status, IncidentStatus):
            status = status.value

        # No escalation for resolved / closed
        if status in {IncidentStatus.resolved.value, IncidentStatus.closed.value}:
            return False, "", "Incident is resolved or closed - no escalation needed"

        rules = IncidentParser.extract_escalation_rules(severity)
        # Find the highest tier whose threshold has been exceeded
        applicable_tier = ""
        applicable_reason = ""
        for rule in sorted(rules, key=lambda r: r.time_threshold_minutes, reverse=True):
            if elapsed_minutes >= rule.time_threshold_minutes and rule.auto_escalate:
                tier_val = rule.tier
                if isinstance(tier_val, EscalationTier):
                    tier_val = tier_val.value
                applicable_tier = tier_val
                applicable_reason = rule.escalation_reason
                break

        if applicable_tier:
            return True, applicable_tier, applicable_reason
        return False, "", "No escalation threshold breached"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _minutes_since_reported(incident: IncidentObject) -> float:
        """Calculate minutes elapsed since the incident was reported."""
        if not incident.reported_at:
            return 0.0
        now = datetime.utcnow()
        delta = now - incident.reported_at
        return delta.total_seconds() / 60.0

    @staticmethod
    def _determine_action(
        status: str,
        sla_result: dict[str, Any],
        esc_required: bool,
        esc_tier: str,
        owner_ok: bool,
        evidence_ok: bool,
        service_state: Optional[ServiceStateObject],
    ) -> tuple[str, str]:
        """Determine the single best next action based on collected signals."""

        # Escalation overrides everything if it is required
        if esc_required:
            return (
                f"escalate_to_{esc_tier}",
                f"Escalation required to {esc_tier} based on elapsed time and severity",
            )

        # SLA breach is next priority
        if sla_result.get("response_breach") and status == IncidentStatus.open.value:
            return "acknowledge_immediately", "Response SLA breached - acknowledge now"

        if sla_result.get("resolution_breach"):
            return "expedite_resolution", (
                f"Resolution SLA breached by {sla_result.get('breach_minutes', 0)} minutes"
            )

        # Status-based recommendations
        if status == IncidentStatus.open.value:
            if not owner_ok:
                return "assign_owner", "Incident needs an owner before it can progress"
            return "acknowledge", "Incident is open and awaiting acknowledgement"

        if status == IncidentStatus.acknowledged.value:
            return "begin_investigation", "Incident acknowledged - start investigation"

        if status == IncidentStatus.investigating.value:
            # If service state shows ongoing impact, prioritise
            if service_state and service_state.current_status in ("outage", "degraded"):
                return "prioritise_mitigation", (
                    f"Service '{service_state.service_name}' is {service_state.current_status} "
                    "- prioritise mitigation before root cause"
                )
            return "continue_investigation", "Investigation in progress"

        if status == IncidentStatus.resolving.value:
            return "confirm_resolution", "Verify fix and mark as resolved"

        if status == IncidentStatus.resolved.value:
            if not evidence_ok:
                return "add_evidence", "Incident resolved but missing root cause or resolution summary"
            return "close_incident", "Incident resolved with evidence - ready to close"

        if status == IncidentStatus.closed.value:
            return "no_action", "Incident is closed"

        return "review", "Unable to determine next action - manual review required"
