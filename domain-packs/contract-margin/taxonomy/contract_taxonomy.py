"""Taxonomy enumerations for contract types, clause classifications, and billing categories."""

from enum import Enum


class ContractType(str, Enum):
    """Classification of telecom contract types."""

    master_services = "master_services"
    work_order = "work_order"
    change_order = "change_order"
    framework = "framework"
    amendment = "amendment"

    @property
    def requires_parent(self) -> bool:
        """Whether this contract type typically references a parent contract."""
        return self in (
            ContractType.work_order,
            ContractType.change_order,
            ContractType.amendment,
        )

    @property
    def is_standalone(self) -> bool:
        """Whether this contract type can exist independently."""
        return self in (ContractType.master_services, ContractType.framework)


class ClauseType(str, Enum):
    """Classification of contract clause types."""

    obligation = "obligation"
    penalty = "penalty"
    sla = "sla"
    rate = "rate"
    scope = "scope"
    termination = "termination"
    liability = "liability"
    indemnity = "indemnity"

    @property
    def is_financial(self) -> bool:
        """Whether this clause type has direct financial impact."""
        return self in (
            ClauseType.penalty,
            ClauseType.rate,
            ClauseType.liability,
            ClauseType.indemnity,
        )

    @property
    def is_operational(self) -> bool:
        """Whether this clause type governs operational requirements."""
        return self in (
            ClauseType.obligation,
            ClauseType.sla,
            ClauseType.scope,
        )


class BillableCategory(str, Enum):
    """Classification of billing models used in telecom contracts."""

    time_and_materials = "time_and_materials"
    fixed_price = "fixed_price"
    milestone = "milestone"
    cost_plus = "cost_plus"
    retainer = "retainer"

    @property
    def is_variable(self) -> bool:
        """Whether the billing amount varies based on actual work performed."""
        return self in (
            BillableCategory.time_and_materials,
            BillableCategory.cost_plus,
        )

    @property
    def requires_rate_card(self) -> bool:
        """Whether this billing category requires an associated rate card."""
        return self in (
            BillableCategory.time_and_materials,
            BillableCategory.cost_plus,
            BillableCategory.retainer,
        )
