"""Utilities Field domain pack schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pydantic import BaseModel


class WorkOrderType(str, enum.Enum):
    installation = "installation"
    maintenance = "maintenance"
    repair = "repair"
    inspection = "inspection"
    emergency = "emergency"
    upgrade = "upgrade"


class SkillCategory(str, enum.Enum):
    electrical = "electrical"
    plumbing = "plumbing"
    hvac = "hvac"
    gas = "gas"
    fiber = "fiber"
    general = "general"


class PermitType(str, enum.Enum):
    street_works = "street_works"
    building_access = "building_access"
    confined_space = "confined_space"
    hot_works = "hot_works"
    height_works = "height_works"


class ReadinessStatus(str, enum.Enum):
    ready = "ready"
    blocked = "blocked"
    conditional = "conditional"
    escalate = "escalate"


class PreconditionType(str, enum.Enum):
    ppe = "ppe"
    certification = "certification"
    risk_assessment = "risk_assessment"
    method_statement = "method_statement"
    toolbox_talk = "toolbox_talk"


class ExceptionType(str, enum.Enum):
    rework = "rework"
    revisit = "revisit"
    no_access = "no_access"
    safety_stop = "safety_stop"
    wrong_materials = "wrong_materials"
    skill_gap = "skill_gap"
    weather = "weather"
    customer_refusal = "customer_refusal"


class RecommendationType(str, enum.Enum):
    dispatch = "dispatch"
    hold = "hold"
    reassign = "reassign"
    reschedule = "reschedule"
    cancel = "cancel"


class RiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class SkillRecord(BaseModel):
    skill_name: str
    category: SkillCategory
    level: str = "qualified"  # qualified, expert, trainee
    expiry_date: str | None = None


class Accreditation(BaseModel):
    name: str
    issuing_body: str = ""
    valid_from: str | None = None
    valid_to: str | None = None
    is_valid: bool = True


class EngineerProfile(BaseModel):
    engineer_id: str
    name: str
    skills: list[SkillRecord] = []
    accreditations: list[Accreditation] = []
    availability: str = "available"
    location: str = ""


class PermitRequirement(BaseModel):
    permit_type: PermitType
    description: str = ""
    required: bool = True
    obtained: bool = False
    reference: str = ""


class ParsedWorkOrder(BaseModel):
    work_order_id: str
    work_order_type: WorkOrderType = WorkOrderType.maintenance
    description: str = ""
    location: str = ""
    scheduled_date: str | None = None
    priority: str = "normal"
    required_skills: list[SkillRecord] = []
    required_permits: list[PermitRequirement] = []
    prerequisites: list[dict] = []
    estimated_duration_hours: float = 0
    customer: str = ""
    site_id: str = ""
    scheduled_end: str | None = None
    dependencies: list[dict] = []
    materials_required: list[dict] = []
    special_instructions: str = ""
    linked_contract_id: uuid.UUID | None = None
    customer_confirmed: bool = False
    weather_conditions: str | None = None


# ---------------------------------------------------------------------------
# Analysis & decision schemas
# ---------------------------------------------------------------------------


class SkillFitAnalysis(BaseModel):
    fit: bool
    matching_skills: list[str] = []
    missing_skills: list[str] = []
    expiring_soon: list[str] = []


class ComplianceBlocker(BaseModel):
    blocker_type: str  # permit, accreditation, safety, access
    description: str
    severity: str = "error"
    resolution: str = ""


class ReadinessDecision(BaseModel):
    status: ReadinessStatus
    missing_prerequisites: list[str] = []
    skill_fit: SkillFitAnalysis | None = None
    blockers: list[ComplianceBlocker] = []
    recommendation: str = ""
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# New schemas
# ---------------------------------------------------------------------------


class WorkOrderObject(BaseModel):
    """Full work order object with extended attributes."""

    work_order_id: str
    work_order_type: WorkOrderType = WorkOrderType.maintenance
    description: str = ""
    location: str = ""
    site_id: str = ""
    customer: str = ""
    scheduled_start: str | None = None
    scheduled_end: str | None = None
    priority: str = "normal"
    estimated_duration_hours: float = 0
    actual_duration_hours: float | None = None
    status: str = "pending"
    dependencies: list[dict] = []
    materials_required: list[dict] = []
    special_instructions: str = ""
    linked_contract_id: uuid.UUID | None = None


class SafetyPreconditionObject(BaseModel):
    """A single safety precondition that must be met before dispatch."""

    precondition_type: PreconditionType
    description: str
    required: bool = True
    verified: bool = False
    verified_by: str = ""
    verified_at: str = ""


class MissingPrerequisite(BaseModel):
    """A prerequisite that is missing or unresolved."""

    prerequisite_type: str  # permit, skill, accreditation, access, dependency, safety, customer
    description: str
    severity: str = "error"
    resolution_action: str = ""
    estimated_resolution_time_hours: float = 0.0
    blocking: bool = True


class DispatchRecommendation(BaseModel):
    """A recommendation on whether to dispatch an engineer."""

    recommendation: RecommendationType
    reasons: list[str] = []
    alternative_engineers: list[str] = []
    suggested_date: str | None = None
    risk_level: str = "low"
    confidence: float = 1.0


class FieldExceptionClassification(BaseModel):
    """Classification of a field exception event."""

    exception_type: ExceptionType
    description: str = ""
    root_cause: str = ""
    preventable: bool = False
    cost_impact: float = 0.0
    recommended_action: str = ""


class FieldSummaryResult(BaseModel):
    """Comprehensive field summary combining all analysis outputs."""

    work_order_id: str
    readiness: ReadinessDecision
    dispatch_recommendation: DispatchRecommendation
    exceptions: list[FieldExceptionClassification] = []
    engineer_briefing: str = ""
    risk_assessment: str = ""


class RepeatVisitRisk(BaseModel):
    """Assessment of repeat-visit risk for a work order."""

    risk_level: RiskLevel
    contributing_factors: list[str] = []
    previous_visit_count: int = 0
    recommended_mitigations: list[str] = []


class MaterialRequirement(BaseModel):
    """A single material requirement for a work order."""

    material_id: str = ""
    description: str = ""
    quantity: float = 1.0
    unit: str = "each"
    available: bool = True
    alternative: str = ""


# ---------------------------------------------------------------------------
# SPEN / UK Utility Managed Services schemas
# ---------------------------------------------------------------------------


class SPENWorkCategory(str, enum.Enum):
    """Work categories for SPEN (Scottish Power Energy Networks) electricity distribution."""

    hv_switching = "hv_switching"
    lv_fault_repair = "lv_fault_repair"
    cable_jointing = "cable_jointing"
    overhead_lines = "overhead_lines"
    substation_maintenance = "substation_maintenance"
    metering_installation = "metering_installation"
    metering_exchange = "metering_exchange"
    new_connection = "new_connection"
    service_alteration = "service_alteration"
    tree_cutting = "tree_cutting"
    civils_excavation = "civils_excavation"
    reinstatement = "reinstatement"
    cable_laying = "cable_laying"
    pole_erection = "pole_erection"
    transformer_installation = "transformer_installation"


class UKAccreditation(str, enum.Enum):
    """UK-specific accreditations and competency cards for utility field work."""

    ecs_card = "ecs_card"
    jib_grading = "jib_grading"
    cscs_card = "cscs_card"
    eighteen_edition = "eighteen_edition"
    hv_authorized_person = "hv_authorized_person"
    lv_authorized_person = "lv_authorized_person"
    hv_competent_person = "hv_competent_person"
    cable_jointer_approved = "cable_jointer_approved"
    cat_and_genny = "cat_and_genny"
    nrswa_supervisor = "nrswa_supervisor"
    nrswa_operative = "nrswa_operative"
    sssts = "sssts"
    smsts = "smsts"
    first_aid_at_work = "first_aid_at_work"
    confined_space_entry = "confined_space_entry"
    working_at_height = "working_at_height"
    asbestos_awareness = "asbestos_awareness"
    ipaf_mewp = "ipaf_mewp"
    abrasive_wheels = "abrasive_wheels"


class CompletionEvidenceType(str, enum.Enum):
    """Types of evidence required for SPEN work completion sign-off."""

    before_photo = "before_photo"
    after_photo = "after_photo"
    as_built_drawing = "as_built_drawing"
    customer_sign_off = "customer_sign_off"
    safety_documentation = "safety_documentation"
    permit_close_out = "permit_close_out"
    test_certificate = "test_certificate"
    reinstatement_record = "reinstatement_record"
    waste_transfer_note = "waste_transfer_note"
    risk_assessment_completed = "risk_assessment_completed"


class SPENReadinessGate(BaseModel):
    """A readiness gate that must be satisfied before SPEN work can proceed."""

    gate_name: str
    gate_type: str  # "permit", "accreditation", "safety", "access", "materials", "design", "customer", "dependency"
    required: bool = True
    satisfied: bool = False
    evidence_ref: str = ""
    blocking: bool = True
    description: str = ""


class CompletionEvidence(BaseModel):
    """Evidence item required for SPEN work completion sign-off."""

    evidence_type: CompletionEvidenceType
    description: str = ""
    provided: bool = False
    reference: str = ""
    timestamp: str = ""


class CrewRequirement(BaseModel):
    """Crew composition requirements for SPEN work categories."""

    minimum_crew_size: int = 1
    requires_supervisor: bool = False
    requires_hv_authorized: bool = False
    requires_cable_jointer: bool = False
    special_roles: list[str] = []
