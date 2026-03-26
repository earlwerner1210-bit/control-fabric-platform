"""
Pydantic models for contract margin domain pack.

Defines all schemas for contract parsing, clause extraction, billability
assessment, leakage detection, penalty analysis, and recovery recommendations.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ClauseType(str, Enum):
    """Classification of contract clause types."""
    obligation = "obligation"
    sla = "sla"
    penalty = "penalty"
    rate = "rate"
    scope = "scope"
    termination = "termination"
    liability = "liability"
    billing = "billing"
    re_attendance = "re_attendance"
    evidence = "evidence"
    service_credit = "service_credit"
    safety = "safety"
    nrswa = "nrswa"


class ContractType(str, Enum):
    """Type of contract document."""
    master_services = "master_services"
    statement_of_work = "statement_of_work"
    change_order = "change_order"
    amendment = "amendment"
    framework = "framework"


class ScopeType(str, Enum):
    """Scope classification for activities."""
    in_scope = "in_scope"
    out_of_scope = "out_of_scope"
    conditional = "conditional"


class BillableCategory(str, Enum):
    """Category of billable work."""
    standard = "standard"
    emergency = "emergency"
    overtime = "overtime"
    materials = "materials"
    subcontractor = "subcontractor"
    mobilisation = "mobilisation"


class RecoveryType(str, Enum):
    """Type of commercial recovery action."""
    backbill = "backbill"
    rate_adjustment = "rate_adjustment"
    penalty_waiver = "penalty_waiver"
    change_order = "change_order"
    evidence_collection = "evidence_collection"
    dispute = "dispute"


class PriorityLevel(str, Enum):
    """Priority level for SLAs and obligations."""
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


# ---------------------------------------------------------------------------
# Clause / Segment Models
# ---------------------------------------------------------------------------

class ClauseSegment(BaseModel):
    """A segment within a clause, representing a parsed portion of text."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    clause_id: str = Field(..., description="Parent clause identifier")
    text: str = Field(..., min_length=1, description="Segment text content")
    start_offset: int = Field(..., ge=0, description="Character start offset in source")
    end_offset: int = Field(..., ge=0, description="Character end offset in source")
    segment_type: str = Field(
        default="body",
        description="Segment type: header, body, table, list_item, reference",
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")

    @field_validator("end_offset")
    @classmethod
    def end_after_start(cls, v: int, info) -> int:
        start = info.data.get("start_offset", 0)
        if v < start:
            raise ValueError("end_offset must be >= start_offset")
        return v


class ExtractedClause(BaseModel):
    """A clause extracted from a contract document."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ClauseType = Field(..., description="Classification of clause type")
    text: str = Field(..., min_length=1, description="Full clause text")
    section: str = Field(default="", description="Section reference in source document")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Extraction confidence")
    risk_level: PriorityLevel = Field(
        default=PriorityLevel.medium,
        description="Risk level associated with this clause",
    )
    segments: list[ClauseSegment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# SLA & Rate Card
# ---------------------------------------------------------------------------

class SLAEntry(BaseModel):
    """A single SLA row defining response/resolution targets."""
    priority: PriorityLevel = Field(..., description="SLA priority level")
    response_time_hours: float = Field(..., gt=0, description="Max response time in hours")
    resolution_time_hours: float = Field(..., gt=0, description="Max resolution time in hours")
    availability: float = Field(
        default=99.5, ge=0.0, le=100.0,
        description="Service availability percentage target",
    )
    penalty_percentage: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="Penalty as percentage of monthly invoice for breach",
    )
    measurement_window: str = Field(
        default="monthly",
        description="Measurement window: monthly, quarterly, annual",
    )

    @field_validator("measurement_window")
    @classmethod
    def validate_window(cls, v: str) -> str:
        allowed = {"monthly", "quarterly", "annual", "weekly"}
        if v.lower() not in allowed:
            raise ValueError(f"measurement_window must be one of {allowed}")
        return v.lower()


class RateCardEntry(BaseModel):
    """A single rate card entry for a billable activity."""
    activity: str = Field(..., min_length=1, description="Activity name or code")
    unit: str = Field(default="each", description="Unit of measure: each, hour, metre, day")
    rate: float = Field(..., ge=0.0, description="Rate value")
    currency: str = Field(default="GBP", description="ISO 4217 currency code")
    effective_from: Optional[date] = Field(default=None, description="Rate effective from date")
    effective_to: Optional[date] = Field(default=None, description="Rate effective to date")
    multipliers: dict[str, float] = Field(
        default_factory=dict,
        description="Rate multipliers, e.g. {'overtime': 1.5, 'weekend': 2.0}",
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if len(v) != 3 or not v.isalpha():
            raise ValueError("currency must be a 3-letter ISO 4217 code")
        return v.upper()

    def is_active(self, check_date: Optional[date] = None) -> bool:
        """Check whether this rate card entry is active on the given date."""
        ref = check_date or date.today()
        if self.effective_from and ref < self.effective_from:
            return False
        if self.effective_to and ref > self.effective_to:
            return False
        return True

    def effective_rate(self, category: str = "standard") -> float:
        """Return the rate after applying the multiplier for the given category."""
        multiplier = self.multipliers.get(category, 1.0)
        return round(self.rate * multiplier, 2)


# ---------------------------------------------------------------------------
# Scope, Obligation, Penalty
# ---------------------------------------------------------------------------

class ScopeBoundary(BaseModel):
    """Defines a scope boundary for contract activities."""
    scope_type: ScopeType = Field(..., description="In-scope, out-of-scope, or conditional")
    description: str = Field(default="", description="Human-readable scope description")
    activities: list[str] = Field(default_factory=list, description="Activity names covered")
    conditions: list[str] = Field(
        default_factory=list,
        description="Conditions that must hold for conditional scope",
    )


class Obligation(BaseModel):
    """A contractual obligation extracted from a clause."""
    clause_id: str = Field(..., description="Source clause identifier")
    description: str = Field(..., min_length=1, description="Obligation description")
    frequency: str = Field(
        default="per_event",
        description="Frequency: per_event, daily, weekly, monthly, quarterly, annual",
    )
    owner: str = Field(default="provider", description="Obligation owner: provider, client, both")
    evidence_required: list[str] = Field(
        default_factory=list,
        description="List of evidence types required to prove fulfilment",
    )
    deadline_days: int = Field(
        default=30, ge=0,
        description="Number of days from trigger to complete obligation",
    )


class PenaltyCondition(BaseModel):
    """A penalty condition extracted from a contract clause."""
    clause_id: str = Field(..., description="Source clause identifier")
    description: str = Field(..., min_length=1, description="Penalty description")
    trigger: str = Field(..., description="Condition that triggers the penalty")
    penalty_type: str = Field(
        default="percentage",
        description="Type: percentage, fixed, service_credit, liquidated_damages",
    )
    penalty_amount: float = Field(default=0.0, ge=0.0, description="Penalty amount or percentage")
    cap: Optional[float] = Field(default=None, ge=0.0, description="Maximum penalty cap")
    grace_period_days: int = Field(default=0, ge=0, description="Grace period before penalty applies")
    cure_period_days: int = Field(default=0, ge=0, description="Cure period to rectify breach")


# ---------------------------------------------------------------------------
# Billability & Leakage
# ---------------------------------------------------------------------------

class BillableEvent(BaseModel):
    """Defines a billable event with its prerequisites and evidence."""
    activity: str = Field(..., min_length=1, description="Activity name")
    category: BillableCategory = Field(default=BillableCategory.standard)
    rate: float = Field(..., ge=0.0, description="Applicable rate")
    unit: str = Field(default="each", description="Unit of measure")
    prerequisites: list[str] = Field(
        default_factory=list,
        description="Prerequisites that must be met before billing",
    )
    evidence_required: list[str] = Field(
        default_factory=list,
        description="Evidence items required to support billing",
    )


class LeakageTrigger(BaseModel):
    """A detected revenue leakage trigger."""
    trigger_type: str = Field(..., description="Type of leakage trigger")
    description: str = Field(..., min_length=1, description="Human-readable description")
    severity: PriorityLevel = Field(default=PriorityLevel.medium)
    estimated_impact_value: float = Field(default=0.0, ge=0.0, description="Estimated GBP impact")
    clause_refs: list[str] = Field(default_factory=list, description="Related clause IDs")
    evidence: list[str] = Field(default_factory=list, description="Supporting evidence items")


class BillabilityDecision(BaseModel):
    """Result of a billability assessment for a work activity."""
    billable: bool = Field(..., description="Whether the activity is billable")
    category: BillableCategory = Field(default=BillableCategory.standard)
    rate_applied: float = Field(default=0.0, ge=0.0, description="Rate applied for billing")
    reasons: list[str] = Field(default_factory=list, description="Reasons for the decision")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    rule_results: dict[str, bool] = Field(
        default_factory=dict,
        description="Results of individual rule evaluations",
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Evidence references supporting the decision",
    )


# ---------------------------------------------------------------------------
# Parsed Contract (aggregate)
# ---------------------------------------------------------------------------

class ParsedContract(BaseModel):
    """Full parsed representation of a contract document."""
    document_type: str = Field(default="contract", description="Document type identifier")
    title: str = Field(default="", description="Contract title")
    effective_date: Optional[date] = Field(default=None)
    expiry_date: Optional[date] = Field(default=None)
    parties: list[str] = Field(default_factory=list, description="Contracting parties")
    contract_type: ContractType = Field(default=ContractType.master_services)
    governing_law: str = Field(default="England and Wales")
    payment_terms: str = Field(default="30 days net")
    clauses: list[ExtractedClause] = Field(default_factory=list)
    sla_table: list[SLAEntry] = Field(default_factory=list)
    rate_card: list[RateCardEntry] = Field(default_factory=list)
    scope_boundaries: list[ScopeBoundary] = Field(default_factory=list)
    obligations: list[Obligation] = Field(default_factory=list)
    penalties: list[PenaltyCondition] = Field(default_factory=list)
    billable_events: list[BillableEvent] = Field(default_factory=list)

    def is_active(self, check_date: Optional[date] = None) -> bool:
        """Return True if the contract is active on the given date."""
        ref = check_date or date.today()
        if self.effective_date and ref < self.effective_date:
            return False
        if self.expiry_date and ref > self.expiry_date:
            return False
        return True


# ---------------------------------------------------------------------------
# Summary & Diagnosis
# ---------------------------------------------------------------------------

class ContractCompileSummary(BaseModel):
    """High-level summary of a parsed contract for dashboards and reports."""
    contract_title: str = Field(default="")
    parties: list[str] = Field(default_factory=list)
    effective_date: Optional[date] = Field(default=None)
    expiry_date: Optional[date] = Field(default=None)
    clause_count: int = Field(default=0, ge=0)
    obligation_count: int = Field(default=0, ge=0)
    penalty_count: int = Field(default=0, ge=0)
    billable_event_count: int = Field(default=0, ge=0)
    sla_entry_count: int = Field(default=0, ge=0)
    scope_boundary_count: int = Field(default=0, ge=0)
    risk_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Count of clauses by risk level, e.g. {'high': 3, 'medium': 5}",
    )

    @classmethod
    def from_parsed_contract(cls, pc: ParsedContract) -> "ContractCompileSummary":
        """Build a summary from a fully parsed contract."""
        risk_counts: dict[str, int] = {}
        for clause in pc.clauses:
            key = clause.risk_level.value
            risk_counts[key] = risk_counts.get(key, 0) + 1
        return cls(
            contract_title=pc.title,
            parties=pc.parties,
            effective_date=pc.effective_date,
            expiry_date=pc.expiry_date,
            clause_count=len(pc.clauses),
            obligation_count=len(pc.obligations),
            penalty_count=len(pc.penalties),
            billable_event_count=len(pc.billable_events),
            sla_entry_count=len(pc.sla_table),
            scope_boundary_count=len(pc.scope_boundaries),
            risk_summary=risk_counts,
        )


class CommercialRecoveryRecommendation(BaseModel):
    """A recommendation for recovering leaked revenue."""
    recommendation_type: RecoveryType = Field(..., description="Type of recovery action")
    description: str = Field(..., min_length=1)
    estimated_recovery_value: float = Field(default=0.0, ge=0.0)
    evidence_clause_refs: list[str] = Field(default_factory=list)
    priority: PriorityLevel = Field(default=PriorityLevel.medium)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class CommercialEvidenceBundle(BaseModel):
    """Aggregated evidence bundle supporting a margin diagnosis."""
    contract_evidence: list[str] = Field(default_factory=list)
    work_order_evidence: list[str] = Field(default_factory=list)
    execution_evidence: list[str] = Field(default_factory=list)
    billing_evidence: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(
        default_factory=list,
        description="Identified evidence gaps that weaken the case",
    )

    def completeness_score(self) -> float:
        """Return a 0-1 score indicating how complete the evidence bundle is."""
        total_items = (
            len(self.contract_evidence)
            + len(self.work_order_evidence)
            + len(self.execution_evidence)
            + len(self.billing_evidence)
        )
        gap_count = len(self.gaps)
        if total_items + gap_count == 0:
            return 0.0
        return round(total_items / (total_items + gap_count), 2)


class MarginDiagnosisResult(BaseModel):
    """Complete result of a margin diagnosis for a work activity or contract."""
    verdict: str = Field(..., description="Overall verdict: billable, non_billable, partial, review")
    billability: BillabilityDecision = Field(...)
    leakage_triggers: list[LeakageTrigger] = Field(default_factory=list)
    penalty_exposure: float = Field(default=0.0, ge=0.0, description="Total penalty exposure GBP")
    recovery_recommendations: list[CommercialRecoveryRecommendation] = Field(default_factory=list)
    evidence_bundle: CommercialEvidenceBundle = Field(
        default_factory=CommercialEvidenceBundle,
    )
    executive_summary: str = Field(default="", description="Plain-English executive summary")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)

    @field_validator("verdict")
    @classmethod
    def validate_verdict(cls, v: str) -> str:
        allowed = {"billable", "non_billable", "partial", "review"}
        if v not in allowed:
            raise ValueError(f"verdict must be one of {allowed}")
        return v
