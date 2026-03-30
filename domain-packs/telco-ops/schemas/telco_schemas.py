"""Pydantic v2 models for telco operations: incidents, runbooks, escalation, and ops notes."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from ..taxonomy.telco_taxonomy import (
    EscalationLevel,
    IncidentSeverity,
    IncidentState,
    ServiceState,
)

# ---------------------------------------------------------------------------
# Core parsed objects
# ---------------------------------------------------------------------------


class ServiceStateMapping(BaseModel):
    """Mapping of a service to its current operational state."""

    service_id: str
    service_name: str
    state: ServiceState
    affected_customers: int = Field(0, ge=0)
    region: str = Field("")
    last_state_change: datetime | None = None
    related_incident_ids: list[str] = Field(default_factory=list)


class ParsedIncident(BaseModel):
    """A parsed telecom incident."""

    incident_id: str = Field(default_factory=lambda: f"INC-{str(uuid4())[:8].upper()}")
    title: str
    description: str = ""
    severity: IncidentSeverity = IncidentSeverity.p3
    state: IncidentState = IncidentState.new
    escalation_level: EscalationLevel = EscalationLevel.l1
    reported_at: datetime | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    reporter: str = Field("", description="Person or system that reported the incident")
    assigned_to: str | None = None
    affected_services: list[ServiceStateMapping] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    related_incident_ids: list[str] = Field(default_factory=list)
    root_cause: str | None = None
    resolution_notes: str | None = None
    is_recurring: bool = False
    recurrence_count: int = Field(0, ge=0)


class RunbookStep(BaseModel):
    """A single step in a runbook procedure."""

    step_number: int
    instruction: str
    expected_outcome: str = ""
    rollback_instruction: str = ""
    requires_approval: bool = False
    estimated_minutes: float = Field(5.0, gt=0.0)


class ParsedRunbook(BaseModel):
    """A parsed operational runbook."""

    runbook_id: str = Field(default_factory=lambda: f"RB-{str(uuid4())[:8].upper()}")
    title: str
    description: str = ""
    applicable_severity: list[IncidentSeverity] = Field(default_factory=list)
    applicable_services: list[str] = Field(default_factory=list)
    steps: list[RunbookStep] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    estimated_total_minutes: float = Field(0.0, ge=0.0)
    last_updated: datetime | None = None
    owner: str = ""
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Decision & analysis models
# ---------------------------------------------------------------------------


class IncidentSummary(BaseModel):
    """Concise summary of an incident for reporting and handoff."""

    incident_id: str
    title: str
    severity: IncidentSeverity
    state: IncidentState
    duration_minutes: float | None = None
    affected_services_count: int = 0
    total_affected_customers: int = 0
    key_events: list[str] = Field(default_factory=list, description="Timeline of key events")
    current_action: str = ""
    next_action: str = ""


class NextAction(BaseModel):
    """Recommended next action for an incident."""

    action: str = Field(..., description="Description of the recommended action")
    action_type: str = Field(
        "investigate", description="Type: investigate, escalate, resolve, communicate"
    )
    owner: str | None = Field(None, description="Suggested owner for this action")
    priority: str = Field("normal", description="Priority: low, normal, high, critical")
    runbook_ref: str | None = Field(None, description="Reference to applicable runbook")
    estimated_minutes: float | None = None
    rationale: str = Field("", description="Why this action is recommended")


class RunbookRecommendation(BaseModel):
    """Recommendation to apply a specific runbook to an incident."""

    runbook_id: str
    runbook_title: str
    relevance_score: float = Field(0.0, ge=0.0, le=1.0)
    matching_criteria: list[str] = Field(default_factory=list)
    estimated_resolution_minutes: float = Field(0.0, ge=0.0)


class EscalationDecision(BaseModel):
    """Result of evaluating whether an incident should be escalated."""

    level: EscalationLevel
    owner: str | None = None
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)
    urgency: str = Field("normal", description="Urgency: normal, urgent, critical")
    should_escalate: bool = True


class OpsNote(BaseModel):
    """Structured operational note for incident handoff or status update."""

    note_id: str = Field(default_factory=lambda: f"NOTE-{str(uuid4())[:8].upper()}")
    incident_id: str
    summary: str
    next_action: NextAction
    runbook_ref: str | None = None
    escalation: EscalationDecision | None = None
    service_state_explanation: str = Field(
        "", description="Current service state and impact description"
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    author: str = Field("system", description="Author: system or analyst name")
