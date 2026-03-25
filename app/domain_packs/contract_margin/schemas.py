"""Contract & Margin domain pack schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import date

from pydantic import BaseModel, Field


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


class BillableCategory(str, enum.Enum):
    time_and_materials = "time_and_materials"
    fixed_price = "fixed_price"
    milestone = "milestone"
    cost_plus = "cost_plus"
    retainer = "retainer"


class ExtractedClause(BaseModel):
    id: str
    type: ClauseType
    text: str
    section: str = ""
    confidence: float = 1.0


class SLAEntry(BaseModel):
    priority: str
    response_time_hours: float
    resolution_time_hours: float
    availability: str = "business_hours"


class RateCardEntry(BaseModel):
    activity: str
    unit: str
    rate: float
    currency: str = "USD"


class Obligation(BaseModel):
    clause_id: str
    description: str
    owner: str = ""
    due_type: str = ""  # ongoing, one_time, periodic


class PenaltyCondition(BaseModel):
    clause_id: str
    description: str
    trigger: str = ""
    penalty_amount: str = ""
    penalty_type: str = ""  # percentage, fixed, per_breach


class BillableEvent(BaseModel):
    activity: str
    rate: float
    unit: str
    category: BillableCategory = BillableCategory.time_and_materials
    conditions: list[str] = []


class ParsedContract(BaseModel):
    document_type: str
    title: str = ""
    effective_date: date | None = None
    expiry_date: date | None = None
    parties: list[str] = []
    clauses: list[ExtractedClause] = []
    sla_table: list[SLAEntry] = []
    rate_card: list[RateCardEntry] = []
    contract_type: ContractType = ContractType.master_services


class BillabilityDecision(BaseModel):
    billable: bool
    confidence: float
    evidence_ids: list[uuid.UUID] = []
    reasons: list[str] = []
    rate_applied: float | None = None
    category: BillableCategory | None = None


class LeakageTrigger(BaseModel):
    trigger_type: str
    description: str
    severity: str
    estimated_impact: str = ""
    evidence_ids: list[uuid.UUID] = []


class MarginLeakageDiagnosis(BaseModel):
    verdict: str  # billable, non_billable, under_recovery, penalty_risk, unknown
    leakage_drivers: list[str] = []
    recovery_recommendations: list[str] = []
    evidence_ids: list[uuid.UUID] = []
    executive_summary: str = ""
    total_leakage_triggers: int = 0


class ContractCompileSummary(BaseModel):
    contract_title: str = ""
    parties: list[str] = []
    obligation_count: int = 0
    penalty_count: int = 0
    billable_event_count: int = 0
    sla_entry_count: int = 0
    control_object_ids: list[uuid.UUID] = []
