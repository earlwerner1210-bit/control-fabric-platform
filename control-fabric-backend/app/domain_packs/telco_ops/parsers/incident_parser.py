"""
Telco Ops Pack - Parsers for incidents, state transitions, service
states, and escalation rule extraction.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain_packs.telco_ops.schemas.telco_schemas import (
    EscalationRuleObject,
    EscalationTier,
    IncidentObject,
    IncidentSeverity,
    IncidentStateObject,
    IncidentStatus,
    ServiceImpact,
    ServiceStateObject,
)

# ---------------------------------------------------------------------------
# Default escalation rule definitions
# ---------------------------------------------------------------------------

_DEFAULT_ESCALATION_RULES: dict[str, list[dict[str, Any]]] = {
    IncidentSeverity.P1.value: [
        {
            "tier": EscalationTier.L1,
            "time_threshold_minutes": 0,
            "auto_escalate": True,
            "notify_roles": ["noc_operator"],
            "escalation_reason": "P1 incident opened - immediate L1 assignment",
        },
        {
            "tier": EscalationTier.L2,
            "time_threshold_minutes": 15,
            "auto_escalate": True,
            "notify_roles": ["noc_lead", "platform_engineer"],
            "escalation_reason": "P1 not resolved within 15 minutes - escalate to L2",
        },
        {
            "tier": EscalationTier.L3,
            "time_threshold_minutes": 30,
            "auto_escalate": True,
            "notify_roles": ["senior_engineer", "architect"],
            "escalation_reason": "P1 not resolved within 30 minutes - escalate to L3",
        },
        {
            "tier": EscalationTier.management,
            "time_threshold_minutes": 60,
            "auto_escalate": True,
            "notify_roles": ["ops_manager", "service_delivery_manager"],
            "escalation_reason": "P1 not resolved within 60 minutes - management escalation",
        },
        {
            "tier": EscalationTier.major_incident,
            "time_threshold_minutes": 90,
            "auto_escalate": True,
            "notify_roles": ["major_incident_manager", "vp_engineering", "exec_on_call"],
            "escalation_reason": "P1 not resolved within 90 minutes - major incident declared",
        },
    ],
    IncidentSeverity.P2.value: [
        {
            "tier": EscalationTier.L1,
            "time_threshold_minutes": 0,
            "auto_escalate": True,
            "notify_roles": ["noc_operator"],
            "escalation_reason": "P2 incident opened - L1 assignment",
        },
        {
            "tier": EscalationTier.L2,
            "time_threshold_minutes": 30,
            "auto_escalate": True,
            "notify_roles": ["noc_lead", "platform_engineer"],
            "escalation_reason": "P2 not resolved within 30 minutes - escalate to L2",
        },
        {
            "tier": EscalationTier.L3,
            "time_threshold_minutes": 60,
            "auto_escalate": True,
            "notify_roles": ["senior_engineer"],
            "escalation_reason": "P2 not resolved within 60 minutes - escalate to L3",
        },
        {
            "tier": EscalationTier.management,
            "time_threshold_minutes": 120,
            "auto_escalate": True,
            "notify_roles": ["ops_manager"],
            "escalation_reason": "P2 not resolved within 120 minutes - management escalation",
        },
    ],
    IncidentSeverity.P3.value: [
        {
            "tier": EscalationTier.L1,
            "time_threshold_minutes": 0,
            "auto_escalate": True,
            "notify_roles": ["noc_operator"],
            "escalation_reason": "P3 incident opened - L1 assignment",
        },
        {
            "tier": EscalationTier.L2,
            "time_threshold_minutes": 60,
            "auto_escalate": True,
            "notify_roles": ["platform_engineer"],
            "escalation_reason": "P3 not resolved within 60 minutes - escalate to L2",
        },
        {
            "tier": EscalationTier.L3,
            "time_threshold_minutes": 180,
            "auto_escalate": False,
            "notify_roles": ["senior_engineer"],
            "escalation_reason": "P3 not resolved within 180 minutes - escalate to L3",
        },
    ],
    IncidentSeverity.P4.value: [
        {
            "tier": EscalationTier.L1,
            "time_threshold_minutes": 0,
            "auto_escalate": True,
            "notify_roles": ["noc_operator"],
            "escalation_reason": "P4 incident opened - L1 assignment",
        },
        {
            "tier": EscalationTier.L2,
            "time_threshold_minutes": 240,
            "auto_escalate": False,
            "notify_roles": ["platform_engineer"],
            "escalation_reason": "P4 not resolved within 240 minutes - escalate to L2",
        },
    ],
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class IncidentParser:
    """Parses raw payloads into validated telco-ops domain objects."""

    # -- Incident parsing ----------------------------------------------------

    @staticmethod
    def parse_incident(payload: dict[str, Any]) -> IncidentObject:
        """Parse a raw dict into a validated IncidentObject.

        Handles datetime coercion, enum normalisation, and safe defaults.
        """
        severity_raw = payload.get("severity", "P4")
        try:
            severity = IncidentSeverity(severity_raw)
        except ValueError:
            severity = IncidentSeverity.P4

        status_raw = payload.get("status", "open")
        try:
            status = IncidentStatus(status_raw)
        except ValueError:
            status = IncidentStatus.open

        impact_raw = payload.get("service_impact", "no_impact")
        try:
            service_impact = ServiceImpact(impact_raw)
        except ValueError:
            service_impact = ServiceImpact.no_impact

        return IncidentObject(
            incident_id=str(payload.get("incident_id", payload.get("id", ""))),
            title=payload.get("title", "Untitled incident"),
            description=payload.get("description", ""),
            severity=severity,
            status=status,
            reported_at=_parse_dt(payload.get("reported_at")),
            acknowledged_at=_parse_dt(payload.get("acknowledged_at")),
            resolved_at=_parse_dt(payload.get("resolved_at")),
            service_impact=service_impact,
            affected_services=payload.get("affected_services", []),
            affected_customers_count=int(payload.get("affected_customers_count", 0)),
            work_order_refs=payload.get("work_order_refs", []),
            root_cause=payload.get("root_cause"),
            resolution_summary=payload.get("resolution_summary"),
        )

    # -- State transitions ---------------------------------------------------

    @staticmethod
    def extract_state_transitions(payload: dict[str, Any]) -> list[IncidentStateObject]:
        """Extract state-transition history from the payload.

        Looks for ``transitions`` or ``state_history`` keys.
        """
        raw_list = payload.get("transitions", payload.get("state_history", []))
        if not isinstance(raw_list, list):
            return []

        results: list[IncidentStateObject] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue

            current_raw = item.get("current_state", item.get("to", ""))
            previous_raw = item.get("previous_state", item.get("from"))

            try:
                current_state = IncidentStatus(current_raw)
            except ValueError:
                continue  # skip invalid transitions

            previous_state: IncidentStatus | None = None
            if previous_raw:
                try:
                    previous_state = IncidentStatus(previous_raw)
                except ValueError:
                    pass

            results.append(
                IncidentStateObject(
                    incident_id=str(item.get("incident_id", payload.get("incident_id", ""))),
                    current_state=current_state,
                    previous_state=previous_state,
                    transition_reason=item.get("transition_reason", item.get("reason", "")),
                    transitioned_by=item.get("transitioned_by", item.get("by")),
                    transitioned_at=_parse_dt(item.get("transitioned_at", item.get("at"))),
                )
            )
        return results

    # -- Service state -------------------------------------------------------

    @staticmethod
    def extract_service_state(payload: dict[str, Any]) -> ServiceStateObject | None:
        """Extract a service-state snapshot from the payload, if present."""
        svc = payload.get("service_state", payload.get("service"))
        if not svc or not isinstance(svc, dict):
            return None

        impact_raw = svc.get("impact_level", "no_impact")
        try:
            impact_level = ServiceImpact(impact_raw)
        except ValueError:
            impact_level = ServiceImpact.no_impact

        return ServiceStateObject(
            service_id=str(svc.get("service_id", svc.get("id", ""))),
            service_name=svc.get("service_name", svc.get("name", "")),
            current_status=svc.get("current_status", svc.get("status", "operational")),
            last_change=_parse_dt(svc.get("last_change")),
            impact_level=impact_level,
            dependent_services=svc.get("dependent_services", []),
        )

    # -- Escalation rules ----------------------------------------------------

    @staticmethod
    def extract_escalation_rules(severity: str) -> list[EscalationRuleObject]:
        """Return the default escalation ladder for a given severity.

        Falls back to P4 rules if severity is not recognised.
        """
        try:
            sev = IncidentSeverity(severity)
        except ValueError:
            sev = IncidentSeverity.P4

        rule_defs = _DEFAULT_ESCALATION_RULES.get(sev.value, [])
        results: list[EscalationRuleObject] = []
        for rd in rule_defs:
            results.append(
                EscalationRuleObject(
                    severity=sev,
                    tier=rd["tier"],
                    time_threshold_minutes=rd["time_threshold_minutes"],
                    auto_escalate=rd.get("auto_escalate", True),
                    notify_roles=rd.get("notify_roles", []),
                    escalation_reason=rd.get("escalation_reason", ""),
                )
            )
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_dt(value: Any) -> datetime | None:
    """Best-effort datetime parsing."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
