"""Tests for the Validation Chain Service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.validation_chain import (
    ChainOutcome,
    StepVerdict,
    ValidationChainRequest,
    ValidationStage,
)
from app.services.validation_chain.service import ValidationChainService

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
CASE = uuid.UUID("00000000-0000-0000-0000-000000000099")


def _make_request(**ctx_overrides) -> ValidationChainRequest:
    context = {
        "schema_valid": True,
        "evidence_completeness": 1.0,
        "boundary_valid": True,
        "failed_rules": [],
        "cross_plane_conflicts": 0,
        "policy_compliant": True,
        "confidence": 0.95,
        "confidence_threshold": 0.7,
    }
    context.update(ctx_overrides)
    return ValidationChainRequest(
        pilot_case_id=CASE,
        tenant_id=TENANT,
        context=context,
    )


class TestAllPass:
    def test_all_stages_pass(self):
        svc = ValidationChainService()
        result = svc.run_chain(_make_request())

        assert result.outcome == ChainOutcome.RELEASED
        assert result.passed_steps == 8
        assert result.failed_steps == 0
        assert result.blocking_stage is None

    def test_run_retrieval(self):
        svc = ValidationChainService()
        result = svc.run_chain(_make_request())
        fetched = svc.get_run(result.id)
        assert fetched is not None
        assert fetched.id == result.id


class TestSchemaFail:
    def test_schema_failure_blocks(self):
        svc = ValidationChainService()
        result = svc.run_chain(_make_request(schema_valid=False))

        assert result.outcome == ChainOutcome.BLOCKED
        assert result.blocking_stage == ValidationStage.SCHEMA
        assert result.failed_steps == 1


class TestEvidenceLevels:
    def test_evidence_pass(self):
        svc = ValidationChainService()
        result = svc.run_chain(_make_request(evidence_completeness=0.9))
        assert result.outcome == ChainOutcome.RELEASED

    def test_evidence_warn(self):
        svc = ValidationChainService()
        result = svc.run_chain(_make_request(evidence_completeness=0.6))
        assert result.outcome == ChainOutcome.WARN_RELEASED
        assert result.warned_steps >= 1

    def test_evidence_fail(self):
        svc = ValidationChainService()
        result = svc.run_chain(_make_request(evidence_completeness=0.2))
        assert result.outcome == ChainOutcome.BLOCKED
        assert result.blocking_stage == ValidationStage.EVIDENCE


class TestRuleFail:
    def test_rule_failure(self):
        svc = ValidationChainService()
        result = svc.run_chain(_make_request(failed_rules=["R001", "R002"]))
        assert result.outcome == ChainOutcome.BLOCKED
        assert result.blocking_stage == ValidationStage.RULE


class TestCrossPlane:
    def test_cross_plane_warn(self):
        svc = ValidationChainService()
        result = svc.run_chain(_make_request(cross_plane_conflicts=1))
        assert result.outcome == ChainOutcome.WARN_RELEASED

    def test_cross_plane_fail(self):
        svc = ValidationChainService()
        result = svc.run_chain(_make_request(cross_plane_conflicts=5))
        assert result.outcome == ChainOutcome.BLOCKED
        assert result.blocking_stage == ValidationStage.CROSS_PLANE


class TestConfidence:
    def test_confidence_fail(self):
        svc = ValidationChainService()
        result = svc.run_chain(_make_request(confidence=0.3, confidence_threshold=0.7))
        assert result.outcome == ChainOutcome.BLOCKED
        assert result.blocking_stage == ValidationStage.CONFIDENCE


class TestPolicyFail:
    def test_policy_violation(self):
        svc = ValidationChainService()
        result = svc.run_chain(_make_request(policy_compliant=False, policy_reason="Exceeds limit"))
        assert result.outcome == ChainOutcome.BLOCKED
        assert result.blocking_stage == ValidationStage.POLICY


class TestSkipStages:
    def test_skip_evidence(self):
        svc = ValidationChainService()
        result = svc.run_chain(
            ValidationChainRequest(
                pilot_case_id=CASE,
                tenant_id=TENANT,
                context={"evidence_completeness": 0.1},
                skip_stages=[ValidationStage.EVIDENCE],
            )
        )
        assert result.skipped_steps == 1
        # Evidence skip means the low score doesn't block
        evidence_step = next(s for s in result.steps if s.stage == ValidationStage.EVIDENCE)
        assert evidence_step.skipped is True


class TestFailFast:
    def test_fail_fast_stops_early(self):
        svc = ValidationChainService()
        result = svc.run_chain(
            ValidationChainRequest(
                pilot_case_id=CASE,
                tenant_id=TENANT,
                context={"schema_valid": False},
                fail_fast=True,
            )
        )
        assert result.total_steps == 1  # Stopped at schema
        assert result.outcome == ChainOutcome.BLOCKED

    def test_no_fail_fast_continues(self):
        svc = ValidationChainService()
        result = svc.run_chain(
            ValidationChainRequest(
                pilot_case_id=CASE,
                tenant_id=TENANT,
                context={"schema_valid": False, "evidence_completeness": 0.1},
                fail_fast=False,
            )
        )
        assert result.total_steps == 8
        assert result.failed_steps >= 2


class TestCustomValidator:
    def test_custom_validator(self):
        def custom_schema(stage, request, context):
            return {"verdict": "pass", "message": "Custom passed"}

        svc = ValidationChainService(validators={ValidationStage.SCHEMA: custom_schema})
        result = svc.run_chain(_make_request())
        schema_step = next(s for s in result.steps if s.stage == ValidationStage.SCHEMA)
        assert schema_step.message == "Custom passed"


class TestSummary:
    def test_summary(self):
        svc = ValidationChainService()
        svc.run_chain(_make_request())
        svc.run_chain(_make_request(schema_valid=False))
        svc.run_chain(_make_request(evidence_completeness=0.6))

        summary = svc.get_summary(TENANT)
        assert summary.total_runs == 3
        assert summary.released == 1
        assert summary.blocked == 1
        assert summary.warn_released == 1
        assert summary.most_common_blocking_stage == "schema"
