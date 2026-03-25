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
