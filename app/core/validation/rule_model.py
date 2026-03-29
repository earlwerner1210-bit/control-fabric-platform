"""Wave 3 validation rule model — typed, ordered, inspectable validation rules."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.core.control_object import ControlObject
from app.core.graph.service import GraphService
from app.core.types import ControlLinkType, ControlObjectType, ControlState, PlaneType
from app.core.validation.domain_types import (
    ContradictionCheckResult,
    DeterministicReproducibilityResult,
    EvidenceSufficiencyValidationResult,
    GraphCompletenessResult,
    ProvenanceIntegrityResult,
    ValidationFailure,
    ValidationFailureCode,
    ValidationResult,
    ValidationRuleId,
    ValidationRuleVersion,
    ValidationSeverity,
    ValidationWarning,
    W3ValidationStatus,
)


class ValidationRuleCategory(str, enum.Enum):
    SCHEMA_VALIDITY = "schema-validity"
    GRAPH_COMPLETENESS = "graph-completeness"
    EVIDENCE_SUFFICIENCY = "evidence-sufficiency"
    PROVENANCE_INTEGRITY = "provenance-integrity"
    RECONCILIATION_STATE = "reconciliation-state"
    POLICY_COMPLIANCE = "policy-compliance"
    DETERMINISTIC_REPRODUCIBILITY = "deterministic-reproducibility"
    CONTRADICTION_CHECK = "contradiction-check"
    CONFIDENCE_THRESHOLD = "confidence-threshold"
    ACTION_PRECONDITION = "action-precondition"


class ValidationRuleApplicability(BaseModel):
    applicable_planes: list[PlaneType] = Field(default_factory=list)
    applicable_object_types: list[ControlObjectType] = Field(default_factory=list)
    applicable_object_kinds: list[str] = Field(default_factory=list)
    applicable_action_types: list[str] = Field(default_factory=list)

    def is_applicable(self, objects: list[ControlObject], action_type: str = "") -> bool:
        if self.applicable_action_types and action_type not in self.applicable_action_types:
            return False
        if self.applicable_planes:
            if not any(o.plane in self.applicable_planes for o in objects):
                return False
        if self.applicable_object_types:
            if not any(o.object_type in self.applicable_object_types for o in objects):
                return False
        return True


class ValidationRuleExplanation(BaseModel):
    rule_id: ValidationRuleId
    description: str
    passed: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationRuleTraceEntry(BaseModel):
    rule_id: ValidationRuleId
    rule_version: ValidationRuleVersion = ValidationRuleVersion(1)
    category: ValidationRuleCategory
    applied: bool = True
    passed: bool = False
    failure_count: int = 0
    warning_count: int = 0
    explanation: ValidationRuleExplanation | None = None


class ValidationRuleWeight(BaseModel):
    rule_id: ValidationRuleId
    is_hard_fail: bool = True
    is_blocking: bool = True


class ValidationChainDefinition(BaseModel):
    name: str
    ordered_rule_ids: list[ValidationRuleId] = Field(default_factory=list)
    version: int = 1
    description: str = ""


class ValidationChainExecutionPlan(BaseModel):
    chain_definition: ValidationChainDefinition
    applicable_rule_ids: list[ValidationRuleId] = Field(default_factory=list)
    skipped_rule_ids: list[ValidationRuleId] = Field(default_factory=list)


class W3ValidationRule(ABC):
    """Base class for Wave 3 validation rules."""

    rule_id: ValidationRuleId
    rule_version: ValidationRuleVersion = ValidationRuleVersion(1)
    category: ValidationRuleCategory
    weight: ValidationRuleWeight
    applicability: ValidationRuleApplicability

    @abstractmethod
    def validate(
        self,
        objects: list[ControlObject],
        graph_service: GraphService,
        context: dict[str, Any],
    ) -> ValidationResult: ...

    def is_applicable(self, objects: list[ControlObject], action_type: str = "") -> bool:
        return self.applicability.is_applicable(objects, action_type)


class W3SchemaValidityRule(W3ValidationRule):
    rule_id = ValidationRuleId("w3-schema-validity")
    category = ValidationRuleCategory.SCHEMA_VALIDITY
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("w3-schema-validity"), is_hard_fail=True
    )
    applicability = ValidationRuleApplicability()

    def validate(self, objects, graph_service, context):
        failures: list[ValidationFailure] = []
        for obj in objects:
            if not obj.label.strip():
                failures.append(
                    ValidationFailure(
                        code=ValidationFailureCode.SCHEMA_INVALID,
                        object_id=obj.id,
                        description=f"Object {obj.id} has empty label",
                        rule_id=self.rule_id,
                    )
                )
            if not obj.domain.strip():
                failures.append(
                    ValidationFailure(
                        code=ValidationFailureCode.SCHEMA_INVALID,
                        object_id=obj.id,
                        description=f"Object {obj.id} has empty domain",
                        rule_id=self.rule_id,
                    )
                )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.FAILED if failures else W3ValidationStatus.PASSED,
            passed=len(failures) == 0,
            failures=failures,
            explanation="Schema validation" + (" failed" if failures else " passed"),
        )


class W3GraphCompletenessRule(W3ValidationRule):
    rule_id = ValidationRuleId("w3-graph-completeness")
    category = ValidationRuleCategory.GRAPH_COMPLETENESS
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("w3-graph-completeness"), is_hard_fail=False, is_blocking=False
    )
    applicability = ValidationRuleApplicability()

    def validate(self, objects, graph_service, context):
        warnings: list[ValidationWarning] = []
        failures: list[ValidationFailure] = []
        for obj in objects:
            links = graph_service.get_links_for_object(obj.id)
            if not links:
                if context.get("require_graph_links", False):
                    failures.append(
                        ValidationFailure(
                            code=ValidationFailureCode.GRAPH_INCOMPLETE,
                            object_id=obj.id,
                            description=f"Object '{obj.label}' has no graph links",
                            rule_id=self.rule_id,
                        )
                    )
                else:
                    warnings.append(
                        ValidationWarning(
                            rule_id=self.rule_id,
                            object_id=obj.id,
                            description=f"Object '{obj.label}' has no graph links",
                        )
                    )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.FAILED
            if failures
            else (
                W3ValidationStatus.PASSED_WITH_WARNINGS
                if warnings
                else W3ValidationStatus.PASSED
            ),
            passed=len(failures) == 0,
            failures=failures,
            warnings=warnings,
            explanation="Graph completeness check",
        )


class W3EvidenceSufficiencyRule(W3ValidationRule):
    rule_id = ValidationRuleId("w3-evidence-sufficiency")
    category = ValidationRuleCategory.EVIDENCE_SUFFICIENCY
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("w3-evidence-sufficiency"), is_hard_fail=True
    )
    applicability = ValidationRuleApplicability()

    def validate(self, objects, graph_service, context):
        min_evidence = context.get("min_evidence", 1)
        required_types = context.get("required_evidence_types", [])
        failures: list[ValidationFailure] = []
        for obj in objects:
            if len(obj.evidence) < min_evidence:
                failures.append(
                    ValidationFailure(
                        code=ValidationFailureCode.EVIDENCE_INSUFFICIENT,
                        object_id=obj.id,
                        description=(
                            f"Object '{obj.label}' has {len(obj.evidence)} evidence, "
                            f"requires {min_evidence}"
                        ),
                        expected=min_evidence,
                        actual=len(obj.evidence),
                        rule_id=self.rule_id,
                    )
                )
            if required_types:
                present = {e.evidence_type for e in obj.evidence}
                missing = [t for t in required_types if t not in present]
                if missing:
                    failures.append(
                        ValidationFailure(
                            code=ValidationFailureCode.EVIDENCE_INSUFFICIENT,
                            object_id=obj.id,
                            description=f"Object '{obj.label}' missing evidence types: {missing}",
                            rule_id=self.rule_id,
                            metadata={"missing_types": missing},
                        )
                    )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.FAILED if failures else W3ValidationStatus.PASSED,
            passed=len(failures) == 0,
            failures=failures,
            explanation="Evidence sufficiency check",
        )


class W3ProvenanceIntegrityRule(W3ValidationRule):
    rule_id = ValidationRuleId("w3-provenance-integrity")
    category = ValidationRuleCategory.PROVENANCE_INTEGRITY
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("w3-provenance-integrity"), is_hard_fail=True
    )
    applicability = ValidationRuleApplicability()

    def validate(self, objects, graph_service, context):
        failures: list[ValidationFailure] = []
        for obj in objects:
            if not obj.provenance.created_by:
                failures.append(
                    ValidationFailure(
                        code=ValidationFailureCode.PROVENANCE_INVALID,
                        object_id=obj.id,
                        description=f"Object '{obj.label}' has no provenance creator",
                        rule_id=self.rule_id,
                    )
                )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.FAILED if failures else W3ValidationStatus.PASSED,
            passed=len(failures) == 0,
            failures=failures,
            explanation="Provenance integrity check",
        )


class W3ReconciliationStateRule(W3ValidationRule):
    rule_id = ValidationRuleId("w3-reconciliation-state")
    category = ValidationRuleCategory.RECONCILIATION_STATE
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("w3-reconciliation-state"), is_hard_fail=True
    )
    applicability = ValidationRuleApplicability()

    def validate(self, objects, graph_service, context):
        require_reconciled = context.get("require_reconciled", False)
        failures: list[ValidationFailure] = []
        for obj in objects:
            if obj.state == ControlState.DISPUTED:
                failures.append(
                    ValidationFailure(
                        code=ValidationFailureCode.RECONCILIATION_INCOMPLETE,
                        object_id=obj.id,
                        description=f"Object '{obj.label}' is disputed",
                        rule_id=self.rule_id,
                    )
                )
            elif require_reconciled and obj.state not in (
                ControlState.RECONCILED,
                ControlState.ACTIONED,
            ):
                failures.append(
                    ValidationFailure(
                        code=ValidationFailureCode.RECONCILIATION_INCOMPLETE,
                        object_id=obj.id,
                        description=(
                            f"Object '{obj.label}' is {obj.state.value}, "
                            f"expected reconciled or actioned"
                        ),
                        rule_id=self.rule_id,
                    )
                )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.FAILED if failures else W3ValidationStatus.PASSED,
            passed=len(failures) == 0,
            failures=failures,
            explanation="Reconciliation state check",
        )


class W3PolicyComplianceRule(W3ValidationRule):
    rule_id = ValidationRuleId("w3-policy-compliance")
    category = ValidationRuleCategory.POLICY_COMPLIANCE
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("w3-policy-compliance"), is_hard_fail=True
    )
    applicability = ValidationRuleApplicability()

    def __init__(
        self, policy_checks: list[tuple[str, Any]] | None = None
    ) -> None:
        self._policy_checks = policy_checks or []

    def validate(self, objects, graph_service, context):
        failures: list[ValidationFailure] = []
        for check_name, check_fn in self._policy_checks:
            for obj in objects:
                if not check_fn(obj, context):
                    failures.append(
                        ValidationFailure(
                            code=ValidationFailureCode.POLICY_NONCOMPLIANT,
                            object_id=obj.id,
                            description=f"Policy '{check_name}' failed for '{obj.label}'",
                            rule_id=self.rule_id,
                        )
                    )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.FAILED if failures else W3ValidationStatus.PASSED,
            passed=len(failures) == 0,
            failures=failures,
            explanation="Policy compliance check",
        )


class W3DeterministicReproducibilityRule(W3ValidationRule):
    rule_id = ValidationRuleId("w3-deterministic-reproducibility")
    category = ValidationRuleCategory.DETERMINISTIC_REPRODUCIBILITY
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("w3-deterministic-reproducibility"),
        is_hard_fail=False,
        is_blocking=False,
    )
    applicability = ValidationRuleApplicability()

    def validate(self, objects, graph_service, context):
        warnings: list[ValidationWarning] = []
        for obj in objects:
            if str(obj.provenance.creation_method) == "model_assisted" and not obj.provenance.model_id:
                warnings.append(
                    ValidationWarning(
                        rule_id=self.rule_id,
                        object_id=obj.id,
                        description=(
                            f"Object '{obj.label}' is model-assisted but has no model_id"
                        ),
                    )
                )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.PASSED_WITH_WARNINGS
            if warnings
            else W3ValidationStatus.PASSED,
            passed=True,
            warnings=warnings,
            explanation="Deterministic reproducibility check",
        )


class W3ContradictionCheckRule(W3ValidationRule):
    rule_id = ValidationRuleId("w3-contradiction-check")
    category = ValidationRuleCategory.CONTRADICTION_CHECK
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("w3-contradiction-check"), is_hard_fail=True
    )
    applicability = ValidationRuleApplicability()

    def validate(self, objects, graph_service, context):
        failures: list[ValidationFailure] = []
        for obj in objects:
            links = graph_service.get_links_for_object(
                obj.id, link_type=ControlLinkType.CONTRADICTS
            )
            if links:
                failures.append(
                    ValidationFailure(
                        code=ValidationFailureCode.CONTRADICTORY_EVIDENCE,
                        object_id=obj.id,
                        description=f"Object '{obj.label}' has {len(links)} contradictory links",
                        rule_id=self.rule_id,
                        metadata={"contradiction_count": len(links)},
                    )
                )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.FAILED if failures else W3ValidationStatus.PASSED,
            passed=len(failures) == 0,
            failures=failures,
            explanation="Contradiction check",
        )


class W3ConfidenceThresholdRule(W3ValidationRule):
    rule_id = ValidationRuleId("w3-confidence-threshold")
    category = ValidationRuleCategory.CONFIDENCE_THRESHOLD
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("w3-confidence-threshold"), is_hard_fail=True
    )
    applicability = ValidationRuleApplicability()

    def validate(self, objects, graph_service, context):
        min_confidence = context.get("min_confidence", 0.5)
        failures: list[ValidationFailure] = []
        for obj in objects:
            if float(obj.confidence) < min_confidence:
                failures.append(
                    ValidationFailure(
                        code=ValidationFailureCode.CONFIDENCE_BELOW_THRESHOLD,
                        object_id=obj.id,
                        description=(
                            f"Object '{obj.label}' confidence {obj.confidence} "
                            f"below threshold {min_confidence}"
                        ),
                        expected=min_confidence,
                        actual=float(obj.confidence),
                        rule_id=self.rule_id,
                    )
                )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.FAILED if failures else W3ValidationStatus.PASSED,
            passed=len(failures) == 0,
            failures=failures,
            explanation="Confidence threshold check",
        )


class W3ActionPreconditionRule(W3ValidationRule):
    rule_id = ValidationRuleId("w3-action-precondition")
    category = ValidationRuleCategory.ACTION_PRECONDITION
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("w3-action-precondition"), is_hard_fail=False, is_blocking=False
    )
    applicability = ValidationRuleApplicability()

    def validate(self, objects, graph_service, context):
        required_states = context.get(
            "required_states",
            [ControlState.FROZEN.value, ControlState.RECONCILED.value],
        )
        failures: list[ValidationFailure] = []
        warnings: list[ValidationWarning] = []
        for obj in objects:
            if obj.state.value not in required_states:
                if context.get("strict_preconditions", False):
                    failures.append(
                        ValidationFailure(
                            code=ValidationFailureCode.ACTION_PRECONDITION_FAILED,
                            object_id=obj.id,
                            description=(
                                f"Object '{obj.label}' is {obj.state.value}, "
                                f"expected one of {required_states}"
                            ),
                            rule_id=self.rule_id,
                        )
                    )
                else:
                    warnings.append(
                        ValidationWarning(
                            rule_id=self.rule_id,
                            object_id=obj.id,
                            description=(
                                f"Object '{obj.label}' is {obj.state.value}, "
                                f"expected one of {required_states}"
                            ),
                        )
                    )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.FAILED
            if failures
            else (
                W3ValidationStatus.PASSED_WITH_WARNINGS
                if warnings
                else W3ValidationStatus.PASSED
            ),
            passed=len(failures) == 0,
            failures=failures,
            warnings=warnings,
            explanation="Action precondition check",
        )


DEFAULT_W3_VALIDATION_RULES: list[W3ValidationRule] = [
    W3SchemaValidityRule(),
    W3GraphCompletenessRule(),
    W3EvidenceSufficiencyRule(),
    W3ProvenanceIntegrityRule(),
    W3ReconciliationStateRule(),
    W3PolicyComplianceRule(),
    W3DeterministicReproducibilityRule(),
    W3ContradictionCheckRule(),
    W3ConfidenceThresholdRule(),
    W3ActionPreconditionRule(),
]


class ValidationRuleRegistry:
    """Registry for Wave 3 validation rules, extensible by domain packs."""

    def __init__(self) -> None:
        self._rules: dict[ValidationRuleId, W3ValidationRule] = {}
        self._order: list[ValidationRuleId] = []

    def register_rule(self, rule: W3ValidationRule, order: int | None = None) -> None:
        self._rules[rule.rule_id] = rule
        if rule.rule_id not in self._order:
            if order is not None:
                self._order.insert(order, rule.rule_id)
            else:
                self._order.append(rule.rule_id)

    def get_rule(self, rule_id: ValidationRuleId) -> W3ValidationRule | None:
        return self._rules.get(rule_id)

    def get_ordered_rules(self) -> list[W3ValidationRule]:
        return [self._rules[rid] for rid in self._order if rid in self._rules]

    def get_applicable_rules(
        self, objects: list[ControlObject], action_type: str = ""
    ) -> list[W3ValidationRule]:
        return [
            self._rules[rid]
            for rid in self._order
            if rid in self._rules and self._rules[rid].is_applicable(objects, action_type)
        ]

    @property
    def rule_count(self) -> int:
        return len(self._rules)


def build_default_validation_rule_registry() -> ValidationRuleRegistry:
    registry = ValidationRuleRegistry()
    for rule in DEFAULT_W3_VALIDATION_RULES:
        registry.register_rule(rule)
    return registry
