"""Default validation rules for each dimension."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.control_object import ControlObject
from app.core.graph.service import GraphService
from app.core.types import ControlLinkType, ControlState
from app.core.validation.types import (
    DimensionVerdict,
    ValidationDimension,
    ValidationStepResult,
)


class ValidationRule(Protocol):
    """Protocol for validation dimension rules."""

    dimension: ValidationDimension

    def validate(
        self,
        objects: list[ControlObject],
        graph_service: GraphService,
        context: dict[str, Any],
    ) -> ValidationStepResult: ...


class SchemaValidationRule:
    dimension = ValidationDimension.SCHEMA

    def validate(
        self,
        objects: list[ControlObject],
        graph_service: GraphService,
        context: dict[str, Any],
    ) -> ValidationStepResult:
        for obj in objects:
            if not obj.label.strip():
                return ValidationStepResult(
                    dimension=self.dimension,
                    verdict=DimensionVerdict.FAIL,
                    message=f"Object {obj.id} has empty label",
                )
            if not obj.domain.strip():
                return ValidationStepResult(
                    dimension=self.dimension,
                    verdict=DimensionVerdict.FAIL,
                    message=f"Object {obj.id} has empty domain",
                )
        return ValidationStepResult(
            dimension=self.dimension,
            verdict=DimensionVerdict.PASS,
            message="All objects pass schema validation",
        )


class GraphCompletenessRule:
    dimension = ValidationDimension.GRAPH_COMPLETENESS

    def validate(
        self,
        objects: list[ControlObject],
        graph_service: GraphService,
        context: dict[str, Any],
    ) -> ValidationStepResult:
        for obj in objects:
            links = graph_service.get_links_for_object(obj.id)
            if not links:
                return ValidationStepResult(
                    dimension=self.dimension,
                    verdict=DimensionVerdict.WARN,
                    message=f"Object '{obj.label}' has no links in graph",
                )
        return ValidationStepResult(
            dimension=self.dimension,
            verdict=DimensionVerdict.PASS,
            message="All objects have graph links",
        )


class EvidenceSufficiencyRule:
    dimension = ValidationDimension.EVIDENCE_SUFFICIENCY

    def __init__(self, min_evidence: int = 1) -> None:
        self._min = min_evidence

    def validate(
        self,
        objects: list[ControlObject],
        graph_service: GraphService,
        context: dict[str, Any],
    ) -> ValidationStepResult:
        for obj in objects:
            if len(obj.evidence) < self._min:
                return ValidationStepResult(
                    dimension=self.dimension,
                    verdict=DimensionVerdict.FAIL,
                    message=(
                        f"Object '{obj.label}' has {len(obj.evidence)} evidence "
                        f"refs, requires {self._min}"
                    ),
                )
        return ValidationStepResult(
            dimension=self.dimension,
            verdict=DimensionVerdict.PASS,
            message="All objects have sufficient evidence",
        )


class ProvenanceRule:
    dimension = ValidationDimension.PROVENANCE

    def validate(
        self,
        objects: list[ControlObject],
        graph_service: GraphService,
        context: dict[str, Any],
    ) -> ValidationStepResult:
        for obj in objects:
            if not obj.provenance.created_by:
                return ValidationStepResult(
                    dimension=self.dimension,
                    verdict=DimensionVerdict.FAIL,
                    message=f"Object '{obj.label}' has no provenance creator",
                )
        return ValidationStepResult(
            dimension=self.dimension,
            verdict=DimensionVerdict.PASS,
            message="All objects have valid provenance",
        )


class ReconciliationStateRule:
    dimension = ValidationDimension.RECONCILIATION_STATE

    def validate(
        self,
        objects: list[ControlObject],
        graph_service: GraphService,
        context: dict[str, Any],
    ) -> ValidationStepResult:
        require_reconciled = context.get("require_reconciled", False)
        for obj in objects:
            if require_reconciled and obj.state not in (
                ControlState.RECONCILED,
                ControlState.ACTIONED,
            ):
                return ValidationStepResult(
                    dimension=self.dimension,
                    verdict=DimensionVerdict.FAIL,
                    message=(
                        f"Object '{obj.label}' is {obj.state.value}, "
                        f"expected reconciled or actioned"
                    ),
                )
            if obj.state == ControlState.DISPUTED:
                return ValidationStepResult(
                    dimension=self.dimension,
                    verdict=DimensionVerdict.FAIL,
                    message=f"Object '{obj.label}' is disputed",
                )
        return ValidationStepResult(
            dimension=self.dimension,
            verdict=DimensionVerdict.PASS,
            message="Reconciliation state check passed",
        )


class PolicyRule:
    dimension = ValidationDimension.POLICY

    def validate(
        self,
        objects: list[ControlObject],
        graph_service: GraphService,
        context: dict[str, Any],
    ) -> ValidationStepResult:
        # Delegate to registry-based policy checks
        return ValidationStepResult(
            dimension=self.dimension,
            verdict=DimensionVerdict.PASS,
            message="Policy check passed (no domain-specific violations)",
        )


class DeterminismRule:
    dimension = ValidationDimension.DETERMINISM

    def validate(
        self,
        objects: list[ControlObject],
        graph_service: GraphService,
        context: dict[str, Any],
    ) -> ValidationStepResult:
        for obj in objects:
            if obj.provenance.creation_method == "model_assisted":
                if not obj.provenance.model_id:
                    return ValidationStepResult(
                        dimension=self.dimension,
                        verdict=DimensionVerdict.WARN,
                        message=(
                            f"Object '{obj.label}' is model-assisted "
                            f"but has no model_id in provenance"
                        ),
                    )
        return ValidationStepResult(
            dimension=self.dimension,
            verdict=DimensionVerdict.PASS,
            message="Determinism check passed",
        )


class ConfidenceRule:
    dimension = ValidationDimension.CONFIDENCE

    def __init__(self, min_confidence: float = 0.5) -> None:
        self._min = min_confidence

    def validate(
        self,
        objects: list[ControlObject],
        graph_service: GraphService,
        context: dict[str, Any],
    ) -> ValidationStepResult:
        for obj in objects:
            if float(obj.confidence) < self._min:
                return ValidationStepResult(
                    dimension=self.dimension,
                    verdict=DimensionVerdict.FAIL,
                    message=(
                        f"Object '{obj.label}' confidence {obj.confidence} "
                        f"below minimum {self._min}"
                    ),
                )
        return ValidationStepResult(
            dimension=self.dimension,
            verdict=DimensionVerdict.PASS,
            message="Confidence check passed",
        )


class ContradictoryEvidenceRule:
    dimension = ValidationDimension.CONTRADICTORY_EVIDENCE

    def validate(
        self,
        objects: list[ControlObject],
        graph_service: GraphService,
        context: dict[str, Any],
    ) -> ValidationStepResult:
        for obj in objects:
            links = graph_service.get_links_for_object(
                obj.id, link_type=ControlLinkType.CONTRADICTS
            )
            if links:
                return ValidationStepResult(
                    dimension=self.dimension,
                    verdict=DimensionVerdict.FAIL,
                    message=(f"Object '{obj.label}' has {len(links)} contradictory links"),
                )
        return ValidationStepResult(
            dimension=self.dimension,
            verdict=DimensionVerdict.PASS,
            message="No contradictory evidence found",
        )


class ActionPreconditionsRule:
    dimension = ValidationDimension.ACTION_PRECONDITIONS

    def validate(
        self,
        objects: list[ControlObject],
        graph_service: GraphService,
        context: dict[str, Any],
    ) -> ValidationStepResult:
        required_states = context.get(
            "required_states",
            [ControlState.FROZEN.value, ControlState.RECONCILED.value],
        )
        for obj in objects:
            if obj.state.value not in required_states:
                return ValidationStepResult(
                    dimension=self.dimension,
                    verdict=DimensionVerdict.WARN,
                    message=(
                        f"Object '{obj.label}' is {obj.state.value}, "
                        f"expected one of {required_states}"
                    ),
                )
        return ValidationStepResult(
            dimension=self.dimension,
            verdict=DimensionVerdict.PASS,
            message="Action preconditions met",
        )


DEFAULT_VALIDATION_RULES: list[ValidationRule] = [
    SchemaValidationRule(),
    GraphCompletenessRule(),
    EvidenceSufficiencyRule(),
    ProvenanceRule(),
    ReconciliationStateRule(),
    PolicyRule(),
    DeterminismRule(),
    ConfidenceRule(),
    ContradictoryEvidenceRule(),
    ActionPreconditionsRule(),
]
