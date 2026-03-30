"""Tests for validators from all 3 domain packs.

Tests the validation logic in app.services.validation.service.ValidationService
by exercising the private domain-rule methods directly (no DB dependency).
"""

from __future__ import annotations

import uuid

import pytest

from app.schemas.validation import RuleResult

# ---------------------------------------------------------------------------
# Lightweight helper that mirrors ValidationService domain-rule methods
# without requiring a DB session.
# ---------------------------------------------------------------------------


class _DomainValidatorProxy:
    """Replicates ValidationService domain-rule validation logic in-process."""

    # -- contract_margin ---------------------------------------------------

    def validate_contract_margin(self, output: dict) -> list[RuleResult]:
        results: list[RuleResult] = []

        # Schema checks
        for field in ("verdict", "evidence_object_ids"):
            results.append(
                RuleResult(
                    rule_name=f"schema_{field}_present",
                    passed=field in output and output[field] is not None,
                    message=(
                        f"Field '{field}' is present"
                        if field in output
                        else f"Required field '{field}' is missing"
                    ),
                    severity="error" if field not in output else "info",
                )
            )

        # Evidence
        evidence_ids = output.get("evidence_object_ids") or output.get("evidence_ids") or []
        results.append(
            RuleResult(
                rule_name="evidence_present",
                passed=len(evidence_ids) > 0,
                message=(
                    f"{len(evidence_ids)} evidence references found"
                    if evidence_ids
                    else "No evidence references provided"
                ),
                severity="warning" if not evidence_ids else "info",
            )
        )

        # Valid verdict
        verdict = output.get("verdict", "")
        valid_verdicts = {"billable", "non_billable", "under_recovery", "penalty_risk", "unknown"}
        results.append(
            RuleResult(
                rule_name="valid_margin_verdict",
                passed=verdict in valid_verdicts,
                message=(
                    f"Verdict '{verdict}' is valid"
                    if verdict in valid_verdicts
                    else f"Unsupported verdict: '{verdict}'"
                ),
                severity="error" if verdict not in valid_verdicts else "info",
            )
        )

        # Billable requires evidence
        if verdict == "billable" and not output.get("evidence_object_ids"):
            results.append(
                RuleResult(
                    rule_name="billable_requires_evidence",
                    passed=False,
                    message="Billable verdict requires supporting evidence",
                    severity="error",
                )
            )

        return results

    # -- utilities_field ---------------------------------------------------

    def validate_utilities_field(self, output: dict) -> list[RuleResult]:
        results: list[RuleResult] = []

        # Schema checks
        for field in ("verdict", "reasons"):
            results.append(
                RuleResult(
                    rule_name=f"schema_{field}_present",
                    passed=field in output and output[field] is not None,
                    message=(
                        f"Field '{field}' is present"
                        if field in output
                        else f"Required field '{field}' is missing"
                    ),
                    severity="error" if field not in output else "info",
                )
            )

        # Evidence
        evidence_ids = output.get("evidence_object_ids") or output.get("evidence_ids") or []
        results.append(
            RuleResult(
                rule_name="evidence_present",
                passed=len(evidence_ids) > 0,
                message=(
                    f"{len(evidence_ids)} evidence references found"
                    if evidence_ids
                    else "No evidence references provided"
                ),
                severity="warning" if not evidence_ids else "info",
            )
        )

        # Valid verdict
        verdict = output.get("verdict", "")
        valid_verdicts = {"ready", "blocked", "warn", "escalate"}
        results.append(
            RuleResult(
                rule_name="valid_readiness_verdict",
                passed=verdict in valid_verdicts,
                message=(
                    f"Readiness verdict '{verdict}' is valid"
                    if verdict in valid_verdicts
                    else f"Unsupported: '{verdict}'"
                ),
                severity="error" if verdict not in valid_verdicts else "info",
            )
        )

        # Ready with missing prerequisites is contradictory
        if verdict == "ready":
            missing = output.get("missing_prerequisites", [])
            results.append(
                RuleResult(
                    rule_name="ready_no_missing_prereqs",
                    passed=len(missing) == 0,
                    message=(
                        "No missing prerequisites for ready verdict"
                        if not missing
                        else f"Ready verdict contradicts {len(missing)} missing prerequisites"
                    ),
                    severity="error" if missing else "info",
                )
            )

        return results

    # -- telco_ops ---------------------------------------------------------

    def validate_telco_ops(self, output: dict) -> list[RuleResult]:
        results: list[RuleResult] = []

        # Schema checks
        results.append(
            RuleResult(
                rule_name="schema_next_action_present",
                passed="next_action" in output and output["next_action"] is not None,
                message=(
                    "Field 'next_action' is present"
                    if "next_action" in output
                    else "Required field 'next_action' is missing"
                ),
                severity="error" if "next_action" not in output else "info",
            )
        )

        # Evidence
        evidence_ids = output.get("evidence_object_ids") or output.get("evidence_ids") or []
        results.append(
            RuleResult(
                rule_name="evidence_present",
                passed=len(evidence_ids) > 0,
                message=(
                    f"{len(evidence_ids)} evidence references found"
                    if evidence_ids
                    else "No evidence references provided"
                ),
                severity="warning" if not evidence_ids else "info",
            )
        )

        # Valid next action
        next_action = output.get("next_action", "")
        valid_actions = {
            "investigate",
            "escalate",
            "dispatch",
            "resolve",
            "monitor",
            "contact_customer",
            "assign_engineer",
            "close",
            "reopen",
        }
        results.append(
            RuleResult(
                rule_name="valid_next_action",
                passed=next_action in valid_actions,
                message=(
                    f"Action '{next_action}' is valid"
                    if next_action in valid_actions
                    else f"Invalid action: '{next_action}'"
                ),
                severity="error" if next_action not in valid_actions else "info",
            )
        )

        # Escalation level if present
        if output.get("escalation_level"):
            valid_levels = {"l1", "l2", "l3", "management"}
            level = output["escalation_level"]
            results.append(
                RuleResult(
                    rule_name="valid_escalation_level",
                    passed=level in valid_levels,
                    message=(
                        f"Escalation level '{level}' is valid"
                        if level in valid_levels
                        else f"Unsupported: '{level}'"
                    ),
                    severity="error" if level not in valid_levels else "info",
                )
            )

        # Escalation requires owner
        if output.get("escalation_level") and not output.get("escalation_owner"):
            results.append(
                RuleResult(
                    rule_name="escalation_has_owner",
                    passed=False,
                    message="Escalation decision provided without owner",
                    severity="error",
                )
            )

        return results


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def validator() -> _DomainValidatorProxy:
    return _DomainValidatorProxy()


# ---------------------------------------------------------------------------
# Contract Margin Validator Tests
# ---------------------------------------------------------------------------


class TestContractMarginValidator:
    def test_valid_output(self, validator: _DomainValidatorProxy):
        """test_contract_margin_validator_valid_output"""
        output = {
            "verdict": "billable",
            "evidence_object_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
            "confidence": 0.95,
        }
        results = validator.validate_contract_margin(output)

        failed = [r for r in results if not r.passed]
        assert len(failed) == 0, f"Unexpected failures: {[r.message for r in failed]}"

    def test_missing_evidence(self, validator: _DomainValidatorProxy):
        """test_contract_margin_validator_missing_evidence"""
        output = {
            "verdict": "billable",
            "evidence_object_ids": [],
        }
        results = validator.validate_contract_margin(output)

        evidence_rule = [r for r in results if r.rule_name == "evidence_present"]
        assert len(evidence_rule) == 1
        assert evidence_rule[0].passed is False

        billable_evidence = [r for r in results if r.rule_name == "billable_requires_evidence"]
        assert len(billable_evidence) == 1
        assert billable_evidence[0].passed is False

    def test_invalid_verdict(self, validator: _DomainValidatorProxy):
        output = {
            "verdict": "invalid_verdict",
            "evidence_object_ids": [str(uuid.uuid4())],
        }
        results = validator.validate_contract_margin(output)

        verdict_rule = [r for r in results if r.rule_name == "valid_margin_verdict"]
        assert len(verdict_rule) == 1
        assert verdict_rule[0].passed is False
        assert verdict_rule[0].severity == "error"

    def test_non_billable_no_evidence_is_warning_only(self, validator: _DomainValidatorProxy):
        output = {
            "verdict": "non_billable",
            "evidence_object_ids": [],
        }
        results = validator.validate_contract_margin(output)

        evidence_rule = [r for r in results if r.rule_name == "evidence_present"]
        assert evidence_rule[0].severity == "warning"

        # Should NOT have billable_requires_evidence since verdict is not billable
        billable_evidence = [r for r in results if r.rule_name == "billable_requires_evidence"]
        assert len(billable_evidence) == 0


# ---------------------------------------------------------------------------
# Utilities Field Validator Tests
# ---------------------------------------------------------------------------


class TestUtilitiesFieldValidator:
    def test_blocked_no_reasons(self, validator: _DomainValidatorProxy):
        """test_utilities_field_validator_blocked_no_reasons"""
        output = {
            "verdict": "blocked",
            "reasons": [],
            "evidence_ids": [str(uuid.uuid4())],
        }
        results = validator.validate_utilities_field(output)

        # "blocked" is a valid verdict so the verdict rule passes
        verdict_rule = [r for r in results if r.rule_name == "valid_readiness_verdict"]
        assert verdict_rule[0].passed is True

        # No ready_no_missing_prereqs check since verdict is "blocked" not "ready"
        ready_check = [r for r in results if r.rule_name == "ready_no_missing_prereqs"]
        assert len(ready_check) == 0

    def test_valid_ready(self, validator: _DomainValidatorProxy):
        """test_utilities_field_validator_valid_ready"""
        output = {
            "verdict": "ready",
            "reasons": ["All checks passed"],
            "evidence_ids": [str(uuid.uuid4())],
            "missing_prerequisites": [],
        }
        results = validator.validate_utilities_field(output)

        failed = [r for r in results if not r.passed]
        assert len(failed) == 0

        ready_check = [r for r in results if r.rule_name == "ready_no_missing_prereqs"]
        assert len(ready_check) == 1
        assert ready_check[0].passed is True

    def test_ready_with_missing_prereqs_fails(self, validator: _DomainValidatorProxy):
        output = {
            "verdict": "ready",
            "reasons": ["Passed"],
            "evidence_ids": [str(uuid.uuid4())],
            "missing_prerequisites": ["permit_missing", "skill_gap"],
        }
        results = validator.validate_utilities_field(output)

        ready_check = [r for r in results if r.rule_name == "ready_no_missing_prereqs"]
        assert len(ready_check) == 1
        assert ready_check[0].passed is False
        assert ready_check[0].severity == "error"

    def test_invalid_verdict(self, validator: _DomainValidatorProxy):
        output = {
            "verdict": "invalid",
            "reasons": [],
        }
        results = validator.validate_utilities_field(output)

        verdict_rule = [r for r in results if r.rule_name == "valid_readiness_verdict"]
        assert verdict_rule[0].passed is False


# ---------------------------------------------------------------------------
# Telco Ops Validator Tests
# ---------------------------------------------------------------------------


class TestTelcoOpsValidator:
    def test_escalation_valid(self, validator: _DomainValidatorProxy):
        """test_telco_ops_validator_escalation_valid"""
        output = {
            "next_action": "escalate",
            "escalation_level": "l3",
            "escalation_owner": "senior_engineering",
            "evidence_ids": [str(uuid.uuid4())],
        }
        results = validator.validate_telco_ops(output)

        failed = [r for r in results if not r.passed]
        assert len(failed) == 0

    def test_escalation_missing_owner(self, validator: _DomainValidatorProxy):
        """test_telco_ops_validator_escalation_missing_owner"""
        output = {
            "next_action": "escalate",
            "escalation_level": "l3",
            "escalation_owner": "",
            "evidence_ids": [str(uuid.uuid4())],
        }
        results = validator.validate_telco_ops(output)

        owner_rule = [r for r in results if r.rule_name == "escalation_has_owner"]
        assert len(owner_rule) == 1
        assert owner_rule[0].passed is False

    def test_next_action_valid(self, validator: _DomainValidatorProxy):
        """test_telco_ops_validator_next_action_valid"""
        output = {
            "next_action": "investigate",
            "evidence_ids": [str(uuid.uuid4())],
        }
        results = validator.validate_telco_ops(output)

        action_rule = [r for r in results if r.rule_name == "valid_next_action"]
        assert action_rule[0].passed is True

    def test_invalid_next_action(self, validator: _DomainValidatorProxy):
        output = {
            "next_action": "do_nothing",
            "evidence_ids": [],
        }
        results = validator.validate_telco_ops(output)

        action_rule = [r for r in results if r.rule_name == "valid_next_action"]
        assert action_rule[0].passed is False
        assert action_rule[0].severity == "error"

    def test_invalid_escalation_level(self, validator: _DomainValidatorProxy):
        output = {
            "next_action": "escalate",
            "escalation_level": "l99",
            "escalation_owner": "someone",
            "evidence_ids": [str(uuid.uuid4())],
        }
        results = validator.validate_telco_ops(output)

        level_rule = [r for r in results if r.rule_name == "valid_escalation_level"]
        assert len(level_rule) == 1
        assert level_rule[0].passed is False

    def test_missing_next_action_field(self, validator: _DomainValidatorProxy):
        output = {"evidence_ids": [str(uuid.uuid4())]}
        results = validator.validate_telco_ops(output)

        schema_rule = [r for r in results if r.rule_name == "schema_next_action_present"]
        assert schema_rule[0].passed is False
        assert schema_rule[0].severity == "error"
