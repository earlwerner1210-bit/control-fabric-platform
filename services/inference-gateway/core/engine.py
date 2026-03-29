"""
Control Fabric Platform — Bounded Inference Engine
Pipeline Orchestrator

Full pipeline: PolicyGate → ScopeEnforcer → MLXRunner → TypedOutputValidator → EvidenceLogger

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import logging
import uuid

from core.evidence_logger import EvidenceLogger
from core.mlx_runner import MLXRunner, ModelConfig
from core.policy_gate import PolicyGate, PolicyStore
from core.scope_enforcer import ScopeEnforcer, ScopeViolationError
from core.typed_output_validator import TypedOutputValidator
from models.domain_types import (
    InferenceRequest,
    InferenceResponse,
    InferenceStatus,
    PolicyDecision,
    RejectionReason,
)

logger = logging.getLogger(__name__)


class BoundedInferenceEngine:
    def __init__(
        self,
        policy_store: PolicyStore | None = None,
        model_config: ModelConfig | None = None,
        simulation_mode: bool = False,
        min_confidence: float = 0.5,
    ) -> None:
        self._policy_gate = PolicyGate(policy_store=policy_store)
        self._mlx_runner = MLXRunner(model_config=model_config, simulation_mode=simulation_mode)
        self._validator = TypedOutputValidator(min_confidence=min_confidence)
        self._evidence_logger = EvidenceLogger()

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        session_id = str(uuid.uuid4())

        gate_result = self._policy_gate.evaluate(
            requesting_entity_id=request.requesting_entity_id,
            target_operational_plane=request.target_operational_plane,
            hypothesis_type_requested=request.hypothesis_type_requested.value,
            target_control_object_ids=request.target_control_object_ids,
        )

        if gate_result.decision == PolicyDecision.DENY:
            evidence = self._evidence_logger.record_rejection(
                session_id=session_id,
                request_hash=request.request_hash,
                policy_gate_result=gate_result,
                model_id=self._mlx_runner.model_id,
                rejection_reason=RejectionReason.POLICY_DENIED,
                rejection_detail=gate_result.denial_reason or "Denied",
            )
            return InferenceResponse(
                session_id=session_id,
                request_id=request.request_id,
                status=InferenceStatus.REJECTED,
                rejection_reason=RejectionReason.POLICY_DENIED,
                rejection_detail=gate_result.denial_reason,
                evidence_record=evidence,
                policy_gate_result=gate_result,
            )

        assert gate_result.scope_parameters is not None
        scope = gate_result.scope_parameters

        try:
            enforcer = ScopeEnforcer(scope=scope)
            sanitised_context = enforcer.enforce(request.context_data)
        except ScopeViolationError as e:
            evidence = self._evidence_logger.record_rejection(
                session_id=session_id,
                request_hash=request.request_hash,
                policy_gate_result=gate_result,
                model_id=self._mlx_runner.model_id,
                rejection_reason=RejectionReason.SCOPE_VIOLATION,
                rejection_detail=str(e),
            )
            return InferenceResponse(
                session_id=session_id,
                request_id=request.request_id,
                status=InferenceStatus.REJECTED,
                rejection_reason=RejectionReason.SCOPE_VIOLATION,
                rejection_detail=str(e),
                evidence_record=evidence,
                policy_gate_result=gate_result,
            )

        try:
            hypothesis, duration_ms = self._mlx_runner.infer(
                scope=scope,
                sanitised_context=sanitised_context,
                hypothesis_type=request.hypothesis_type_requested,
                session_id=session_id,
            )
        except Exception as e:
            evidence = self._evidence_logger.record_failure(
                session_id=session_id,
                request_hash=request.request_hash,
                policy_gate_result=gate_result,
                model_id=self._mlx_runner.model_id,
                failure_detail=str(e),
            )
            return InferenceResponse(
                session_id=session_id,
                request_id=request.request_id,
                status=InferenceStatus.FAILED,
                rejection_detail=str(e),
                evidence_record=evidence,
                policy_gate_result=gate_result,
            )

        validation_result = self._validator.validate(
            hypothesis=hypothesis, requested_type=request.hypothesis_type_requested, scope=scope
        )

        if not validation_result.passed:
            evidence = self._evidence_logger.record_rejection(
                session_id=session_id,
                request_hash=request.request_hash,
                policy_gate_result=gate_result,
                model_id=self._mlx_runner.model_id,
                rejection_reason=validation_result.rejection_reason
                or RejectionReason.SCHEMA_VIOLATION,
                rejection_detail=validation_result.rejection_detail or "Validation failed",
            )
            return InferenceResponse(
                session_id=session_id,
                request_id=request.request_id,
                status=InferenceStatus.REJECTED,
                rejection_reason=validation_result.rejection_reason,
                rejection_detail=validation_result.rejection_detail,
                evidence_record=evidence,
                policy_gate_result=gate_result,
            )

        evidence = self._evidence_logger.record_success(
            session_id=session_id,
            request_hash=request.request_hash,
            policy_gate_result=gate_result,
            hypothesis=hypothesis,
            model_id=self._mlx_runner.model_id,
            inference_duration_ms=duration_ms,
        )

        return InferenceResponse(
            session_id=session_id,
            request_id=request.request_id,
            status=InferenceStatus.COMPLETE,
            hypothesis=hypothesis,
            evidence_record=evidence,
            policy_gate_result=gate_result,
        )

    @property
    def evidence_logger(self) -> EvidenceLogger:
        return self._evidence_logger
