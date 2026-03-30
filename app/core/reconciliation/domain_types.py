"""Wave 2 reconciliation domain types — strongly typed constructs for cross-plane reconciliation."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any, NewType

from pydantic import BaseModel, Field

from app.core.types import (
    ConfidenceScore,
    ControlLinkId,
    ControlObjectId,
    EvidenceRef,
    PlaneType,
    deterministic_hash,
)

ReconciliationRunId = NewType("ReconciliationRunId", uuid.UUID)
ReconciliationCaseId = NewType("ReconciliationCaseId", uuid.UUID)
ReconciliationRuleId = NewType("ReconciliationRuleId", str)
ReconciliationRuleVersion = NewType("ReconciliationRuleVersion", int)
MatchCandidateId = NewType("MatchCandidateId", uuid.UUID)
MatchScore = NewType("MatchScore", float)
ReconciliationHash = NewType("ReconciliationHash", str)


def new_run_id() -> ReconciliationRunId:
    return ReconciliationRunId(uuid.uuid4())


def new_case_id() -> ReconciliationCaseId:
    return ReconciliationCaseId(uuid.uuid4())


def new_candidate_id() -> MatchCandidateId:
    return MatchCandidateId(uuid.uuid4())


class ReconciliationOutcomeType(str, enum.Enum):
    FULLY_RECONCILED = "fully-reconciled"
    CANDIDATE_MATCH = "candidate-match"
    MISMATCH_DETECTED = "mismatch-detected"
    DUPLICATE_DETECTED = "duplicate-detected"
    COVERAGE_GAP = "coverage-gap"
    DISPUTED = "disputed"
    INSUFFICIENT_EVIDENCE = "insufficient-evidence"


class ReconciliationStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ReconciliationCaseStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class ReconciliationCasePriority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReconciliationDeterminismLevel(str, enum.Enum):
    FULLY_DETERMINISTIC = "fully-deterministic"
    RULE_DRIVEN = "rule-driven"
    THRESHOLD_BASED = "threshold-based"


class CrossPlaneMismatchCategory(str, enum.Enum):
    MISSING_IN_COMMERCIAL = "missing-in-commercial"
    MISSING_IN_FIELD = "missing-in-field"
    MISSING_IN_SERVICE = "missing-in-service"
    IDENTIFIER_CONFLICT = "identifier-conflict"
    STATE_CONFLICT = "state-conflict"
    QUANTITY_CONFLICT = "quantity-conflict"
    COST_CONFLICT = "cost-conflict"
    SERVICE_PRESENCE_CONFLICT = "service-presence-conflict"
    CHRONOLOGY_CONFLICT = "chronology-conflict"
    UNSUPPORTED_LINKAGE = "unsupported-linkage"
    DUPLICATE_CANDIDATE = "duplicate-candidate"
    EVIDENCE_INSUFFICIENT = "evidence-insufficient"


MISSING_CATEGORY_BY_PLANE: dict[PlaneType, CrossPlaneMismatchCategory] = {
    PlaneType.COMMERCIAL: CrossPlaneMismatchCategory.MISSING_IN_COMMERCIAL,
    PlaneType.FIELD: CrossPlaneMismatchCategory.MISSING_IN_FIELD,
    PlaneType.SERVICE: CrossPlaneMismatchCategory.MISSING_IN_SERVICE,
}


class ReconciliationScopeType(str, enum.Enum):
    BY_OBJECT_ID = "by-object-id"
    BY_GRAPH_SLICE = "by-graph-slice"
    BY_CORRELATION_KEY = "by-correlation-key"
    BY_PLANE_COMBINATION = "by-plane-combination"
    BY_OBJECT_KIND = "by-object-kind"
    BY_EXPLICIT_TARGETS = "by-explicit-targets"


class ReconciliationScope(BaseModel):
    scope_type: ReconciliationScopeType
    planes: list[PlaneType]
    domains: list[str] = Field(default_factory=list)
    object_kinds: list[str] = Field(default_factory=list)
    tenant_id: uuid.UUID


class ReconciliationTarget(BaseModel):
    object_ids: list[ControlObjectId] = Field(default_factory=list)
    correlation_keys: dict[str, str] = Field(default_factory=dict)
    graph_slice_root_ids: list[ControlObjectId] = Field(default_factory=list)
    plane_combination: list[PlaneType] = Field(default_factory=list)
    object_kind_filter: list[str] = Field(default_factory=list)


class ReconciliationRuleContext(BaseModel):
    tenant_id: uuid.UUID
    scope: ReconciliationScope
    source_object_ids: list[ControlObjectId] = Field(default_factory=list)
    target_object_ids: list[ControlObjectId] = Field(default_factory=list)
    available_link_ids: list[ControlLinkId] = Field(default_factory=list)
    correlation_keys: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReconciliationEvidenceBundle(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    source_object_ids: list[ControlObjectId] = Field(default_factory=list)
    target_object_ids: list[ControlObjectId] = Field(default_factory=list)
    link_ids: list[ControlLinkId] = Field(default_factory=list)

    @property
    def total_evidence(self) -> int:
        return len(self.evidence_refs)


class ReconciliationMismatch(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    category: CrossPlaneMismatchCategory
    source_object_id: ControlObjectId | None = None
    target_object_id: ControlObjectId | None = None
    source_plane: PlaneType | None = None
    target_plane: PlaneType | None = None
    involved_link_ids: list[ControlLinkId] = Field(default_factory=list)
    description: str
    expected_value: Any = None
    actual_value: Any = None
    deviation: float | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    rule_id: ReconciliationRuleId | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_hash_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "source_object_id": str(self.source_object_id) if self.source_object_id else None,
            "target_object_id": str(self.target_object_id) if self.target_object_id else None,
            "expected_value": str(self.expected_value),
            "actual_value": str(self.actual_value),
            "rule_id": self.rule_id,
        }


class MatchScoreBreakdown(BaseModel):
    rule_scores: dict[str, float] = Field(default_factory=dict)
    rule_explanations: dict[str, str] = Field(default_factory=dict)
    weighted_total: float = 0.0
    max_possible: float = 0.0

    @property
    def normalized_score(self) -> float:
        if self.max_possible <= 0.0:
            return 0.0
        return min(self.weighted_total / self.max_possible, 1.0)


class MatchCandidate(BaseModel):
    id: MatchCandidateId = Field(default_factory=new_candidate_id)
    source_object_id: ControlObjectId
    target_object_id: ControlObjectId
    source_plane: PlaneType
    target_plane: PlaneType
    score: MatchScore = MatchScore(0.0)
    score_breakdown: MatchScoreBreakdown = Field(default_factory=MatchScoreBreakdown)
    match_method: str = ""
    confidence: ConfidenceScore = ConfidenceScore(0.0)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    mismatches: list[ReconciliationMismatch] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateRanking(BaseModel):
    source_object_id: ControlObjectId
    ranked_candidates: list[MatchCandidate] = Field(default_factory=list)
    top_score: MatchScore = MatchScore(0.0)
    is_ambiguous: bool = False
    ambiguity_gap: float = 0.0


class DuplicateCandidateSet(BaseModel):
    source_object_id: ControlObjectId
    duplicate_target_ids: list[ControlObjectId] = Field(default_factory=list)
    scores: list[MatchScore] = Field(default_factory=list)
    description: str = ""


class CoverageGap(BaseModel):
    plane: PlaneType
    expected_object_kind: str
    expected_count: int
    actual_count: int
    missing_count: int
    description: str

    @property
    def coverage_ratio(self) -> float:
        if self.expected_count <= 0:
            return 1.0
        return self.actual_count / self.expected_count


class ExpectedPlaneCoverage(BaseModel):
    plane: PlaneType
    expected_object_kinds: list[str] = Field(default_factory=list)
    min_objects_per_kind: dict[str, int] = Field(default_factory=dict)
    require_cross_plane_links: bool = True


class CoverageExpectationResult(BaseModel):
    expectations: list[ExpectedPlaneCoverage] = Field(default_factory=list)
    gaps: list[CoverageGap] = Field(default_factory=list)
    is_fully_covered: bool = True

    @property
    def gap_count(self) -> int:
        return len(self.gaps)


class EvidenceSufficiencyResult(BaseModel):
    object_id: ControlObjectId
    is_sufficient: bool = True
    required_evidence_types: list[str] = Field(default_factory=list)
    present_evidence_types: list[str] = Field(default_factory=list)
    missing_evidence_types: list[str] = Field(default_factory=list)


class ReconciliationDecisionTrace(BaseModel):
    run_id: ReconciliationRunId
    rule_traces: list[dict[str, Any]] = Field(default_factory=list)
    candidate_count: int = 0
    mismatch_count: int = 0
    outcome_count: int = 0
    determinism_level: ReconciliationDeterminismLevel = (
        ReconciliationDeterminismLevel.FULLY_DETERMINISTIC
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReconciliationOutcome(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    outcome_type: ReconciliationOutcomeType
    source_object_id: ControlObjectId | None = None
    target_object_id: ControlObjectId | None = None
    candidate: MatchCandidate | None = None
    mismatches: list[ReconciliationMismatch] = Field(default_factory=list)
    coverage_gap: CoverageGap | None = None
    evidence_bundle: ReconciliationEvidenceBundle = Field(
        default_factory=ReconciliationEvidenceBundle
    )
    confidence: ConfidenceScore = ConfidenceScore(0.0)
    hash: ReconciliationHash = ReconciliationHash("")
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_hash(self) -> ReconciliationHash:
        data: dict[str, Any] = {
            "outcome_type": self.outcome_type.value,
            "source_object_id": str(self.source_object_id) if self.source_object_id else None,
            "target_object_id": str(self.target_object_id) if self.target_object_id else None,
            "mismatches": [m.to_hash_dict() for m in self.mismatches],
        }
        self.hash = ReconciliationHash(deterministic_hash(data))
        return self.hash


class ReconciliationCase(BaseModel):
    id: ReconciliationCaseId = Field(default_factory=new_case_id)
    run_id: ReconciliationRunId
    tenant_id: uuid.UUID
    status: ReconciliationCaseStatus = ReconciliationCaseStatus.OPEN
    priority: ReconciliationCasePriority = ReconciliationCasePriority.MEDIUM
    outcome: ReconciliationOutcome
    involved_object_ids: list[ControlObjectId] = Field(default_factory=list)
    involved_planes: list[PlaneType] = Field(default_factory=list)
    domain: str = ""
    description: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReconciliationSummary(BaseModel):
    run_id: ReconciliationRunId
    tenant_id: uuid.UUID
    total_objects_evaluated: int = 0
    total_candidates_generated: int = 0
    total_matches: int = 0
    total_mismatches: int = 0
    total_duplicates: int = 0
    total_coverage_gaps: int = 0
    total_insufficient_evidence: int = 0
    total_cases_created: int = 0
    outcome_counts: dict[str, int] = Field(default_factory=dict)
    planes_reconciled: list[PlaneType] = Field(default_factory=list)
    domains_reconciled: list[str] = Field(default_factory=list)


class ReconciliationRun(BaseModel):
    id: ReconciliationRunId = Field(default_factory=new_run_id)
    tenant_id: uuid.UUID
    scope: ReconciliationScope
    target: ReconciliationTarget
    status: ReconciliationStatus = ReconciliationStatus.PENDING
    determinism_level: ReconciliationDeterminismLevel = (
        ReconciliationDeterminismLevel.FULLY_DETERMINISTIC
    )
    outcomes: list[ReconciliationOutcome] = Field(default_factory=list)
    cases: list[ReconciliationCase] = Field(default_factory=list)
    summary: ReconciliationSummary | None = None
    decision_trace: ReconciliationDecisionTrace | None = None
    run_hash: ReconciliationHash = ReconciliationHash("")
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_run_hash(self) -> ReconciliationHash:
        data: dict[str, Any] = {
            "run_id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "scope_type": self.scope.scope_type.value,
            "planes": [p.value for p in self.scope.planes],
            "outcomes": [
                {
                    "outcome_type": o.outcome_type.value,
                    "hash": o.hash,
                    "mismatches": [m.to_hash_dict() for m in o.mismatches],
                }
                for o in self.outcomes
            ],
        }
        self.run_hash = ReconciliationHash(deterministic_hash(data))
        return self.run_hash


class ReconciliationAssemblyInput(BaseModel):
    candidates: list[MatchCandidate] = Field(default_factory=list)
    rankings: list[CandidateRanking] = Field(default_factory=list)
    duplicates: list[DuplicateCandidateSet] = Field(default_factory=list)
    coverage_result: CoverageExpectationResult | None = None
    evidence_results: list[EvidenceSufficiencyResult] = Field(default_factory=list)
    mismatches: list[ReconciliationMismatch] = Field(default_factory=list)


class ReconciliationAssemblyOutput(BaseModel):
    outcomes: list[ReconciliationOutcome] = Field(default_factory=list)
    summary: ReconciliationSummary | None = None


class ReconciliationRequest(BaseModel):
    tenant_id: uuid.UUID
    scope: ReconciliationScope
    target: ReconciliationTarget
    match_threshold: float = 0.7
    duplicate_threshold: float = 0.05
    coverage_expectations: list[ExpectedPlaneCoverage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReconciliationExecutionPlan(BaseModel):
    run_id: ReconciliationRunId
    scope: ReconciliationScope
    target: ReconciliationTarget
    planes_to_reconcile: list[PlaneType] = Field(default_factory=list)
    rule_ids_to_apply: list[ReconciliationRuleId] = Field(default_factory=list)
    match_threshold: float = 0.7
    duplicate_threshold: float = 0.05
    coverage_expectations: list[ExpectedPlaneCoverage] = Field(default_factory=list)


class ReconciliationExecutionResult(BaseModel):
    run: ReconciliationRun
    cases: list[ReconciliationCase] = Field(default_factory=list)
    summary: ReconciliationSummary
    execution_plan: ReconciliationExecutionPlan
