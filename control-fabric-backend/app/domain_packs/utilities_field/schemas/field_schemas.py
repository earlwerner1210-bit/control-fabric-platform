"""
Utilities Field Pack - Schema definitions for field operations,
work orders, engineer profiles, and dispatch preconditions.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WorkCategory(str, Enum):
    """Categories of utility field work."""

    hv_switching = "hv_switching"
    cable_jointing_hv = "cable_jointing_hv"
    cable_jointing_lv = "cable_jointing_lv"
    overhead_line = "overhead_line"
    metering = "metering"
    new_connection = "new_connection"
    civils = "civils"
    reinstatement = "reinstatement"


class AccreditationType(str, Enum):
    """Recognised accreditation / competence-card types."""

    ecs_card = "ecs_card"
    jib_grading = "jib_grading"
    cscs = "cscs"
    eighteenth_edition = "eighteenth_edition"
    nrswa = "nrswa"
    first_aid = "first_aid"
    confined_space = "confined_space"


class DispatchStatus(str, Enum):
    """Lifecycle status of a field dispatch."""

    pending = "pending"
    approved = "approved"
    dispatched = "dispatched"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


# ---------------------------------------------------------------------------
# Core domain objects
# ---------------------------------------------------------------------------

class WorkOrderObject(BaseModel):
    """Represents a single field work order."""

    work_order_id: str = Field(..., description="Unique identifier for the work order")
    contract_ref: Optional[str] = Field(None, description="Reference to the governing contract")
    description: str = Field("", description="Free-text description of the work")
    work_category: WorkCategory = Field(..., description="Category of work to be performed")
    scheduled_date: Optional[date] = Field(None, description="Planned execution date")
    location: Optional[str] = Field(None, description="Site / address where work takes place")
    crew_size: int = Field(1, ge=1, description="Number of engineers required")
    special_requirements: list[str] = Field(default_factory=list, description="Extra requirements such as permits or equipment")
    status: DispatchStatus = Field(DispatchStatus.pending, description="Current dispatch status")
    completion_evidence: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Evidence items attached on completion (photos, signatures, etc.)",
    )
    billing_gates: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Billing milestone gates and their statuses",
    )

    class Config:
        use_enum_values = True


class EngineerProfileObject(BaseModel):
    """Profile of a field engineer including qualifications."""

    engineer_id: str = Field(..., description="Unique engineer identifier")
    name: str = Field(..., description="Full name")
    grade: str = Field(..., description="Engineer grade / seniority level")
    accreditations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Accreditation records with type, expiry, issuing body",
    )
    skills: list[str] = Field(default_factory=list, description="Skill tags")
    availability_status: str = Field("available", description="Current availability (available, on_job, off_duty, leave)")

    class Config:
        use_enum_values = True


class SkillRequirementObject(BaseModel):
    """Skills required for a specific work category."""

    work_category: WorkCategory = Field(..., description="The work category these requirements apply to")
    required_skills: list[str] = Field(default_factory=list, description="List of skill tags the crew must collectively hold")
    minimum_grade: str = Field("standard", description="Minimum engineer grade required")
    crew_size: int = Field(1, ge=1, description="Minimum crew size")

    class Config:
        use_enum_values = True


class AccreditationRequirementObject(BaseModel):
    """Accreditation requirements for a work category."""

    work_category: WorkCategory = Field(..., description="The work category these requirements apply to")
    required_accreditations: list[AccreditationType] = Field(
        default_factory=list,
        description="Accreditation types that must be held by at least one crew member",
    )
    validity_check_required: bool = Field(
        True,
        description="Whether expiry dates must be validated before dispatch",
    )

    class Config:
        use_enum_values = True


class DispatchPreconditionObject(BaseModel):
    """A single precondition that must be satisfied before dispatch."""

    precondition_type: str = Field(..., description="Category of precondition (e.g. permit, access, safety)")
    description: str = Field("", description="Human-readable description of the precondition")
    satisfied: bool = Field(False, description="Whether this precondition is currently met")
    evidence_ref: Optional[str] = Field(None, description="Reference to supporting evidence document / record")
    blocker: bool = Field(
        True,
        description="If True, an unsatisfied precondition blocks dispatch entirely",
    )


# ---------------------------------------------------------------------------
# Convenience type aliases
# ---------------------------------------------------------------------------

WorkOrderPayload = dict[str, Any]
EngineerPayload = dict[str, Any]
