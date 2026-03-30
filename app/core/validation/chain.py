"""Validation chain executor — runs all 10 dimensions, produces gated outcome."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.control_object import ControlObject
from app.core.errors import ValidationBypassAttempt
from app.core.graph.service import GraphService
from app.core.validation.rules import DEFAULT_VALIDATION_RULES, ValidationRule
from app.core.validation.types import (
    ChainOutcome,
    DimensionVerdict,
    ValidationChainResult,
    ValidationDimension,
    ValidationStepResult,
)


class ValidationChain:
    """Executes the full validation chain across all dimensions.

    This is mandatory before any action release.
    """

    def __init__(
        self,
        graph_service: GraphService,
        rules: list[ValidationRule] | None = None,
    ) -> None:
        self._graph = graph_service
        self._rules: list[ValidationRule] = (
            rules if rules is not None else list(DEFAULT_VALIDATION_RULES)
        )
        self._bypass_allowed = False

    def add_rule(self, rule: ValidationRule) -> None:
        self._rules.append(rule)

    def replace_rule(self, dimension: ValidationDimension, rule: ValidationRule) -> None:
        self._rules = [r for r in self._rules if r.dimension != dimension]
        self._rules.append(rule)

    def validate(
        self,
        tenant_id: uuid.UUID,
        objects: list[ControlObject],
        action_type: str = "",
        context: dict[str, Any] | None = None,
    ) -> ValidationChainResult:
        """Run all validation dimensions. Returns gated outcome."""
        if not objects:
            raise ValidationBypassAttempt(
                "Cannot validate with no objects — possible bypass attempt"
            )

        ctx = context or {}
        steps: list[ValidationStepResult] = []
        passed = 0
        failed = 0
        warnings = 0
        skipped = 0

        for rule in self._rules:
            try:
                result = rule.validate(objects, self._graph, ctx)
            except Exception as e:
                result = ValidationStepResult(
                    dimension=rule.dimension,
                    verdict=DimensionVerdict.FAIL,
                    message=f"Rule raised exception: {e}",
                )
            steps.append(result)

            if result.verdict == DimensionVerdict.PASS:
                passed += 1
            elif result.verdict == DimensionVerdict.FAIL:
                failed += 1
            elif result.verdict == DimensionVerdict.WARN:
                warnings += 1
            else:
                skipped += 1

        if failed > 0:
            outcome = ChainOutcome.FAILED
        elif warnings > 0:
            outcome = ChainOutcome.PASSED_WITH_WARNINGS
        else:
            outcome = ChainOutcome.PASSED

        chain_result = ValidationChainResult(
            tenant_id=tenant_id,
            target_object_ids=[o.id for o in objects],
            action_type=action_type,
            outcome=outcome,
            steps=steps,
            passed_count=passed,
            failed_count=failed,
            warning_count=warnings,
            skipped_count=skipped,
            validated_at=datetime.now(UTC),
        )
        chain_result.compute_hash()
        return chain_result
