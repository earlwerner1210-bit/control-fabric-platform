"""
Bounded Inference Engine — Full test suite.
Tests: domain types, policy gate, scope enforcer, MLX runner (simulation),
typed output validator, evidence logger, and full engine pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Ensure the inference-gateway package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.engine import BoundedInferenceEngine
from core.evidence_logger import EvidenceLogger
from core.mlx_runner import MLXRunner, ModelConfig
from core.policy_gate import PolicyGate, PolicyRule, PolicyStore, build_default_policy_store
from core.scope_enforcer import ScopeEnforcer, ScopeViolationError
from core.typed_output_validator import TypedOutputValidator
from models.domain_types import (
    EvidenceRecord,
    HypothesisType,
    InferenceRequest,
    InferenceResponse,
    InferenceStatus,
    PolicyDecision,
    PolicyGateResult,
    RejectionReason,
    ScopeParameters,
    TypedHypothesis,
)

# ══════════════════════════════════════════════════════════════════════════════
# Domain Types
# ══════════════════════════════════════════════════════════════════════════════


class TestScopeParameters:
    def test_scope_hash_deterministic(self):
        s1 = ScopeParameters(
            allowed_control_object_ids=["obj-1", "obj-2"],
            allowed_operational_planes=["risk"],
        )
        s2 = ScopeParameters(
            allowed_control_object_ids=["obj-1", "obj-2"],
            allowed_operational_planes=["risk"],
        )
        assert s1.scope_hash == s2.scope_hash
        assert s1.scope_hash != ""

    def test_scope_hash_changes_with_inputs(self):
        s1 = ScopeParameters(
            allowed_control_object_ids=["obj-1"],
            allowed_operational_planes=["risk"],
        )
        s2 = ScopeParameters(
            allowed_control_object_ids=["obj-1", "obj-2"],
            allowed_operational_planes=["risk"],
        )
        assert s1.scope_hash != s2.scope_hash

    def test_scope_frozen(self):
        s = ScopeParameters(
            allowed_control_object_ids=["obj-1"],
            allowed_operational_planes=["risk"],
        )
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            s.max_graph_depth = 5


class TestPolicyGateResult:
    def test_allow_requires_scope(self):
        with pytest.raises(ValueError, match="ALLOW decision must include scope parameters"):
            PolicyGateResult(
                decision=PolicyDecision.ALLOW,
                policy_id="test",
                policy_version="1.0",
                scope_parameters=None,
            )

    def test_deny_requires_reason(self):
        with pytest.raises(ValueError, match="DENY decision must include denial_reason"):
            PolicyGateResult(
                decision=PolicyDecision.DENY,
                policy_id="test",
                policy_version="1.0",
                denial_reason=None,
            )

    def test_gate_signature_computed(self):
        result = PolicyGateResult(
            decision=PolicyDecision.DENY,
            policy_id="test",
            policy_version="1.0",
            denial_reason="not allowed",
        )
        assert result.gate_signature != ""
        assert len(result.gate_signature) == 64


class TestTypedHypothesis:
    def test_is_executable_always_false(self):
        h = TypedHypothesis(
            hypothesis_type=HypothesisType.GAP_ANALYSIS,
            title="Test",
            findings=["finding-1"],
            affected_control_object_ids=["obj-1"],
            confidence_score=0.8,
            evidence_references=["ev-1"],
            reasoning_trace=["step-1"],
            scope_hash_used="abc",
            model_id="test",
            is_executable=True,  # Should be forced to False
        )
        assert h.is_executable is False

    def test_hypothesis_hash_computed(self):
        h = TypedHypothesis(
            hypothesis_type=HypothesisType.RISK_ASSESSMENT,
            title="Test",
            findings=["finding-1"],
            affected_control_object_ids=["obj-1"],
            confidence_score=0.9,
            evidence_references=["ev-1"],
            reasoning_trace=["step-1"],
            scope_hash_used="abc",
            model_id="test",
        )
        assert h.hypothesis_hash != ""
        assert len(h.hypothesis_hash) == 64


class TestEvidenceRecord:
    def test_chain_hash_computed(self):
        r = EvidenceRecord(
            session_id="sess-1",
            request_hash="req-hash",
            policy_gate_signature="gate-sig",
            scope_hash="scope-hash",
            model_id="test",
            inference_duration_ms=100,
            final_status=InferenceStatus.COMPLETE,
        )
        assert r.chain_hash != ""
        assert len(r.chain_hash) == 64

    def test_frozen(self):
        r = EvidenceRecord(
            session_id="sess-1",
            request_hash="req-hash",
            policy_gate_signature="gate-sig",
            scope_hash="scope-hash",
            model_id="test",
            inference_duration_ms=100,
            final_status=InferenceStatus.COMPLETE,
        )
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            r.session_id = "tampered"


class TestInferenceRequest:
    def test_request_hash_computed(self):
        req = InferenceRequest(
            requesting_entity_id="analyst-1",
            target_control_object_ids=["obj-1"],
            target_operational_plane="risk",
            hypothesis_type_requested=HypothesisType.GAP_ANALYSIS,
        )
        assert req.request_hash != ""


# ══════════════════════════════════════════════════════════════════════════════
# Policy Gate
# ══════════════════════════════════════════════════════════════════════════════


class TestPolicyGate:
    def test_allow_standard_plane(self):
        gate = PolicyGate()
        result = gate.evaluate(
            requesting_entity_id="analyst-1",
            target_operational_plane="risk",
            hypothesis_type_requested="gap_analysis",
            target_control_object_ids=["obj-1", "obj-2"],
        )
        assert result.decision == PolicyDecision.ALLOW
        assert result.scope_parameters is not None

    def test_deny_unknown_plane(self):
        gate = PolicyGate()
        result = gate.evaluate(
            requesting_entity_id="analyst-1",
            target_operational_plane="nonexistent_plane",
            hypothesis_type_requested="gap_analysis",
            target_control_object_ids=["obj-1"],
        )
        assert result.decision == PolicyDecision.DENY

    def test_deny_restricted_plane_unauthorized(self):
        gate = PolicyGate()
        result = gate.evaluate(
            requesting_entity_id="junior-analyst",
            target_operational_plane="financial",
            hypothesis_type_requested="risk_assessment",
            target_control_object_ids=["obj-1"],
        )
        assert result.decision == PolicyDecision.DENY

    def test_allow_restricted_plane_authorized(self):
        gate = PolicyGate()
        result = gate.evaluate(
            requesting_entity_id="senior-analyst",
            target_operational_plane="financial",
            hypothesis_type_requested="risk_assessment",
            target_control_object_ids=["obj-1"],
        )
        assert result.decision == PolicyDecision.ALLOW

    def test_deny_too_many_objects(self):
        gate = PolicyGate()
        ids = [f"obj-{i}" for i in range(51)]
        result = gate.evaluate(
            requesting_entity_id="analyst-1",
            target_operational_plane="risk",
            hypothesis_type_requested="gap_analysis",
            target_control_object_ids=ids,
        )
        assert result.decision == PolicyDecision.DENY

    def test_deny_disallowed_hypothesis_type(self):
        gate = PolicyGate()
        result = gate.evaluate(
            requesting_entity_id="senior-analyst",
            target_operational_plane="financial",
            hypothesis_type_requested="pattern_detection",
            target_control_object_ids=["obj-1"],
        )
        assert result.decision == PolicyDecision.DENY

    def test_scope_parameters_populated_on_allow(self):
        gate = PolicyGate()
        result = gate.evaluate(
            requesting_entity_id="analyst-1",
            target_operational_plane="compliance",
            hypothesis_type_requested="compliance_mapping",
            target_control_object_ids=["obj-1", "obj-2"],
        )
        assert result.decision == PolicyDecision.ALLOW
        assert result.scope_parameters is not None
        assert result.scope_parameters.scope_hash != ""
        assert result.scope_parameters.allowed_control_object_ids == ["obj-1", "obj-2"]


# ══════════════════════════════════════════════════════════════════════════════
# Scope Enforcer
# ══════════════════════════════════════════════════════════════════════════════


class TestScopeEnforcer:
    def _scope(self, obj_ids=None):
        return ScopeParameters(
            allowed_control_object_ids=obj_ids or ["obj-1", "obj-2"],
            allowed_operational_planes=["risk"],
            max_graph_depth=2,
        )

    def test_filters_control_objects(self):
        enforcer = ScopeEnforcer(self._scope())
        raw = {
            "control_objects": [
                {"id": "obj-1", "name": "A"},
                {"id": "obj-3", "name": "C"},  # not in scope
            ]
        }
        result = enforcer.enforce(raw)
        assert len(result["control_objects"]) == 1
        assert result["control_objects"][0]["id"] == "obj-1"

    def test_filters_relationships(self):
        enforcer = ScopeEnforcer(self._scope())
        raw = {
            "relationships": [
                {"type": "mitigates", "source_id": "obj-1", "target_id": "obj-2"},
                {"type": "mitigates", "source_id": "obj-1", "target_id": "obj-3"},  # out of scope
                {"type": "unknown_type", "source_id": "obj-1", "target_id": "obj-2"},  # bad type
            ]
        }
        result = enforcer.enforce(raw)
        assert len(result["relationships"]) == 1

    def test_filters_planes(self):
        enforcer = ScopeEnforcer(self._scope())
        raw = {"plane_data": {"risk": {"data": 1}, "financial": {"data": 2}}}
        result = enforcer.enforce(raw)
        assert "risk" in result["plane_data"]
        assert "financial" not in result["plane_data"]

    def test_strips_sensitive_fields(self):
        enforcer = ScopeEnforcer(self._scope())
        raw = {"control_objects": [{"id": "obj-1", "credentials": "secret", "name": "A"}]}
        result = enforcer.enforce(raw)
        obj = result["control_objects"][0]
        assert "credentials" not in obj
        assert obj["name"] == "A"

    def test_scope_metadata_attached(self):
        enforcer = ScopeEnforcer(self._scope())
        result = enforcer.enforce({})
        assert "_scope_metadata" in result
        assert result["_scope_metadata"]["scope_hash"] == self._scope().scope_hash

    def test_classification_ceiling(self):
        enforcer = ScopeEnforcer(self._scope())
        raw = {
            "control_objects": [
                {"id": "obj-1", "classification": "restricted", "data": "secret"},
            ]
        }
        result = enforcer.enforce(raw)
        obj = result["control_objects"][0]
        assert obj.get("_redacted") is True


# ══════════════════════════════════════════════════════════════════════════════
# MLX Runner (Simulation Mode)
# ══════════════════════════════════════════════════════════════════════════════


class TestMLXRunner:
    def test_simulation_mode(self):
        runner = MLXRunner(simulation_mode=True)
        assert runner.is_simulation is True

    def test_infer_produces_hypothesis(self):
        runner = MLXRunner(simulation_mode=True)
        scope = ScopeParameters(
            allowed_control_object_ids=["obj-1", "obj-2"],
            allowed_operational_planes=["risk"],
        )
        hypothesis, duration_ms = runner.infer(
            scope=scope,
            sanitised_context={},
            hypothesis_type=HypothesisType.GAP_ANALYSIS,
            session_id="test-session",
        )
        assert isinstance(hypothesis, TypedHypothesis)
        assert hypothesis.is_executable is False
        assert hypothesis.scope_hash_used == scope.scope_hash
        assert duration_ms >= 0

    def test_model_id(self):
        runner = MLXRunner(simulation_mode=True)
        assert runner.model_id == "phi-3-mini"


# ══════════════════════════════════════════════════════════════════════════════
# Typed Output Validator
# ══════════════════════════════════════════════════════════════════════════════


class TestTypedOutputValidator:
    def _scope(self):
        return ScopeParameters(
            allowed_control_object_ids=["obj-1", "obj-2"],
            allowed_operational_planes=["risk"],
        )

    def _hypothesis(self, **overrides):
        scope = self._scope()
        defaults = dict(
            hypothesis_type=HypothesisType.GAP_ANALYSIS,
            title="Test Hypothesis",
            findings=["finding-1"],
            affected_control_object_ids=["obj-1"],
            confidence_score=0.8,
            evidence_references=["ev-1"],
            reasoning_trace=["step-1", "step-2"],
            scope_hash_used=scope.scope_hash,
            model_id="test-model",
        )
        defaults.update(overrides)
        return TypedHypothesis(**defaults)

    def test_valid_hypothesis_passes(self):
        validator = TypedOutputValidator()
        result = validator.validate(self._hypothesis(), HypothesisType.GAP_ANALYSIS, self._scope())
        assert result.passed is True

    def test_low_confidence_rejected(self):
        validator = TypedOutputValidator(min_confidence=0.9)
        result = validator.validate(
            self._hypothesis(confidence_score=0.5), HypothesisType.GAP_ANALYSIS, self._scope()
        )
        assert result.passed is False
        assert result.rejection_reason == RejectionReason.CONFIDENCE_BELOW_THRESHOLD

    def test_type_mismatch_rejected(self):
        validator = TypedOutputValidator()
        result = validator.validate(
            self._hypothesis(), HypothesisType.RISK_ASSESSMENT, self._scope()
        )
        assert result.passed is False
        assert result.rejection_reason == RejectionReason.SCHEMA_VIOLATION

    def test_out_of_scope_objects_rejected(self):
        validator = TypedOutputValidator()
        h = self._hypothesis(affected_control_object_ids=["obj-1", "obj-UNKNOWN"])
        result = validator.validate(h, HypothesisType.GAP_ANALYSIS, self._scope())
        assert result.passed is False
        assert result.rejection_reason == RejectionReason.SCOPE_VIOLATION

    def test_scope_hash_mismatch_rejected(self):
        validator = TypedOutputValidator()
        h = self._hypothesis(scope_hash_used="wrong-hash")
        result = validator.validate(h, HypothesisType.GAP_ANALYSIS, self._scope())
        assert result.passed is False
        assert result.rejection_reason == RejectionReason.PROVENANCE_INVALID


# ══════════════════════════════════════════════════════════════════════════════
# Evidence Logger
# ══════════════════════════════════════════════════════════════════════════════


class TestEvidenceLogger:
    def _gate_result(self):
        scope = ScopeParameters(
            allowed_control_object_ids=["obj-1"],
            allowed_operational_planes=["risk"],
        )
        return PolicyGateResult(
            decision=PolicyDecision.ALLOW,
            policy_id="test",
            policy_version="1.0",
            scope_parameters=scope,
        )

    def _hypothesis(self):
        scope = ScopeParameters(
            allowed_control_object_ids=["obj-1"],
            allowed_operational_planes=["risk"],
        )
        return TypedHypothesis(
            hypothesis_type=HypothesisType.GAP_ANALYSIS,
            title="Test",
            findings=["f1"],
            affected_control_object_ids=["obj-1"],
            confidence_score=0.8,
            evidence_references=["ev-1"],
            reasoning_trace=["s1"],
            scope_hash_used=scope.scope_hash,
            model_id="test",
        )

    def test_record_success(self):
        logger = EvidenceLogger()
        record = logger.record_success(
            session_id="s1",
            request_hash="rh",
            policy_gate_result=self._gate_result(),
            hypothesis=self._hypothesis(),
            model_id="test",
            inference_duration_ms=100,
        )
        assert record.final_status == InferenceStatus.COMPLETE
        assert record.chain_hash != ""
        assert logger.record_count == 1

    def test_record_rejection(self):
        logger = EvidenceLogger()
        gate = PolicyGateResult(
            decision=PolicyDecision.DENY,
            policy_id="test",
            policy_version="1.0",
            denial_reason="denied",
        )
        record = logger.record_rejection(
            session_id="s1",
            request_hash="rh",
            policy_gate_result=gate,
            model_id="test",
            rejection_reason=RejectionReason.POLICY_DENIED,
            rejection_detail="denied",
        )
        assert record.final_status == InferenceStatus.REJECTED
        assert logger.record_count == 1

    def test_chain_integrity(self):
        logger = EvidenceLogger()
        logger.record_success(
            session_id="s1",
            request_hash="rh",
            policy_gate_result=self._gate_result(),
            hypothesis=self._hypothesis(),
            model_id="test",
            inference_duration_ms=50,
        )
        assert logger.verify_chain_integrity() is True

    def test_session_index(self):
        logger = EvidenceLogger()
        logger.record_success(
            session_id="s1",
            request_hash="rh",
            policy_gate_result=self._gate_result(),
            hypothesis=self._hypothesis(),
            model_id="test",
            inference_duration_ms=50,
        )
        assert len(logger.get_session_records("s1")) == 1
        assert len(logger.get_session_records("nonexistent")) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Full Engine Pipeline
# ══════════════════════════════════════════════════════════════════════════════


class TestBoundedInferenceEngine:
    def test_happy_path(self):
        engine = BoundedInferenceEngine(simulation_mode=True)
        request = InferenceRequest(
            requesting_entity_id="analyst-1",
            target_control_object_ids=["obj-1", "obj-2"],
            target_operational_plane="risk",
            hypothesis_type_requested=HypothesisType.GAP_ANALYSIS,
        )
        response = engine.infer(request)
        assert response.status == InferenceStatus.COMPLETE
        assert response.hypothesis is not None
        assert response.hypothesis.is_executable is False
        assert response.evidence_record is not None
        assert response.evidence_record.chain_hash != ""

    def test_policy_denied(self):
        engine = BoundedInferenceEngine(simulation_mode=True)
        request = InferenceRequest(
            requesting_entity_id="analyst-1",
            target_control_object_ids=["obj-1"],
            target_operational_plane="nonexistent_plane",
            hypothesis_type_requested=HypothesisType.GAP_ANALYSIS,
        )
        response = engine.infer(request)
        assert response.status == InferenceStatus.REJECTED
        assert response.rejection_reason == RejectionReason.POLICY_DENIED
        assert response.evidence_record is not None

    def test_evidence_chain_integrity_after_multiple(self):
        engine = BoundedInferenceEngine(simulation_mode=True)
        for i in range(5):
            engine.infer(
                InferenceRequest(
                    requesting_entity_id="analyst-1",
                    target_control_object_ids=[f"obj-{i}"],
                    target_operational_plane="compliance",
                    hypothesis_type_requested=HypothesisType.COMPLIANCE_MAPPING,
                )
            )
        assert engine.evidence_logger.record_count == 5
        assert engine.evidence_logger.verify_chain_integrity() is True

    def test_restricted_plane_denied_for_unauthorized(self):
        engine = BoundedInferenceEngine(simulation_mode=True)
        request = InferenceRequest(
            requesting_entity_id="junior-analyst",
            target_control_object_ids=["obj-1"],
            target_operational_plane="financial",
            hypothesis_type_requested=HypothesisType.RISK_ASSESSMENT,
        )
        response = engine.infer(request)
        assert response.status == InferenceStatus.REJECTED

    def test_restricted_plane_allowed_for_authorized(self):
        engine = BoundedInferenceEngine(simulation_mode=True)
        request = InferenceRequest(
            requesting_entity_id="senior-analyst",
            target_control_object_ids=["obj-1"],
            target_operational_plane="financial",
            hypothesis_type_requested=HypothesisType.RISK_ASSESSMENT,
        )
        response = engine.infer(request)
        assert response.status == InferenceStatus.COMPLETE

    def test_hypothesis_never_executable(self):
        engine = BoundedInferenceEngine(simulation_mode=True)
        for ht in HypothesisType:
            response = engine.infer(
                InferenceRequest(
                    requesting_entity_id="analyst-1",
                    target_control_object_ids=["obj-1"],
                    target_operational_plane="risk",
                    hypothesis_type_requested=ht,
                )
            )
            if response.hypothesis:
                assert response.hypothesis.is_executable is False
