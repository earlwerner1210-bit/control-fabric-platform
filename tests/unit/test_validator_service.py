"""Tests for the validator service."""

from __future__ import annotations

import pytest

from services.validator_service.validator import (
    ValidatorService,
    ValidationStatus,
    ValidationSeverity,
    RuleCheckResult,
    required_fields_rule,
    positive_amount_rule,
    confidence_threshold_rule,
)


@pytest.fixture
def validator() -> ValidatorService:
    return ValidatorService()


class TestValidatorService:
    """Tests for the ValidatorService."""

    def test_all_rules_pass(self, validator: ValidatorService):
        """All passing rules should produce 'passed' status."""
        validator.register_rule(required_fields_rule(["name", "amount"]))
        validator.register_rule(positive_amount_rule("amount"))

        result = validator.validate({"name": "Test", "amount": 100.0})
        assert result.status == ValidationStatus.passed
        assert result.rules_passed == 2
        assert result.rules_warned == 0
        assert result.rules_blocked == 0

    def test_warning_status(self, validator: ValidatorService):
        """Low confidence should produce 'warned' status."""
        validator.register_rule(required_fields_rule(["name"]))
        validator.register_rule(confidence_threshold_rule("confidence", threshold=0.8))

        result = validator.validate({"name": "Test", "confidence": 0.5})
        assert result.status == ValidationStatus.warned
        assert result.rules_passed == 1
        assert result.rules_warned == 1

    def test_blocked_status(self, validator: ValidatorService):
        """Missing required fields should produce 'blocked' status."""
        validator.register_rule(required_fields_rule(["name", "amount"]))

        result = validator.validate({"name": "Test"})
        assert result.status == ValidationStatus.blocked
        assert result.rules_blocked == 1

    def test_blocked_takes_precedence_over_warned(self, validator: ValidatorService):
        """Blocked status should take precedence over warned."""
        validator.register_rule(required_fields_rule(["name", "missing_field"]))
        validator.register_rule(confidence_threshold_rule("confidence", threshold=0.8))

        result = validator.validate({"name": "Test", "confidence": 0.5})
        assert result.status == ValidationStatus.blocked

    def test_positive_amount_rule_negative(self, validator: ValidatorService):
        """Negative amount should block."""
        validator.register_rule(positive_amount_rule("amount"))

        result = validator.validate({"amount": -10.0})
        assert result.status == ValidationStatus.blocked
        assert result.rules_blocked == 1

    def test_positive_amount_rule_zero(self, validator: ValidatorService):
        """Zero amount should block."""
        validator.register_rule(positive_amount_rule("amount"))

        result = validator.validate({"amount": 0})
        assert result.status == ValidationStatus.blocked

    def test_positive_amount_rule_missing_optional(self, validator: ValidatorService):
        """Missing optional field should pass."""
        validator.register_rule(positive_amount_rule("optional_field"))

        result = validator.validate({"other": "data"})
        assert result.status == ValidationStatus.passed

    def test_empty_validator(self, validator: ValidatorService):
        """Validator with no rules should pass."""
        result = validator.validate({"any": "data"})
        assert result.status == ValidationStatus.passed
        assert result.rules_passed == 0

    def test_to_dict(self, validator: ValidatorService):
        """to_dict should return a serializable dict."""
        validator.register_rule(required_fields_rule(["name"]))
        result = validator.validate({"name": "Test"})
        d = result.to_dict()
        assert d["status"] == "passed"
        assert isinstance(d["results"], list)
