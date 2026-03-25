"""Contract & Margin domain pack schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ContractType(str, enum.Enum):
    master_services = "master_services"
    work_order = "work_order"
    change_order = "change_order"
    framework = "framework"
    amendment = "amendment"


class ClauseType(str, enum.Enum):
    obligation = "obligation"
    penalty = "penalty"
    sla = "sla"
    rate = "rate"
    scope = "scope"
    termination = "termination"
    liability = "liability"
    indemnity = "indemnity"
    warranty = "warranty"
    confidentiality = "confidentiality"
    force_majeure = "force_majeure"
    governing_law = "governing_law"
    dispute_resolution = "dispute_resolution"


class BillableCategory(str, enum.Enum):
    time_and_materials = "time_and_materials"
    fixed_price = "fixed_price"
    milestone = "milestone"
    cost_plus = "cost_plus"
    retainer = "retainer"


class ScopeType(str, enum.Enum):
    in_scope = "in_scope"
    out_of_scope = "out_of_scope"
    conditional = "conditional"


class RecoveryType(str, enum.Enum):
    change_order = "change_order"
    rate_adjustment = "rate_adjustment"
    penalty_waiver = "penalty_waiver"
    scope_clarification = "scope_clarification"
    backbill = "backbill"
    credit_note = "credit_note"


class PriorityLevel(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ObligationDueType(str, enum.Enum):
    ongoing = "ongoing"
    one_time = "one_time"
    periodic = "periodic"
    upon_trigger = "upon_trigger"


class ObligationStatus(str, enum.Enum):
    active = "active"
    fulfilled = "fulfilled"
    breached = "breached"
    waived = "waived"
    expired = "expired"


class PenaltyType(str, enum.Enum):
    percentage = "percentage"
    fixed = "fixed"
    per_breach = "per_breach"
    tiered = "tiered"
    capped = "capped"


# ---------------------------------------------------------------------------
# Core extracted objects
# ---------------------------------------------------------------------------

class ExtractedClause(BaseModel):
    id: str
    type: ClauseType
    text: str
    section: str = ""
    confidence: float = 1.0


class ClauseSegment(BaseModel):
    """Fine-grained clause segment with positional offsets."""
    id: str
    clause_number: str
    heading: str = ""
    text: str
    clause_type: ClauseType
    section_ref: str = ""
    parent_clause_id: str | None = None
    metadata: dict = Field(default_factory=dict)
    source_offset_start: int = 0
    source_offset_end: int = 0
    confidence: float = 1.0


class SLAEntry(BaseModel):
    priority: str
    response_time_hours: float
    resolution_time_hours: float
    availability: str = "business_hours"
    penalty_percentage: float | None = None
    measurement_window: str = "monthly"


class RateCardEntry(BaseModel):
    activity: str
    unit: str
    rate: float
    currency: str = "USD"
    effective_from: date | None = None
    effective_to: date | None = None
    escalation_rate: float | None = None
    minimum_charge: float | None = None
    overtime_multiplier: float | None = None


class Obligation(BaseModel):
    clause_id: str
    description: str
    owner: str = ""
    due_type: str = ""  # ongoing, one_time, periodic
    risk_level: str = "medium"
    status: str = "active"
    due_date: date | None = None
    dependencies: list[str] = Field(default_factory=list)


class PenaltyCondition(BaseModel):
    clause_id: str
    description: str
    trigger: str = ""
    penalty_amount: str = ""
    penalty_type: str = ""  # percentage, fixed, per_breach
    cap: float | None = None
    grace_period_days: int | None = None
    cure_period_days: int | None = None
    escalation_schedule: list[dict] = Field(default_factory=list)


class BillableEvent(BaseModel):
    activity: str
    rate: float
    unit: str
    category: BillableCategory = BillableCategory.time_and_materials
    conditions: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    requires_work_order: bool = False


# ---------------------------------------------------------------------------
# Scope boundary
# ---------------------------------------------------------------------------

class ScopeBoundaryObject(BaseModel):
    """Defines whether a service/activity is in-scope, out-of-scope, or conditional."""
    scope_type: ScopeType
    description: str
    conditions: list[str] = Field(default_factory=list)
    clause_refs: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------

class CommercialRecoveryRecommendation(BaseModel):
    """A recommended action to recover leaked margin."""
    recommendation_type: RecoveryType
    description: str
    estimated_recovery_value: float = 0.0
    evidence_clause_refs: list[str] = Field(default_factory=list)
    priority: PriorityLevel = PriorityLevel.medium
    confidence: float = 0.0
    timeframe_days: int | None = None
    prerequisites: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsed contract
# ---------------------------------------------------------------------------

class ParsedContract(BaseModel):
    document_type: str
    title: str = ""
    effective_date: date | None = None
    expiry_date: date | None = None
    renewal_date: date | None = None
    parties: list[str] = Field(default_factory=list)
    clauses: list[ExtractedClause] = Field(default_factory=list)
    clause_segments: list[ClauseSegment] = Field(default_factory=list)
    sla_table: list[SLAEntry] = Field(default_factory=list)
    rate_card: list[RateCardEntry] = Field(default_factory=list)
    scope_boundaries: list[ScopeBoundaryObject] = Field(default_factory=list)
    contract_type: ContractType = ContractType.master_services
    governing_law: str = ""
    payment_terms: str = ""


# ---------------------------------------------------------------------------
# Billability
# ---------------------------------------------------------------------------

class BillabilityDecision(BaseModel):
    billable: bool
    confidence: float
    evidence_ids: list[uuid.UUID] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    rate_applied: float | None = None
    category: BillableCategory | None = None
    rule_results: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Leakage
# ---------------------------------------------------------------------------

class LeakageTrigger(BaseModel):
    trigger_type: str
    description: str
    severity: str
    estimated_impact: str = ""
    estimated_impact_value: float = 0.0
    evidence_ids: list[uuid.UUID] = Field(default_factory=list)
    clause_refs: list[str] = Field(default_factory=list)
    recommended_action: str = ""


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------

class MarginLeakageDiagnosis(BaseModel):
    verdict: str  # billable, non_billable, under_recovery, penalty_risk, unknown
    leakage_drivers: list[str] = Field(default_factory=list)
    recovery_recommendations: list[str] = Field(default_factory=list)
    evidence_ids: list[uuid.UUID] = Field(default_factory=list)
    executive_summary: str = ""
    total_leakage_triggers: int = 0


class MarginDiagnosisResult(BaseModel):
    """Full margin diagnosis with typed recovery and penalty data."""
    verdict: str
    billability_assessment: BillabilityDecision | None = None
    leakage_triggers: list[LeakageTrigger] = Field(default_factory=list)
    penalty_exposure: list[PenaltyCondition] = Field(default_factory=list)
    recovery_recommendations: list[CommercialRecoveryRecommendation] = Field(default_factory=list)
    executive_summary: str = ""
    total_at_risk_value: float = 0.0
    evidence_ids: list[uuid.UUID] = Field(default_factory=list)
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Obligation register
# ---------------------------------------------------------------------------

class ObligationRegister(BaseModel):
    """Aggregated view of all contractual obligations."""
    obligations: list[Obligation] = Field(default_factory=list)
    total_count: int = 0
    by_owner: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    high_risk_obligations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Penalty exposure summary
# ---------------------------------------------------------------------------

class PenaltyExposureSummary(BaseModel):
    """Aggregated penalty exposure across a contract."""
    total_penalties: int = 0
    active_breaches: int = 0
    estimated_financial_exposure: float = 0.0
    breach_details: list[dict] = Field(default_factory=list)
    mitigation_actions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Compile summary
# ---------------------------------------------------------------------------

class ContractCompileSummary(BaseModel):
    contract_title: str = ""
    parties: list[str] = Field(default_factory=list)
    obligation_count: int = 0
    penalty_count: int = 0
    billable_event_count: int = 0
    sla_entry_count: int = 0
    scope_boundary_count: int = 0
    leakage_trigger_count: int = 0
    total_rate_card_value: float = 0.0
    control_object_ids: list[uuid.UUID] = Field(default_factory=list)
