"""Validator service -- runs deterministic rule-based validations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class ValidationSeverity(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class ValidationStatus(str, Enum):
    passed = "passed"
    warned = "warned"
    blocked = "blocked"


@dataclass
class RuleCheckResult:
    """Result of a single rule check."""
    rule_name: str
    passed: bool
    message: str
    severity: ValidationSeverity = ValidationSeverity.info
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationOutcome:
    """Outcome of running all validation rules."""
    status: ValidationStatus
    rules_passed: int
    rules_warned: int
    rules_blocked: int
    results: list[RuleCheckResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "rules_passed": self.rules_passed,
            "rules_warned": self.rules_warned,
            "rules_blocked": self.rules_blocked,
            "results": [
                {
                    "rule_name": r.rule_name,
                    "passed": r.passed,
                    "message": r.message,
                    "severity": r.severity.value,
                }
                for r in self.results
            ],
        }


RuleFunction = Callable[[dict[str, Any]], RuleCheckResult]


class ValidatorService:
    """Runs a set of deterministic validation rules against a payload.

    Rules are registered as callables that accept a dict payload and return
    a RuleCheckResult. The validator aggregates results and determines
    the overall validation status.
    """

    def __init__(self) -> None:
        self._rules: list[RuleFunction] = []

    def register_rule(self, rule_fn: RuleFunction) -> None:
        """Register a validation rule function."""
        self._rules.append(rule_fn)

    def validate(self, payload: dict[str, Any]) -> ValidationOutcome:
        """Run all registered rules against the payload.

        Args:
            payload: Data to validate.

        Returns:
            ValidationOutcome with aggregated status.
        """
        results: list[RuleCheckResult] = []
        for rule_fn in self._rules:
            result = rule_fn(payload)
            results.append(result)

        passed = sum(1 for r in results if r.passed)
        warned = sum(
            1 for r in results
            if not r.passed and r.severity in (ValidationSeverity.warning, ValidationSeverity.info)
        )
        blocked = sum(
            1 for r in results
            if not r.passed and r.severity in (ValidationSeverity.error, ValidationSeverity.critical)
        )

        if blocked > 0:
            status = ValidationStatus.blocked
        elif warned > 0:
            status = ValidationStatus.warned
        else:
            status = ValidationStatus.passed

        return ValidationOutcome(
            status=status,
            rules_passed=passed,
            rules_warned=warned,
            rules_blocked=blocked,
            results=results,
        )


# -- Built-in rules ---------------------------------------------------------

def required_fields_rule(required: list[str]) -> RuleFunction:
    """Create a rule that checks for required fields."""
    def _check(payload: dict[str, Any]) -> RuleCheckResult:
        missing = [f for f in required if f not in payload or payload[f] is None]
        if missing:
            return RuleCheckResult(
                rule_name="required_fields",
                passed=False,
                message=f"Missing required fields: {', '.join(missing)}",
                severity=ValidationSeverity.error,
            )
        return RuleCheckResult(
            rule_name="required_fields",
            passed=True,
            message="All required fields present",
        )
    return _check


def positive_amount_rule(field_name: str) -> RuleFunction:
    """Create a rule that validates a numeric field is positive."""
    def _check(payload: dict[str, Any]) -> RuleCheckResult:
        value = payload.get(field_name)
        if value is None:
            return RuleCheckResult(
                rule_name=f"positive_{field_name}",
                passed=True,
                message=f"Field '{field_name}' not present (optional)",
            )
        if not isinstance(value, (int, float)) or value <= 0:
            return RuleCheckResult(
                rule_name=f"positive_{field_name}",
                passed=False,
                message=f"Field '{field_name}' must be a positive number, got {value}",
                severity=ValidationSeverity.error,
            )
        return RuleCheckResult(
            rule_name=f"positive_{field_name}",
            passed=True,
            message=f"Field '{field_name}' is valid ({value})",
        )
    return _check


def confidence_threshold_rule(field_name: str, threshold: float = 0.7) -> RuleFunction:
    """Create a rule that warns if a confidence score is below threshold."""
    def _check(payload: dict[str, Any]) -> RuleCheckResult:
        value = payload.get(field_name)
        if value is None:
            return RuleCheckResult(
                rule_name=f"confidence_{field_name}",
                passed=True,
                message=f"No confidence field '{field_name}'",
            )
        if value < threshold:
            return RuleCheckResult(
                rule_name=f"confidence_{field_name}",
                passed=False,
                message=f"Confidence {value:.2f} below threshold {threshold:.2f}",
                severity=ValidationSeverity.warning,
            )
        return RuleCheckResult(
            rule_name=f"confidence_{field_name}",
            passed=True,
            message=f"Confidence {value:.2f} meets threshold",
        )
    return _check
