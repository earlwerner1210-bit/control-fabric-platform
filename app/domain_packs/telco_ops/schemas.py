"""Telco Ops domain pack schemas."""

from __future__ import annotations

import enum
import uuid

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


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


class ImpactLevel(str, enum.Enum):
    critical = "critical"
    major = "major"
    minor = "minor"
    negligible = "negligible"


class ReconciliationStatus(str, enum.Enum):
    aligned = "aligned"
    mismatched = "mismatched"
    partial = "partial"
    unknown = "unknown"


class SLAStatus(str, enum.Enum):
    within = "within"
    warning = "warning"
    breached = "breached"


# ---------------------------------------------------------------------------
# Core incident / runbook models (existing)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# NEW: Timeline models
# ---------------------------------------------------------------------------


class TimelineEvent(BaseModel):
    """A single event in an incident timeline."""

    timestamp: str
    event_type: str  # created, acknowledged, assigned, note, state_change, escalation, resolution
    actor: str
    description: str
    state_change: str | None = None  # e.g. "new -> acknowledged"


class IncidentTimeline(BaseModel):
    """Structured timeline for an incident."""

    events: list[TimelineEvent] = []
    total_duration_minutes: int = 0
    sla_status: str = "within"  # within, warning, breached
    breach_at: str | None = None


# ---------------------------------------------------------------------------
# NEW: Service state model
# ---------------------------------------------------------------------------


class ServiceStateObject(BaseModel):
    """Detailed representation of a service's operational state."""

    service_id: str
    service_name: str
    state: ServiceState
    last_state_change: str = ""
    affected_customers: int = 0
    impact_level: ImpactLevel = ImpactLevel.negligible
    dependencies: list[str] = []
    recovery_eta_minutes: int | None = None


# ---------------------------------------------------------------------------
# NEW: Runbook reference / step models
# ---------------------------------------------------------------------------


class RunbookStep(BaseModel):
    """A single step within a runbook."""

    step_number: int
    action: str
    expected_result: str
    escalation_on_failure: str = ""
    automated: bool = False
    timeout_minutes: int = 10


class RunbookReferenceObject(BaseModel):
    """A fully-typed runbook reference with steps and metadata."""

    runbook_id: str
    title: str
    applicable_severity: list[str] = []
    applicable_services: list[str] = []
    steps: list[RunbookStep] = []
    estimated_time_minutes: int = 0
    success_rate: float = 0.0
    last_updated: str = ""


# ---------------------------------------------------------------------------
# NEW: Ownership rule model
# ---------------------------------------------------------------------------


class OwnershipRuleObject(BaseModel):
    """Declarative ownership assignment rule."""

    incident_type: str
    severity: str
    primary_owner: str
    secondary_owner: str = ""
    escalation_chain: list[str] = []
    time_to_own_minutes: int = 15


# ---------------------------------------------------------------------------
# NEW: Reconciliation models
# ---------------------------------------------------------------------------


class ReconciliationMismatch(BaseModel):
    """A single field-level mismatch between incident and work order."""

    field: str
    incident_value: str = ""
    work_order_value: str = ""
    severity: str = "info"  # info, warning, error, critical
    resolution: str = ""


class ReconciliationResult(BaseModel):
    """Result of reconciling an incident against a work order or service state."""

    status: ReconciliationStatus = ReconciliationStatus.unknown
    mismatches: list[ReconciliationMismatch] = []
    recommendations: list[str] = []
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# NEW: Ops recommendation model
# ---------------------------------------------------------------------------


class OpsRecommendation(BaseModel):
    """A structured operational recommendation."""

    action: str
    owner: str = ""
    priority: str = "normal"
    rationale: str = ""
    evidence_ids: list[uuid.UUID] = []
    estimated_resolution_minutes: int = 0
    runbook_ref: str | None = None
    risk_if_delayed: str = ""


# ---------------------------------------------------------------------------
# Vodafone UK managed-services enums and models
# ---------------------------------------------------------------------------


class VodafoneServiceDomain(str, enum.Enum):
    core_network = "core_network"
    ran_radio = "ran_radio"
    transport_network = "transport_network"
    vas_platforms = "vas_platforms"
    it_infrastructure = "it_infrastructure"
    billing_mediation = "billing_mediation"
    oss_bss = "oss_bss"
    customer_facing = "customer_facing"
    provisioning = "provisioning"
    number_portability = "number_portability"
    voip_ims = "voip_ims"


class VodafoneIncidentCategory(str, enum.Enum):
    network_outage = "network_outage"
    network_degradation = "network_degradation"
    capacity_breach = "capacity_breach"
    config_error = "config_error"
    hardware_failure = "hardware_failure"
    software_bug = "software_bug"
    security_incident = "security_incident"
    planned_maintenance_overrun = "planned_maintenance_overrun"
    vendor_dependency = "vendor_dependency"
    power_failure = "power_failure"
    fibre_cut = "fibre_cut"
    radio_interference = "radio_interference"


class MajorIncidentPhase(str, enum.Enum):
    detection = "detection"
    bridge_call_initiated = "bridge_call_initiated"
    investigation = "investigation"
    containment = "containment"
    resolution = "resolution"
    rca_pending = "rca_pending"
    rca_complete = "rca_complete"
    post_incident_review = "post_incident_review"


class ClosurePrerequisite(str, enum.Enum):
    root_cause_identified = "root_cause_identified"
    workaround_documented = "workaround_documented"
    permanent_fix_planned = "permanent_fix_planned"
    customer_notified = "customer_notified"
    service_restored = "service_restored"
    rca_submitted = "rca_submitted"
    problem_record_created = "problem_record_created"
    change_request_raised = "change_request_raised"


class VodafoneSLADefinition(BaseModel):
    """SLA definition for a Vodafone managed-services severity level."""

    severity: IncidentSeverity
    response_time_minutes: int
    resolution_time_minutes: int
    update_frequency_minutes: int
    bridge_call_required: bool = False
    rca_required: bool = False
    rca_due_days: int = 5
    escalation_intervals: list[dict] = []  # [{"minutes": 30, "to": "l2"}, ...]


# Pre-built Vodafone SLA definitions
VODAFONE_SLA_DEFINITIONS: list[VodafoneSLADefinition] = [
    VodafoneSLADefinition(
        severity=IncidentSeverity.p1,
        response_time_minutes=15,
        resolution_time_minutes=240,
        update_frequency_minutes=15,
        bridge_call_required=True,
        rca_required=True,
        rca_due_days=3,
        escalation_intervals=[
            {"minutes": 15, "to": "l2"},
            {"minutes": 30, "to": "l3"},
            {"minutes": 60, "to": "management"},
        ],
    ),
    VodafoneSLADefinition(
        severity=IncidentSeverity.p2,
        response_time_minutes=30,
        resolution_time_minutes=480,
        update_frequency_minutes=30,
        bridge_call_required=True,
        rca_required=True,
        rca_due_days=5,
        escalation_intervals=[
            {"minutes": 30, "to": "l2"},
            {"minutes": 60, "to": "l3"},
            {"minutes": 120, "to": "management"},
        ],
    ),
    VodafoneSLADefinition(
        severity=IncidentSeverity.p3,
        response_time_minutes=240,
        resolution_time_minutes=1440,
        update_frequency_minutes=240,
        bridge_call_required=False,
        rca_required=False,
        rca_due_days=5,
        escalation_intervals=[
            {"minutes": 240, "to": "l2"},
            {"minutes": 480, "to": "l3"},
        ],
    ),
    VodafoneSLADefinition(
        severity=IncidentSeverity.p4,
        response_time_minutes=480,
        resolution_time_minutes=7200,
        update_frequency_minutes=1440,
        bridge_call_required=False,
        rca_required=False,
        rca_due_days=5,
        escalation_intervals=[
            {"minutes": 1440, "to": "l2"},
        ],
    ),
]


class MajorIncidentRecord(BaseModel):
    """Tracks the lifecycle of a Vodafone major incident (P1/P2 with MIM)."""

    incident_id: str
    phase: MajorIncidentPhase
    bridge_call_id: str = ""
    bridge_participants: list[str] = []
    customer_comms_sent: list[dict] = []
    rca_status: str = ""  # "not_started", "in_progress", "submitted", "accepted"
    rca_due_date: str = ""
    problem_record_id: str = ""


class ClosureGate(BaseModel):
    """A single closure prerequisite gate for incident closure validation."""

    prerequisite: ClosurePrerequisite
    satisfied: bool = False
    evidence_ref: str = ""
    mandatory: bool = True
