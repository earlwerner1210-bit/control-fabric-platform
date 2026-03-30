"""
Control Fabric Platform — Bounded Inference Engine
Evidence Logger: Cryptographic Provenance Chain

Patent Claim (Theme 4): Every action carries its complete evidence chain.
No session completes without an EvidenceRecord being committed.

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import logging

from models.domain_types import (
    EvidenceRecord,
    InferenceStatus,
    PolicyGateResult,
    RejectionReason,
    TypedHypothesis,
)

logger = logging.getLogger(__name__)


class EvidenceLogger:
    def __init__(self) -> None:
        self._records: list[EvidenceRecord] = []
        self._session_index: dict[str, list[EvidenceRecord]] = {}

    def record_success(
        self,
        session_id: str,
        request_hash: str,
        policy_gate_result: PolicyGateResult,
        hypothesis: TypedHypothesis,
        model_id: str,
        inference_duration_ms: int,
    ) -> EvidenceRecord:
        assert policy_gate_result.scope_parameters is not None
        record = EvidenceRecord(
            session_id=session_id,
            request_hash=request_hash,
            policy_gate_signature=policy_gate_result.gate_signature,
            scope_hash=policy_gate_result.scope_parameters.scope_hash,
            hypothesis_hash=hypothesis.hypothesis_hash,
            model_id=model_id,
            inference_duration_ms=inference_duration_ms,
            final_status=InferenceStatus.COMPLETE,
        )
        self._commit(record)
        return record

    def record_rejection(
        self,
        session_id: str,
        request_hash: str,
        policy_gate_result: PolicyGateResult,
        model_id: str,
        rejection_reason: RejectionReason,
        rejection_detail: str,
    ) -> EvidenceRecord:
        record = EvidenceRecord(
            session_id=session_id,
            request_hash=request_hash,
            policy_gate_signature=policy_gate_result.gate_signature,
            scope_hash=policy_gate_result.scope_parameters.scope_hash
            if policy_gate_result.scope_parameters
            else "no-scope",
            hypothesis_hash=None,
            model_id=model_id,
            inference_duration_ms=0,
            final_status=InferenceStatus.REJECTED,
            rejection_reason=rejection_reason,
        )
        self._commit(record)
        return record

    def record_failure(
        self,
        session_id: str,
        request_hash: str,
        policy_gate_result: PolicyGateResult | None,
        model_id: str,
        failure_detail: str,
    ) -> EvidenceRecord:
        record = EvidenceRecord(
            session_id=session_id,
            request_hash=request_hash,
            policy_gate_signature=policy_gate_result.gate_signature
            if policy_gate_result
            else "no-gate",
            scope_hash=policy_gate_result.scope_parameters.scope_hash
            if policy_gate_result and policy_gate_result.scope_parameters
            else "no-scope",
            hypothesis_hash=None,
            model_id=model_id,
            inference_duration_ms=0,
            final_status=InferenceStatus.FAILED,
            rejection_reason=RejectionReason.EVIDENCE_INSUFFICIENT,
        )
        self._commit(record)
        return record

    def _commit(self, record: EvidenceRecord) -> None:
        self._records.append(record)
        self._session_index.setdefault(record.session_id, []).append(record)

    def get_session_records(self, session_id: str) -> list[EvidenceRecord]:
        return self._session_index.get(session_id, [])

    def get_all_records(self) -> list[EvidenceRecord]:
        return list(self._records)

    def verify_chain_integrity(self) -> bool:
        for record in self._records:
            recomputed = EvidenceRecord(
                record_id=record.record_id,
                session_id=record.session_id,
                request_hash=record.request_hash,
                policy_gate_signature=record.policy_gate_signature,
                scope_hash=record.scope_hash,
                hypothesis_hash=record.hypothesis_hash,
                model_id=record.model_id,
                inference_duration_ms=record.inference_duration_ms,
                final_status=record.final_status,
                rejection_reason=record.rejection_reason,
                created_at=record.created_at,
            )
            if recomputed.chain_hash != record.chain_hash:
                logger.critical("EVIDENCE CHAIN INTEGRITY FAILURE: record=%s", record.record_id)
                return False
        return True

    @property
    def record_count(self) -> int:
        return len(self._records)
