"""
Control Fabric Platform — Bounded Inference Engine
Typed Output Validator: Deterministic Structured Output Enforcement

Patent Claim (Theme 3, Step 7): Sequential deterministic checks —
completeness, evidence, policy, provenance. Same input = same result.

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field

from app.core.inference.models.domain_types import HypothesisType, RejectionReason, ScopeParameters, TypedHypothesis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    rejection_reason: RejectionReason | None = None
    rejection_detail: str | None = None
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)


class TypedOutputValidator:
    def __init__(
        self,
        min_confidence: float = 0.5,
        min_findings: int = 1,
        min_reasoning_steps: int = 2,
        min_evidence_refs: int = 1,
    ) -> None:
        self._min_confidence = min_confidence
        self._min_findings = min_findings
        self._min_reasoning_steps = min_reasoning_steps
        self._min_evidence_refs = min_evidence_refs

    def validate(
        self, hypothesis: TypedHypothesis, requested_type: HypothesisType, scope: ScopeParameters
    ) -> ValidationResult:
        checks_passed: list[str] = []
        checks_failed: list[str] = []

        if hypothesis.is_executable:
            return ValidationResult(
                passed=False,
                rejection_reason=RejectionReason.OUTPUT_TYPE_VIOLATION,
                rejection_detail="CRITICAL: is_executable is True — architectural violation",
                checks_failed=["non_executable_check"],
            )
        checks_passed.append("non_executable_check")

        if hypothesis.hypothesis_type != requested_type:
            return ValidationResult(
                passed=False,
                rejection_reason=RejectionReason.SCHEMA_VIOLATION,
                rejection_detail=f"Type mismatch: requested={requested_type.value} received={hypothesis.hypothesis_type.value}",
                checks_passed=checks_passed,
                checks_failed=["hypothesis_type_check"],
            )
        checks_passed.append("hypothesis_type_check")

        if hypothesis.confidence_score < self._min_confidence:
            return ValidationResult(
                passed=False,
                rejection_reason=RejectionReason.CONFIDENCE_BELOW_THRESHOLD,
                rejection_detail=f"Confidence {hypothesis.confidence_score:.2f} below threshold {self._min_confidence:.2f}",
                checks_passed=checks_passed,
                checks_failed=["confidence_check"],
            )
        checks_passed.append("confidence_check")

        if hypothesis.scope_hash_used != scope.scope_hash:
            return ValidationResult(
                passed=False,
                rejection_reason=RejectionReason.PROVENANCE_INVALID,
                rejection_detail="Scope hash mismatch",
                checks_passed=checks_passed,
                checks_failed=["scope_hash_check"],
            )
        checks_passed.append("scope_hash_check")

        approved_ids = set(scope.allowed_control_object_ids)
        out_of_scope = [
            oid for oid in hypothesis.affected_control_object_ids if oid not in approved_ids
        ]
        if out_of_scope:
            return ValidationResult(
                passed=False,
                rejection_reason=RejectionReason.SCOPE_VIOLATION,
                rejection_detail=f"References {len(out_of_scope)} out-of-scope objects",
                checks_passed=checks_passed,
                checks_failed=["scope_object_check"],
            )
        checks_passed.append("scope_object_check")

        if len(hypothesis.findings) < self._min_findings:
            return ValidationResult(
                passed=False,
                rejection_reason=RejectionReason.EVIDENCE_INSUFFICIENT,
                rejection_detail=f"Only {len(hypothesis.findings)} findings, need {self._min_findings}",
                checks_passed=checks_passed,
                checks_failed=["findings_check"],
            )
        checks_passed.append("findings_check")

        if len(hypothesis.evidence_references) < self._min_evidence_refs:
            return ValidationResult(
                passed=False,
                rejection_reason=RejectionReason.EVIDENCE_INSUFFICIENT,
                rejection_detail=f"Only {len(hypothesis.evidence_references)} evidence refs",
                checks_passed=checks_passed,
                checks_failed=["evidence_check"],
            )
        checks_passed.append("evidence_check")

        if len(hypothesis.reasoning_trace) < self._min_reasoning_steps:
            return ValidationResult(
                passed=False,
                rejection_reason=RejectionReason.EVIDENCE_INSUFFICIENT,
                rejection_detail=f"Only {len(hypothesis.reasoning_trace)} reasoning steps",
                checks_passed=checks_passed,
                checks_failed=["reasoning_check"],
            )
        checks_passed.append("reasoning_check")

        return ValidationResult(passed=True, checks_passed=checks_passed)
