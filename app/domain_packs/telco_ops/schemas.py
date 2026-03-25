"""Telco Ops domain pack schemas."""

from __future__ import annotations

import enum
import uuid

from pydantic import BaseModel


class IncidentSeverity(str, enum.Enum):
    p1 = "p1"
    p2 = "p2"
    p3 = "p3"
    p4 = "p4"


class IncidentState(str, enum.Enum):
    new = "new"
    acknowledged = "acknowledged"
    investigating = "investigating"
    resolved = "resolved"
    closed = "closed"


class ServiceState(str, enum.Enum):
    active = "active"
    degraded = "degraded"
    outage = "outage"
    maintenance = "maintenance"
    provisioning = "provisioning"


class EscalationLevel(str, enum.Enum):
    l1 = "l1"
    l2 = "l2"
    l3 = "l3"
    management = "management"


class ParsedIncident(BaseModel):
    incident_id: str
    title: str = ""
    description: str = ""
    severity: IncidentSeverity = IncidentSeverity.p3
    state: IncidentState = IncidentState.new
    affected_services: list[str] = []
    reported_by: str = ""
    assigned_to: str = ""
    created_at: str = ""
    updated_at: str = ""
    timeline: list[dict] = []
    tags: list[str] = []


class ParsedRunbook(BaseModel):
    runbook_id: str
    title: str = ""
    description: str = ""
    applicable_services: list[str] = []
    steps: list[dict] = []
    decision_points: list[dict] = []
    escalation_criteria: list[dict] = []
    estimated_resolution_minutes: int = 0


class NextAction(BaseModel):
    action: str  # investigate, escalate, dispatch, resolve, monitor, etc.
    owner: str = ""
    reason: str = ""
    evidence_ids: list[uuid.UUID] = []
    priority: str = "normal"


class EscalationDecision(BaseModel):
    escalate: bool
    level: EscalationLevel | None = None
    owner: str = ""
    reason: str = ""
    evidence_ids: list[uuid.UUID] = []


class IncidentSummary(BaseModel):
    incident_id: str
    severity: str
    state: str
    summary: str = ""
    affected_services: list[str] = []
    next_action: NextAction | None = None
    escalation: EscalationDecision | None = None
    runbook_recommendation: str | None = None
    service_state_explanation: str = ""


class OpsNote(BaseModel):
    summary: str
    next_action: str
    runbook_ref: str | None = None
    escalation_level: str | None = None
    escalation_owner: str | None = None
    service_state_explanation: str = ""
    evidence_ids: list[uuid.UUID] = []
