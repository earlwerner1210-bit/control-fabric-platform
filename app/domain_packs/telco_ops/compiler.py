"""Telco Ops compiler — compile parsed artefacts into control objects."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain_packs.telco_ops.schemas import (
    EscalationLevel,
    IncidentSeverity,
    IncidentState,
    ParsedIncident,
    ParsedRunbook,
    ServiceState,
    ServiceStateObject,
)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class TelcoCompileResult:
    """Container for all compiled control objects."""

    incident_state: dict = field(default_factory=dict)
    service_states: list[dict] = field(default_factory=list)
    escalation_rules: list[dict] = field(default_factory=list)
    ownership_rules: list[dict] = field(default_factory=list)
    next_action_context: dict = field(default_factory=dict)
    control_object_payloads: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Severity / state helpers
# ---------------------------------------------------------------------------

_SEVERITY_ESCALATION_MAP: dict[str, str] = {
    "p1": EscalationLevel.l3.value,
    "p2": EscalationLevel.l2.value,
    "p3": EscalationLevel.l1.value,
    "p4": EscalationLevel.l1.value,
}

_SEVERITY_OWNER_MAP: dict[str, str] = {
    "p1": "on_call_engineer",
    "p2": "engineering_team",
    "p3": "service_desk",
    "p4": "service_desk",
}

_STATE_OWNER_OVERRIDE: dict[str, str] = {
    EscalationLevel.l3.value: "senior_engineering",
    EscalationLevel.management.value: "service_delivery_manager",
}

_VALID_ACTIONS_FOR_STATE: dict[str, list[str]] = {
    "new": ["investigate", "assign_engineer", "escalate"],
    "acknowledged": ["investigate", "dispatch", "escalate"],
    "investigating": ["dispatch", "resolve", "escalate", "monitor"],
    "resolved": ["close", "reopen", "monitor"],
    "closed": ["reopen"],
}


# ---------------------------------------------------------------------------
# TelcoCompiler
# ---------------------------------------------------------------------------


class TelcoCompiler:
    """Compile telco operations artefacts into control objects."""

    # -- public entry point -------------------------------------------------

    def compile(
        self,
        incident: ParsedIncident,
        service_state: ServiceStateObject | None = None,
        runbook: ParsedRunbook | None = None,
    ) -> TelcoCompileResult:
        """Full compilation pipeline."""
        incident_state = self.compile_incident_state(incident)
        service_states = self.compile_service_states(incident, service_state)
        escalation_rules = self.compile_escalation_rules(incident)
        ownership_rules = self.compile_ownership_rules(incident)
        next_action_ctx = self.compile_next_action_context(incident, service_state, runbook)

        # Aggregate all payloads for downstream consumers
        control_objects: list[dict] = []
        control_objects.append({"type": "incident_state", "payload": incident_state})
        for ss in service_states:
            control_objects.append({"type": "service_state", "payload": ss})
        for er in escalation_rules:
            control_objects.append({"type": "escalation_rule", "payload": er})
        for ow in ownership_rules:
            control_objects.append({"type": "ownership_rule", "payload": ow})
        control_objects.append({"type": "next_action_context", "payload": next_action_ctx})

        return TelcoCompileResult(
            incident_state=incident_state,
            service_states=service_states,
            escalation_rules=escalation_rules,
            ownership_rules=ownership_rules,
            next_action_context=next_action_ctx,
            control_object_payloads=control_objects,
        )

    # -- incident state -----------------------------------------------------

    def compile_incident_state(self, incident: ParsedIncident) -> dict:
        """Generate incident_state control object."""
        is_active = incident.state not in (IncidentState.resolved, IncidentState.closed)
        requires_attention = (
            incident.severity in (IncidentSeverity.p1, IncidentSeverity.p2)
            and is_active
        )
        return {
            "incident_id": incident.incident_id,
            "severity": incident.severity.value,
            "state": incident.state.value,
            "is_active": is_active,
            "requires_immediate_attention": requires_attention,
            "affected_services": incident.affected_services,
            "assigned_to": incident.assigned_to,
            "title": incident.title,
            "tags": incident.tags,
            "created_at": incident.created_at,
            "updated_at": incident.updated_at,
        }

    # -- service states -----------------------------------------------------

    def compile_service_states(
        self,
        incident: ParsedIncident,
        service_state: ServiceStateObject | None = None,
    ) -> list[dict]:
        """Generate service_state control objects for affected services."""
        results: list[dict] = []

        if service_state is not None:
            results.append({
                "service_id": service_state.service_id,
                "service_name": service_state.service_name,
                "state": service_state.state.value,
                "affected_customers": service_state.affected_customers,
                "impact_level": service_state.impact_level.value,
                "recovery_eta_minutes": service_state.recovery_eta_minutes,
                "dependencies": service_state.dependencies,
                "linked_incident": incident.incident_id,
            })

        # Placeholder entries for services mentioned in the incident but
        # not represented by the explicit service_state argument.
        known = {service_state.service_name} if service_state else set()
        for svc_name in incident.affected_services:
            if svc_name not in known:
                results.append({
                    "service_id": f"svc-{svc_name}",
                    "service_name": svc_name,
                    "state": "unknown",
                    "affected_customers": 0,
                    "impact_level": "unknown",
                    "recovery_eta_minutes": None,
                    "dependencies": [],
                    "linked_incident": incident.incident_id,
                })

        return results

    # -- escalation rules ---------------------------------------------------

    def compile_escalation_rules(self, incident: ParsedIncident) -> list[dict]:
        """Generate escalation_rule control objects based on severity and state."""
        rules: list[dict] = []

        # Base severity-driven rule
        esc_level = _SEVERITY_ESCALATION_MAP.get(incident.severity.value, EscalationLevel.l1.value)
        rules.append({
            "rule": "severity_based_escalation",
            "incident_id": incident.incident_id,
            "severity": incident.severity.value,
            "escalation_level": esc_level,
            "trigger": "incident_created",
            "auto": incident.severity in (IncidentSeverity.p1,),
        })

        # State-based rule: stale investigating
        if incident.state == IncidentState.investigating:
            rules.append({
                "rule": "stale_investigation_escalation",
                "incident_id": incident.incident_id,
                "escalation_level": EscalationLevel.l2.value,
                "trigger": "investigation_exceeds_threshold",
                "threshold_minutes": 60 if incident.severity == IncidentSeverity.p1 else 240,
                "auto": False,
            })

        # Outage service escalation
        if any(svc in ("core_network", "voice_platform", "billing") for svc in incident.affected_services):
            rules.append({
                "rule": "critical_service_escalation",
                "incident_id": incident.incident_id,
                "escalation_level": EscalationLevel.l3.value,
                "trigger": "critical_service_affected",
                "affected_services": incident.affected_services,
                "auto": True,
            })

        return rules

    # -- ownership rules ----------------------------------------------------

    def compile_ownership_rules(self, incident: ParsedIncident) -> list[dict]:
        """Generate ownership assignment rules."""
        owner = _SEVERITY_OWNER_MAP.get(incident.severity.value, "service_desk")
        rules: list[dict] = [
            {
                "rule": "default_ownership",
                "incident_id": incident.incident_id,
                "severity": incident.severity.value,
                "primary_owner": owner,
                "time_to_own_minutes": 5 if incident.severity == IncidentSeverity.p1 else 15,
            }
        ]

        # If unassigned, add an alert rule
        if not incident.assigned_to:
            rules.append({
                "rule": "unassigned_alert",
                "incident_id": incident.incident_id,
                "alert": True,
                "message": f"Incident {incident.incident_id} has no assigned owner",
            })

        return rules

    # -- next-action context ------------------------------------------------

    def compile_next_action_context(
        self,
        incident: ParsedIncident,
        service_state: ServiceStateObject | None = None,
        runbook: ParsedRunbook | None = None,
    ) -> dict:
        """Build context object for next-action determination."""
        valid_actions = _VALID_ACTIONS_FOR_STATE.get(incident.state.value, ["investigate"])

        has_outage = False
        if service_state and service_state.state == ServiceState.outage:
            has_outage = True

        return {
            "incident_id": incident.incident_id,
            "current_state": incident.state.value,
            "severity": incident.severity.value,
            "valid_actions": valid_actions,
            "has_assigned_owner": bool(incident.assigned_to),
            "has_runbook": runbook is not None,
            "runbook_id": runbook.runbook_id if runbook else None,
            "runbook_title": runbook.title if runbook else None,
            "service_outage": has_outage,
            "service_state": service_state.state.value if service_state else None,
            "affected_services": incident.affected_services,
            "recovery_eta_minutes": service_state.recovery_eta_minutes if service_state else None,
            "tags": incident.tags,
        }
