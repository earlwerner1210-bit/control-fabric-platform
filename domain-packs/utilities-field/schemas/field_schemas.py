"""Pydantic v2 models for field operations: work orders, engineers, permits, and readiness."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from ..taxonomy.field_taxonomy import (
    PermitType,
    ReadinessStatus,
    SkillCategory,
    WorkOrderType,
)


# ---------------------------------------------------------------------------
# Core domain objects
# ---------------------------------------------------------------------------


class SkillRecord(BaseModel):
    """A single skill held by a field engineer."""

    skill_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    category: SkillCategory
    name: str = Field(..., description="Specific skill name, e.g. 'Single-mode fibre splicing'")
    proficiency_level: str = Field("competent", description="Level: trainee, competent, expert")
    years_experience: float = Field(0.0, ge=0.0)
    last_assessed: Optional[date] = None


class Accreditation(BaseModel):
    """A formal accreditation or certification held by an engineer."""

    accreditation_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str = Field(..., description="Accreditation name, e.g. 'Gas Safe Register'")
    issuing_body: str = Field("", description="Organisation that issued the accreditation")
    certificate_number: Optional[str] = None
    issued_date: Optional[date] = None
    expiry_date: Optional[date] = None
    categories: list[SkillCategory] = Field(default_factory=list, description="Skill categories this accreditation covers")
    is_mandatory: bool = Field(False, description="Whether this is a legally required accreditation")


class EngineerProfile(BaseModel):
    """Complete profile of a field engineer including skills and accreditations."""

    engineer_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    employee_number: Optional[str] = None
    skills: list[SkillRecord] = Field(default_factory=list)
    accreditations: list[Accreditation] = Field(default_factory=list)
    base_location: str = Field("", description="Engineer's base depot or location")
    max_travel_radius_km: float = Field(50.0, ge=0.0)
    available: bool = Field(True)
    current_assignment: Optional[str] = None


class PermitRequirement(BaseModel):
    """A permit required for a field work order."""

    permit_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    permit_type: PermitType
    status: str = Field("pending", description="Status: pending, approved, rejected, expired")
    reference_number: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    issuing_authority: str = Field("")
    conditions: list[str] = Field(default_factory=list, description="Special conditions attached to the permit")


class FieldJob(BaseModel):
    """A specific job or task within a work order."""

    job_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    description: str
    required_skills: list[SkillCategory] = Field(default_factory=list)
    estimated_duration_hours: float = Field(1.0, gt=0.0)
    priority: str = Field("normal", description="Priority: low, normal, high, critical")
    hazards: list[str] = Field(default_factory=list, description="Known hazards for this job")
    safety_equipment: list[str] = Field(default_factory=list, description="Required PPE and safety equipment")


class ParsedWorkOrder(BaseModel):
    """Top-level model for a parsed field work order."""

    work_order_id: str = Field(default_factory=lambda: str(uuid4()))
    work_order_type: WorkOrderType
    title: str
    description: str = ""
    customer_name: str = ""
    site_address: str = ""
    site_postcode: str = ""
    contact_phone: str = ""
    scheduled_date: Optional[date] = None
    scheduled_time_start: Optional[time] = None
    scheduled_time_end: Optional[time] = None
    jobs: list[FieldJob] = Field(default_factory=list)
    required_skills: list[SkillCategory] = Field(default_factory=list)
    required_permits: list[PermitRequirement] = Field(default_factory=list)
    assigned_engineer_id: Optional[str] = None
    priority: str = Field("normal", description="Priority: low, normal, high, critical")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Decision & analysis models
# ---------------------------------------------------------------------------


class SkillFitAnalysis(BaseModel):
    """Analysis of how well an engineer's skills match work order requirements."""

    overall_fit: float = Field(0.0, ge=0.0, le=1.0, description="Overall fit score 0-1")
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    partially_matched: list[str] = Field(default_factory=list, description="Skills where engineer has related but not exact match")
    overqualified_areas: list[str] = Field(default_factory=list)


class ComplianceBlocker(BaseModel):
    """A compliance issue that blocks dispatch."""

    blocker_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    category: str = Field(..., description="Category: permit, accreditation, safety, access, schedule")
    description: str
    severity: str = Field("blocking", description="Severity: warning, blocking")
    resolution_action: str = Field("", description="Suggested action to resolve this blocker")
    estimated_resolution_hours: Optional[float] = None


class ReadinessDecision(BaseModel):
    """Result of evaluating a work order's readiness for dispatch."""

    status: ReadinessStatus
    missing_prerequisites: list[str] = Field(default_factory=list)
    skill_fit: SkillFitAnalysis = Field(default_factory=SkillFitAnalysis)
    blockers: list[ComplianceBlocker] = Field(default_factory=list)
    recommendation: str = Field("", description="Human-readable dispatch recommendation")
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class DispatchRecommendation(BaseModel):
    """Recommendation for dispatching a work order to an engineer."""

    work_order_id: str
    recommended_engineer_id: Optional[str] = None
    readiness: ReadinessDecision
    alternative_engineers: list[str] = Field(default_factory=list, description="IDs of alternative engineers if primary is not suitable")
    estimated_travel_time_minutes: Optional[float] = None
    special_instructions: list[str] = Field(default_factory=list)
    dispatch_approved: bool = False
