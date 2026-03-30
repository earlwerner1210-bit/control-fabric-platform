"""Taxonomy enumerations for field operations, work orders, skills, and permits."""

from enum import Enum


class WorkOrderType(str, Enum):
    """Classification of field work order types."""

    installation = "installation"
    maintenance = "maintenance"
    repair = "repair"
    inspection = "inspection"
    emergency = "emergency"
    upgrade = "upgrade"

    @property
    def requires_permit(self) -> bool:
        """Whether this work type typically requires a permit."""
        return self in (
            WorkOrderType.installation,
            WorkOrderType.repair,
            WorkOrderType.emergency,
            WorkOrderType.upgrade,
        )

    @property
    def is_urgent(self) -> bool:
        """Whether this work type is considered urgent by default."""
        return self in (WorkOrderType.emergency, WorkOrderType.repair)


class SkillCategory(str, Enum):
    """Classification of field engineer skill categories."""

    electrical = "electrical"
    plumbing = "plumbing"
    hvac = "hvac"
    gas = "gas"
    fiber = "fiber"
    general = "general"

    @property
    def requires_certification(self) -> bool:
        """Whether this skill category requires formal certification."""
        return self in (
            SkillCategory.electrical,
            SkillCategory.gas,
            SkillCategory.hvac,
        )


class PermitType(str, Enum):
    """Classification of field work permit types."""

    street_works = "street_works"
    building_access = "building_access"
    confined_space = "confined_space"
    hot_works = "hot_works"
    height_works = "height_works"

    @property
    def requires_safety_briefing(self) -> bool:
        """Whether this permit type mandates a safety briefing."""
        return self in (
            PermitType.confined_space,
            PermitType.hot_works,
            PermitType.height_works,
        )


class ReadinessStatus(str, Enum):
    """Status of a work order's dispatch readiness."""

    ready = "ready"
    blocked = "blocked"
    conditional = "conditional"
    escalate = "escalate"

    @property
    def can_dispatch(self) -> bool:
        """Whether this status allows dispatch to proceed."""
        return self in (ReadinessStatus.ready, ReadinessStatus.conditional)
