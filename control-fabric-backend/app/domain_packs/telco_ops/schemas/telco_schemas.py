"""
Telco Ops Pack - Schema definitions for incident management,
service state, escalation rules, and SLA tracking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IncidentSeverity(str, Enum):
    """Severity classification aligned with ITIL priority model."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class IncidentStatus(str, Enum):
    """Lifecycle status of an incident."""

    open = "open"
    acknowledged = "acknowledged"
    investigating = "investigating"
    resolving = "resolving"
    resolved = "resolved"
    closed = "closed"


class EscalationTier(str, Enum):
    """Support / management escalation tiers."""

    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    management = "management"
    major_incident = "major_incident"


class ServiceImpact(str, Enum):
    """Degree of impact on a service."""

    total_outage = "total_outage"
    partial_outage = "partial_outage"
    degraded = "degraded"
    no_impact = "no_impact"


# ---------------------------------------------------------------------------
# Core domain objects
# ---------------------------------------------------------------------------

class IncidentObject(BaseModel):
    """Full incident record."""

    incident_id: str = Field(..., description="Unique incident identifier")
    title: str = Field(..., description="Short incident title")
    description: str = Field("", description="Detailed description of the incident")
    severity: IncidentSeverity = Field(..., description="Severity / priority classification")
    status: IncidentStatus = Field(IncidentStatus.open, description="Current lifecycle status")
    reported_at: Optional[datetime] = Field(None, description="When the incident was first reported")
    acknowledged_at: Optional[datetime] = Field(None, description="When the incident was acknowledged")
    resolved_at: Optional[datetime] = Field(None, description="When the incident was resolved")
    service_impact: ServiceImpact = Field(
        ServiceImpact.no_impact,
        description="Assessed impact on services",
    )
    affected_services: list[str] = Field(default_factory=list, description="Service IDs affected")
    affected_customers_count: int = Field(0, ge=0, description="Estimated number of affected customers")
    work_order_refs: list[str] = Field(
        default_factory=list,
        description="References to related field work orders",
    )
    root_cause: Optional[str] = Field(None, description="Root cause once identified")
    resolution_summary: Optional[str] = Field(None, description="Summary of resolution actions")

    class Config:
        use_enum_values = True


class IncidentStateObject(BaseModel):
    """A single state-transition record for an incident."""

    incident_id: str = Field(..., description="Incident this transition belongs to")
    current_state: IncidentStatus = Field(..., description="State after transition")
    previous_state: Optional[IncidentStatus] = Field(None, description="State before transition")
    transition_reason: str = Field("", description="Why the transition occurred")
    transitioned_by: Optional[str] = Field(None, description="User or system that triggered the transition")
    transitioned_at: Optional[datetime] = Field(None, description="Timestamp of transition")

    class Config:
        use_enum_values = True


class ServiceStateObject(BaseModel):
    """Current operational state of a service."""

    service_id: str = Field(..., description="Unique service identifier")
    service_name: str = Field(..., description="Human-readable service name")
    current_status: str = Field("operational", description="Current status (operational, degraded, outage)")
    last_change: Optional[datetime] = Field(None, description="When the status last changed")
    impact_level: ServiceImpact = Field(
        ServiceImpact.no_impact,
        description="Current impact level",
    )
    dependent_services: list[str] = Field(
        default_factory=list,
        description="IDs of services that depend on this one",
    )

    class Config:
        use_enum_values = True


class EscalationRuleObject(BaseModel):
    """A single escalation rule tied to severity and tier."""

    severity: IncidentSeverity = Field(..., description="Severity this rule applies to")
    tier: EscalationTier = Field(..., description="Escalation tier")
    time_threshold_minutes: int = Field(
        0,
        ge=0,
        description="Minutes after incident open before this escalation fires",
    )
    auto_escalate: bool = Field(True, description="Whether this escalation fires automatically")
    notify_roles: list[str] = Field(
        default_factory=list,
        description="Roles to notify when this escalation triggers",
    )
    escalation_reason: str = Field(
        "",
        description="Default reason string attached to the escalation",
    )

    class Config:
        use_enum_values = True


# ---------------------------------------------------------------------------
# SLA target reference (used by rule engine)
# ---------------------------------------------------------------------------

# Response = time to acknowledge; Resolution = time to resolve
SLA_TARGETS: dict[str, dict[str, int]] = {
    IncidentSeverity.P1.value: {"response_minutes": 15, "resolution_minutes": 60},
    IncidentSeverity.P2.value: {"response_minutes": 30, "resolution_minutes": 240},
    IncidentSeverity.P3.value: {"response_minutes": 60, "resolution_minutes": 480},
    IncidentSeverity.P4.value: {"response_minutes": 240, "resolution_minutes": 2880},
}
