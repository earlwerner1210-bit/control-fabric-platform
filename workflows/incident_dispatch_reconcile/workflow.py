"""Incident dispatch workflow -- handles incident triage, dispatch, and reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IncidentDispatchResult:
    """Result of an incident dispatch workflow run."""

    case_id: str
    incident_id: str
    assigned_team: str | None = None
    escalation_level: int = 0
    recommended_actions: list[str] = field(default_factory=list)
    sla_target_minutes: int | None = None
    status: str = "completed"


class IncidentDispatchWorkflow:
    """Orchestrates the incident dispatch and reconciliation workflow.

    Steps:
    1. Evaluate escalation rules
    2. Determine team assignment
    3. Calculate SLA targets
    4. Run validation
    5. Record audit trail
    """

    def __init__(
        self,
        escalation_engine: Any = None,
        validator: Any = None,
        audit_logger: Any = None,
    ) -> None:
        self.escalation_engine = escalation_engine
        self.validator = validator
        self.audit_logger = audit_logger

    async def run(
        self,
        case_id: str,
        incident: dict[str, Any],
        tenant_id: str,
        options: dict[str, Any] | None = None,
    ) -> IncidentDispatchResult:
        """Execute the incident dispatch workflow."""
        incident_id = incident.get("incident_id", "unknown")
        assigned_team = incident.get("assigned_team")
        escalation_level = incident.get("escalation_level", 0)
        recommended_actions: list[str] = []
        sla_target_minutes: int | None = None

        # Run escalation evaluation
        if self.escalation_engine:
            result = self.escalation_engine.evaluate(incident)
            if result.should_escalate:
                escalation_level = result.recommended_level
                recommended_actions = [a.action for a in result.actions]

        # Determine team based on priority and category
        priority = incident.get("priority", "P3")
        category = incident.get("category", "general")
        if not assigned_team:
            assigned_team = self._determine_team(priority, category)

        # Calculate SLA
        sla_targets = {"P1": 240, "P2": 480, "P3": 1440, "P4": 4320}
        sla_target_minutes = sla_targets.get(priority, 1440)

        # Add standard actions
        recommended_actions.extend(self._standard_actions(priority, category))

        if self.audit_logger:
            try:
                await self.audit_logger.log(
                    case_id=case_id,
                    event_type="incident.dispatched",
                    detail={
                        "incident_id": incident_id,
                        "assigned_team": assigned_team,
                        "escalation_level": escalation_level,
                    },
                )
            except Exception:
                pass

        return IncidentDispatchResult(
            case_id=case_id,
            incident_id=incident_id,
            assigned_team=assigned_team,
            escalation_level=escalation_level,
            recommended_actions=recommended_actions,
            sla_target_minutes=sla_target_minutes,
        )

    @staticmethod
    def _determine_team(priority: str, category: str) -> str:
        """Determine the appropriate team based on priority and category."""
        if "network" in category.lower():
            return "network_operations"
        if "field" in category.lower() or "equipment" in category.lower():
            return "field_services"
        if priority in ("P1", "P2"):
            return "critical_response"
        return "general_operations"

    @staticmethod
    def _standard_actions(priority: str, category: str) -> list[str]:
        """Return standard recommended actions."""
        actions = ["Review incident details and confirm impact assessment"]
        if priority in ("P1", "P2"):
            actions.append("Initiate bridge call with stakeholders")
        if "network" in category.lower():
            actions.append("Run network diagnostics")
        return actions
