"""Wave 3 validation domain types — strongly typed validation chain constructs."""

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

ValidationChainId = NewType("ValidationChainId", uuid.UUID)
ValidationRunId = NewType("ValidationRunId", uuid.UUID)
ValidationStepId = NewType("ValidationStepId", uuid.UUID)
ValidationRuleId = NewType("ValidationRuleId", str)
ValidationRuleVersion = NewType("ValidationRuleVersion", int)
ValidationReportHash = NewType("ValidationReportHash", str)


def new_chain_id() -> ValidationChainId:
    return ValidationChainId(uuid.uuid4())


def new_run_id() -> ValidationRunId:
    return ValidationRunId(uuid.uuid4())


def new_step_id() -> ValidationStepId:
    return ValidationStepId(uuid.uuid4())


class W3ValidationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed-with-warnings"
    FAILED = "failed"
    BLOCKED = "blocked"


class ValidationDecision(str, enum.Enum):
    ELIGIBLE = "eligible"
    PROPOSAL_ONLY = "proposal-only"
    APPROVAL_REQUIRED = "approval-required"
    REJECTED = "rejected"


class ValidationFailureCode(str, enum.Enum):
    SCHEMA_INVALID = "schema-invalid"
    GRAPH_INCOMPLETE = "graph-incomplete"
    EVIDENCE_INSUFFICIENT = "evidence-insufficient"
    PROVENANCE_INVALID = "provenance-invalid"
    RECONCILIATION_INCOMPLETE = "reconciliation-incomplete"
    POLICY_NONCOMPLIANT = "policy-noncompliant"
    NON_DETERMINISTIC = "non-deterministic"
    CONFIDENCE_BELOW_THRESHOLD = "confidence-below-threshold"
    CONTRADICTORY_EVIDENCE = "contradictory-evidence"
    ACTION_PRECONDITION_FAILED = "action-precondition-failed"
    UNSUPPORTED_TARGET = "unsupported-target"
    MISSING_ORIGIN = "missing-origin"
    MISSING_VALIDATION_INPUT = "missing-validation-input"


class ValidationSeverity(str, enum.Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationEvidenceRequirement(BaseModel):
    evidence_type: str
    required: bool = True
    description: str = ""


class ValidationArtifactRef(BaseModel):
    artifact_type: str
    artifact_id: str
    source_module: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationFailure(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    code: ValidationFailureCode
    severity: ValidationSeverity = ValidationSeverity.ERROR
    rule_id: ValidationRuleId | None = None
    object_id: ControlObjectId | None = None
    description: str
    expected: Any = None
    actual: Any = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationWarning(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    rule_id: ValidationRuleId | None = None
    object_id: ControlObjectId | None = None
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    rule_id: ValidationRuleId
    step_id: ValidationStepId = Field(default_factory=new_step_id)
    status: W3ValidationStatus = W3ValidationStatus.PENDING
    passed: bool = False
    failures: list[ValidationFailure] = Field(default_factory=list)
    warnings: list[ValidationWarning] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    explanation: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationStep(BaseModel):
    id: ValidationStepId = Field(default_factory=new_step_id)
    order: int = 0
    rule_id: ValidationRuleId
    result: ValidationResult | None = None
    executed: bool = False


class ValidationScope(BaseModel):
    tenant_id: uuid.UUID
    planes: list[PlaneType] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    action_type: str = ""


class ValidationTarget(BaseModel):
    object_ids: list[ControlObjectId] = Field(default_factory=list)
    reconciliation_run_id: uuid.UUID | None = None
    reconciliation_case_ids: list[uuid.UUID] = Field(default_factory=list)
    action_proposal_id: uuid.UUID | None = None
    graph_slice_root_ids: list[ControlObjectId] = Field(default_factory=list)


class ValidationContext(BaseModel):
    scope: ValidationScope
    target: ValidationTarget
    require_reconciled: bool = False
    min_confidence: float = 0.5
    required_evidence_types: list[str] = Field(default_factory=list)
    required_states: list[str] = Field(default_factory=list)
    policy_overrides: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationPrecondition(BaseModel):
    name: str
    met: bool = False
    description: str = ""
    blocking: bool = True


class ValidationEligibility(BaseModel):
    decision: ValidationDecision = ValidationDecision.REJECTED
    eligible_for_release: bool = False
    requires_approval: bool = False
    proposal_only: bool = False
    blocking_failures: list[ValidationFailure] = Field(default_factory=list)
    explanation: str = ""


class ContradictionCheckResult(BaseModel):
    has_contradictions: bool = False
    contradiction_count: int = 0
    contradicting_object_ids: list[ControlObjectId] = Field(default_factory=list)
    contradicting_link_ids: list[ControlLinkId] = Field(default_factory=list)


class ProvenanceIntegrityResult(BaseModel):
    is_valid: bool = True
    invalid_object_ids: list[ControlObjectId] = Field(default_factory=list)
    missing_creator_ids: list[ControlObjectId] = Field(default_factory=list)
    description: str = ""


class GraphCompletenessResult(BaseModel):
    is_complete: bool = True
    orphaned_object_ids: list[ControlObjectId] = Field(default_factory=list)
    missing_link_count: int = 0
    description: str = ""


class EvidenceSufficiencyValidationResult(BaseModel):
    is_sufficient: bool = True
    object_id: ControlObjectId | None = None
    present_count: int = 0
    required_count: int = 0
    missing_types: list[str] = Field(default_factory=list)


class DeterministicReproducibilityResult(BaseModel):
    is_reproducible: bool = True
    non_deterministic_object_ids: list[ControlObjectId] = Field(default_factory=list)
    description: str = ""


class ValidationDecisionTrace(BaseModel):
    run_id: ValidationRunId
    chain_id: ValidationChainId
    steps_executed: int = 0
    failures_total: int = 0
    warnings_total: int = 0
    decision: ValidationDecision = ValidationDecision.REJECTED
    rule_traces: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ValidationReport(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    run_id: ValidationRunId
    chain_id: ValidationChainId
    tenant_id: uuid.UUID
    status: W3ValidationStatus = W3ValidationStatus.PENDING
    decision: ValidationDecision = ValidationDecision.REJECTED
    eligibility: ValidationEligibility = Field(default_factory=ValidationEligibility)
    steps: list[ValidationStep] = Field(default_factory=list)
    failures: list[ValidationFailure] = Field(default_factory=list)
    warnings: list[ValidationWarning] = Field(default_factory=list)
    preconditions: list[ValidationPrecondition] = Field(default_factory=list)
    target: ValidationTarget = Field(default_factory=ValidationTarget)
    scope: ValidationScope | None = None
    decision_trace: ValidationDecisionTrace | None = None
    report_hash: ValidationReportHash = ValidationReportHash("")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_hash(self) -> ValidationReportHash:
        data: dict[str, Any] = {
            "run_id": str(self.run_id),
            "chain_id": str(self.chain_id),
            "status": self.status.value,
            "decision": self.decision.value,
            "failures": [
                {"code": f.code.value, "description": f.description} for f in self.failures
            ],
            "steps": [
                {
                    "rule_id": s.rule_id,
                    "passed": s.result.passed if s.result else False,
                }
                for s in self.steps
            ],
        }
        self.report_hash = ValidationReportHash(deterministic_hash(data))
        return self.report_hash

    @property
    def is_actionable(self) -> bool:
        return self.decision in (
            ValidationDecision.ELIGIBLE,
            ValidationDecision.APPROVAL_REQUIRED,
            ValidationDecision.PROPOSAL_ONLY,
        )

    @property
    def passed(self) -> bool:
        return self.status in (
            W3ValidationStatus.PASSED,
            W3ValidationStatus.PASSED_WITH_WARNINGS,
        )


class ValidationRun(BaseModel):
    id: ValidationRunId = Field(default_factory=new_run_id)
    chain_id: ValidationChainId
    tenant_id: uuid.UUID
    context: ValidationContext
    report: ValidationReport | None = None
    status: W3ValidationStatus = W3ValidationStatus.PENDING
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class ValidationChainDef(BaseModel):
    id: ValidationChainId = Field(default_factory=new_chain_id)
    name: str
    description: str = ""
    rule_ids: list[ValidationRuleId] = Field(default_factory=list)
    version: int = 1


class ValidationExecutionRequest(BaseModel):
    tenant_id: uuid.UUID
    context: ValidationContext
    chain_id: ValidationChainId | None = None


class ValidationExecutionResult(BaseModel):
    run: ValidationRun
    report: ValidationReport
    decision: ValidationDecision


class ValidationDecisionPolicy(BaseModel):
    allow_warnings: bool = True
    max_warnings: int = 10
    require_all_steps: bool = True
    auto_eligible_on_pass: bool = True
    proposal_only_on_warnings: bool = False


class ValidationThresholdPolicy(BaseModel):
    min_confidence: float = 0.5
    min_evidence_count: int = 1
    required_evidence_types: list[str] = Field(default_factory=list)


class ValidationEvidencePolicy(BaseModel):
    required_types: list[str] = Field(default_factory=list)
    min_per_object: int = 0
    require_provenance: bool = True


class ValidationAssemblyInput(BaseModel):
    step_results: list[ValidationResult] = Field(default_factory=list)
    preconditions: list[ValidationPrecondition] = Field(default_factory=list)


class ValidationAssemblyOutput(BaseModel):
    report: ValidationReport | None = None
    decision: ValidationDecision = ValidationDecision.REJECTED
