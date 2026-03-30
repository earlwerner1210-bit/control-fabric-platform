"""Taxonomy enumerations for telco operations: incidents, services, and escalations."""

from enum import Enum


class IncidentSeverity(str, Enum):
    """Severity levels for telecom incidents (P1 = highest)."""

    p1 = "p1"
    p2 = "p2"
    p3 = "p3"
    p4 = "p4"

    @property
    def sla_response_minutes(self) -> int:
        """Default SLA response time in minutes."""
        return {
            IncidentSeverity.p1: 15,
            IncidentSeverity.p2: 30,
            IncidentSeverity.p3: 60,
            IncidentSeverity.p4: 240,
        }[self]

    @property
    def sla_resolution_minutes(self) -> int:
        """Default SLA resolution time in minutes."""
        return {
            IncidentSeverity.p1: 240,
            IncidentSeverity.p2: 480,
            IncidentSeverity.p3: 1440,
            IncidentSeverity.p4: 4320,
        }[self]

    @property
    def requires_management_notification(self) -> bool:
        """Whether management must be notified for this severity."""
        return self in (IncidentSeverity.p1, IncidentSeverity.p2)


class IncidentState(str, Enum):
    """Lifecycle states for incident management."""

    new = "new"
    acknowledged = "acknowledged"
    investigating = "investigating"
    resolved = "resolved"
    closed = "closed"

    @property
    def is_active(self) -> bool:
        """Whether the incident is still being worked on."""
        return self in (
            IncidentState.new,
            IncidentState.acknowledged,
            IncidentState.investigating,
        )

    @property
    def is_terminal(self) -> bool:
        """Whether the incident is in a final state."""
        return self in (IncidentState.resolved, IncidentState.closed)

    def valid_transitions(self) -> list["IncidentState"]:
        """Return valid next states from this state."""
        transitions: dict[IncidentState, list[IncidentState]] = {
            IncidentState.new: [IncidentState.acknowledged],
            IncidentState.acknowledged: [IncidentState.investigating],
            IncidentState.investigating: [IncidentState.resolved, IncidentState.acknowledged],
            IncidentState.resolved: [IncidentState.closed, IncidentState.investigating],
            IncidentState.closed: [],
        }
        return transitions.get(self, [])


class ServiceState(str, Enum):
    """Operational states for telecom services."""

    active = "active"
    degraded = "degraded"
    outage = "outage"
    maintenance = "maintenance"
    provisioning = "provisioning"

    @property
    def is_impacted(self) -> bool:
        """Whether this state represents a service impact."""
        return self in (ServiceState.degraded, ServiceState.outage)

    @property
    def customer_visible(self) -> bool:
        """Whether this state is visible to end customers."""
        return self in (ServiceState.degraded, ServiceState.outage, ServiceState.maintenance)


class EscalationLevel(str, Enum):
    """Escalation levels for incident handling."""

    l1 = "l1"
    l2 = "l2"
    l3 = "l3"
    management = "management"

    @property
    def numeric_level(self) -> int:
        """Numeric representation for comparison."""
        return {
            EscalationLevel.l1: 1,
            EscalationLevel.l2: 2,
            EscalationLevel.l3: 3,
            EscalationLevel.management: 4,
        }[self]

    def is_higher_than(self, other: "EscalationLevel") -> bool:
        """Check if this level is higher than another."""
        return self.numeric_level > other.numeric_level
