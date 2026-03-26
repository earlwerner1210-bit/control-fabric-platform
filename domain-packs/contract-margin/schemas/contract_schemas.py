"""Pydantic v2 models for contract parsing, margin analysis, and billability decisions."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from ..taxonomy.contract_taxonomy import BillableCategory, ClauseType, ContractType

# ---------------------------------------------------------------------------
# Core parsed objects
# ---------------------------------------------------------------------------


class ExtractedClause(BaseModel):
    """A single clause extracted from a contract document."""

    clause_id: str = Field(..., description="Unique identifier for the clause")
    clause_type: ClauseType
    section_ref: str = Field(
        "", description="Section reference in the original document, e.g. '4.2.1'"
    )
    text: str = Field(..., description="Full text of the clause")
    parties: list[str] = Field(
        default_factory=list, description="Parties referenced in this clause"
    )
    effective_date: date | None = None
    expiry_date: date | None = None
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")


class SLAEntry(BaseModel):
    """A single SLA metric extracted from a contract."""

    metric_name: str = Field(..., description="Name of the SLA metric, e.g. 'Uptime'")
    target_value: float = Field(..., description="Numeric target, e.g. 99.95")
    unit: str = Field("%", description="Unit of measurement")
    measurement_period: str = Field("monthly", description="Measurement window")
    penalty_on_breach: str | None = Field(
        None, description="Penalty description if SLA is breached"
    )
    clause_ref: str = Field("", description="Reference to the originating clause")


class RateCardEntry(BaseModel):
    """A single rate extracted from a contract rate card."""

    role_or_item: str = Field(..., description="Role title or line item description")
    rate: float = Field(..., ge=0, description="Rate amount")
    currency: str = Field("USD", description="Currency code")
    rate_unit: str = Field("hourly", description="Billing unit: hourly, daily, per_unit, etc.")
    effective_from: date | None = None
    effective_to: date | None = None
    clause_ref: str = Field("", description="Reference to the originating clause")


class Obligation(BaseModel):
    """A contractual obligation extracted from clauses."""

    obligation_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    description: str
    obligated_party: str = Field(..., description="The party who must fulfil this obligation")
    due_date: date | None = None
    recurrence: str | None = Field(
        None, description="Recurrence pattern, e.g. 'monthly', 'quarterly'"
    )
    linked_clause_ids: list[str] = Field(default_factory=list)
    status: str = Field("open", description="Current status: open, met, breached, waived")


class PenaltyCondition(BaseModel):
    """A penalty or liquidated damages condition extracted from a contract."""

    penalty_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    trigger_condition: str = Field(..., description="Condition that triggers the penalty")
    penalty_type: str = Field(
        "liquidated_damages",
        description="Type: liquidated_damages, service_credit, termination_right",
    )
    amount: float | None = None
    amount_formula: str | None = Field(
        None, description="Formula for computing penalty, e.g. '5% of monthly fee per day'"
    )
    cap: float | None = Field(None, description="Maximum penalty cap amount")
    currency: str = Field("USD")
    linked_clause_ids: list[str] = Field(default_factory=list)


class BillableEvent(BaseModel):
    """A billable event or activity extracted from contract scope."""

    event_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    description: str
    category: BillableCategory
    rate_ref: str | None = Field(None, description="Reference to the applicable rate card entry")
    requires_approval: bool = Field(
        False, description="Whether pre-approval is needed before billing"
    )
    excluded_activities: list[str] = Field(
        default_factory=list, description="Activities explicitly excluded from billing"
    )
    linked_clause_ids: list[str] = Field(default_factory=list)


class ParsedContract(BaseModel):
    """Top-level model representing a fully parsed contract."""

    contract_id: str = Field(default_factory=lambda: str(uuid4()))
    contract_type: ContractType
    title: str
    parties: list[str] = Field(default_factory=list)
    effective_date: date | None = None
    expiry_date: date | None = None
    parent_contract_id: str | None = None
    billing_category: BillableCategory | None = None
    total_value: float | None = None
    currency: str = Field("USD")
    clauses: list[ExtractedClause] = Field(default_factory=list)
    sla_entries: list[SLAEntry] = Field(default_factory=list)
    rate_card: list[RateCardEntry] = Field(default_factory=list)
    obligations: list[Obligation] = Field(default_factory=list)
    penalties: list[PenaltyCondition] = Field(default_factory=list)
    billable_events: list[BillableEvent] = Field(default_factory=list)
    raw_text_hash: str | None = None
    parsed_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Decision & analysis models
# ---------------------------------------------------------------------------


class RuleResult(BaseModel):
    """Outcome of a single rule evaluation."""

    rule_name: str
    passed: bool
    message: str
    severity: str = Field("info", description="Severity: info, warning, critical")


class BillabilityDecision(BaseModel):
    """Result of evaluating whether a work event is billable under a contract."""

    billable: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(
        default_factory=list, description="IDs of clauses/events that support this decision"
    )
    reasons: list[str] = Field(default_factory=list)
    rule_results: list[RuleResult] = Field(default_factory=list)
    category: BillableCategory | None = None
    applicable_rate: float | None = None


class LeakageDriver(str, Enum):
    """Categories of margin leakage."""

    unbilled_work = "unbilled_work"
    rate_erosion = "rate_erosion"
    scope_creep = "scope_creep"
    missing_change_order = "missing_change_order"
    penalty_exposure = "penalty_exposure"
    unrecovered_cost = "unrecovered_cost"


class RecoveryRecommendation(BaseModel):
    """A recommended action to recover leaked margin."""

    recommendation_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    driver: LeakageDriver
    action: str
    estimated_recovery: float | None = None
    currency: str = Field("USD")
    priority: str = Field("medium", description="Priority: low, medium, high, critical")
    evidence_ids: list[str] = Field(default_factory=list)


class MarginLeakageDiagnosis(BaseModel):
    """Full diagnosis of margin leakage on a contract or portfolio."""

    verdict: str = Field(..., description="Overall verdict: healthy, at_risk, leaking, critical")
    leakage_drivers: list[LeakageDriver] = Field(default_factory=list)
    recovery_recommendations: list[RecoveryRecommendation] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    executive_summary: str = Field("", description="Human-readable summary for stakeholders")
    total_estimated_leakage: float | None = None
    currency: str = Field("USD")


class PenaltyExposureSummary(BaseModel):
    """Summary of penalty exposure across a contract."""

    contract_id: str
    total_penalties: int = 0
    total_exposure_amount: float | None = None
    currency: str = Field("USD")
    unmitigated_penalties: list[PenaltyCondition] = Field(default_factory=list)
    mitigated_penalties: list[PenaltyCondition] = Field(default_factory=list)
    highest_risk_penalty: PenaltyCondition | None = None


class ContractCompileSummary(BaseModel):
    """High-level summary of a compiled contract analysis."""

    contract_id: str
    contract_type: ContractType
    title: str
    total_clauses: int = 0
    total_obligations: int = 0
    open_obligations: int = 0
    total_sla_metrics: int = 0
    total_rate_card_entries: int = 0
    total_penalties: int = 0
    billing_category: BillableCategory | None = None
    total_value: float | None = None
    currency: str = Field("USD")
    risk_score: float = Field(0.0, ge=0.0, le=1.0, description="Computed contract risk score")


class ObligationRegister(BaseModel):
    """Register of all obligations across one or more contracts."""

    register_id: str = Field(default_factory=lambda: str(uuid4()))
    contract_ids: list[str] = Field(default_factory=list)
    obligations: list[Obligation] = Field(default_factory=list)
    total_open: int = 0
    total_met: int = 0
    total_breached: int = 0
    generated_at: datetime = Field(default_factory=datetime.utcnow)
