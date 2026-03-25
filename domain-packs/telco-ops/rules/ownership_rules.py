"""Ownership rule engine for determining incident ownership and routing.

Assigns or re-assigns incident ownership based on severity, service domain,
escalation level, and team capacity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..schemas.telco_schemas import ParsedIncident, ServiceStateMapping
from ..taxonomy.telco_taxonomy import (
    EscalationLevel,
    IncidentSeverity,
    ServiceState,
)


@dataclass
class TeamMember:
    """Represents an operations team member for ownership assignment."""

    name: str
    team: str
    level: EscalationLevel
    domains: list[str] = field(default_factory=list)
    current_load: int = 0  # number of active incidents
    max_load: int = 5
    available: bool = True

    @property
    def has_capacity(self) -> bool:
        """Whether this team member can take on more incidents."""
        return self.available and self.current_load < self.max_load


@dataclass
class OwnershipDecision:
    """Result of ownership assignment evaluation."""

    assigned_owner: Optional[str]
    team: str
    reason: str
    reassignment: bool = False
    previous_owner: Optional[str] = None
    escalation_level: EscalationLevel = EscalationLevel.l1


# Service domain to team mapping (configurable in production)
_DEFAULT_DOMAIN_ROUTING: dict[str, str] = {
    "network": "network_ops",
    "core": "core_engineering",
    "access": "access_engineering",
    "transport": "transport_ops",
    "voice": "voice_services",
    "data": "data_services",
    "billing": "billing_ops",
    "provisioning": "provisioning_team",
    "security": "security_ops",
}


class OwnershipRuleEngine:
    """Determines incident ownership based on severity, domain, and team capacity.

    Rules:
    - Route by service domain to the appropriate team
    - Match escalation level to team member seniority
    - Consider current load for balanced assignment
    - Re-assign if current owner lacks capacity or capability
    """

    def __init__(
        self,
        domain_routing: dict[str, str] | None = None,
    ) -> None:
        self._domain_routing = domain_routing or _DEFAULT_DOMAIN_ROUTING

    def evaluate(
        self,
        incident: ParsedIncident,
        available_team: list[TeamMember] | None = None,
    ) -> OwnershipDecision:
        """Determine the appropriate owner for an incident.

        Args:
            incident: The incident requiring ownership assignment.
            available_team: List of available team members.

        Returns:
            OwnershipDecision with assigned owner and reasoning.
        """
        available_team = available_team or []

        # Determine target team based on affected services
        target_team = self._route_to_team(incident)

        # Determine required escalation level
        required_level = self._required_level(incident)

        # Find best available team member
        candidates = [
            m for m in available_team
            if m.has_capacity
            and m.level.numeric_level >= required_level.numeric_level
            and (m.team == target_team or not target_team)
        ]

        # If no candidates in target team, broaden search
        if not candidates:
            candidates = [
                m for m in available_team
                if m.has_capacity
                and m.level.numeric_level >= required_level.numeric_level
            ]

        # Sort by: exact team match, then lowest load, then highest level
        candidates.sort(
            key=lambda m: (
                0 if m.team == target_team else 1,
                m.current_load,
                -m.level.numeric_level,
            )
        )

        if candidates:
            best = candidates[0]
            is_reassignment = (
                incident.assigned_to is not None
                and incident.assigned_to != best.name
            )
            return OwnershipDecision(
                assigned_owner=best.name,
                team=best.team,
                reason=(
                    f"Assigned to {best.name} ({best.team}, {best.level.value}) "
                    f"based on domain routing and capacity (load: {best.current_load}/{best.max_load})."
                ),
                reassignment=is_reassignment,
                previous_owner=incident.assigned_to if is_reassignment else None,
                escalation_level=best.level,
            )

        # No available team members
        return OwnershipDecision(
            assigned_owner=None,
            team=target_team or "unassigned",
            reason=(
                f"No available team members with {required_level.value} capability "
                f"and capacity in {target_team or 'any team'}. "
                f"Incident requires manual assignment."
            ),
            escalation_level=required_level,
        )

    def _route_to_team(self, incident: ParsedIncident) -> Optional[str]:
        """Determine the target team based on affected services."""
        for service in incident.affected_services:
            service_lower = service.service_name.lower()
            for domain_keyword, team in self._domain_routing.items():
                if domain_keyword in service_lower:
                    return team

        # Fallback: route by tags
        for tag in incident.tags:
            tag_lower = tag.lower()
            for domain_keyword, team in self._domain_routing.items():
                if domain_keyword in tag_lower:
                    return team

        return None

    def _required_level(self, incident: ParsedIncident) -> EscalationLevel:
        """Determine the minimum required escalation level for ownership."""
        # Current escalation level is the minimum
        level = incident.escalation_level

        # P1 requires at least L2
        if incident.severity == IncidentSeverity.p1 and level.numeric_level < 2:
            level = EscalationLevel.l2

        # Recurring incidents need at least L2
        if incident.is_recurring and incident.recurrence_count >= 2:
            if level.numeric_level < 2:
                level = EscalationLevel.l2

        # Multiple service impact needs at least L2
        impacted = [s for s in incident.affected_services if s.state.is_impacted]
        if len(impacted) >= 2 and level.numeric_level < 2:
            level = EscalationLevel.l2

        # Large customer impact needs at least L3
        total_customers = sum(s.affected_customers for s in impacted)
        if total_customers >= 5000 and level.numeric_level < 3:
            level = EscalationLevel.l3

        return level
