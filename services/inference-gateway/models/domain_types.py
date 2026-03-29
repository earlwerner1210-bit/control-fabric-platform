"""
Control Fabric Platform — Bounded Inference Engine
Domain Types (Patent-Critical Data Structures)

These types implement the core patent claims:
  - TypedHypothesis: the ONLY output the AI can produce — never an executable command
  - PolicyGateResult: deterministic allow/deny before any inference
  - ScopeParameters: mathematical boundary on what data the model can see
  - EvidenceRecord: cryptographic provenance chain for every inference

UK Patent Claim Reference:
  Theme 3 — Bounded Reasoning with Deterministic Validation
  Theme 4 — Evidence-Gated Action Release Architecture

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class HypothesisType(str, Enum):
    REMEDIATION_SUGGESTION = "remediation_suggestion"
    GAP_ANALYSIS = "gap_analysis"
    CONFLICT_RESOLUTION = "conflict_resolution"
    RISK_ASSESSMENT = "risk_assessment"
    COMPLIANCE_MAPPING = "compliance_mapping"
    PATTERN_DETECTION = "pattern_detection"


class InferenceStatus(str, Enum):
    PENDING = "pending"
    POLICY_CHECKED = "policy_checked"
    SCOPE_BOUNDED = "scope_bounded"
    INFERRING = "inferring"
    VALIDATING = "validating"
    COMPLETE = "complete"
    REJECTED = "rejected"
    FAILED = "failed"


class RejectionReason(str, Enum):
    POLICY_DENIED = "policy_denied"
    SCOPE_VIOLATION = "scope_violation"
    OUTPUT_TYPE_VIOLATION = "output_type_violation"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    SCHEMA_VIOLATION = "schema_violation"
    CONFIDENCE_BELOW_THRESHOLD = "confidence_below_threshold"
    PROVENANCE_INVALID = "provenance_invalid"


class ScopeParameters(BaseModel):
    """
    Defines the exact boundary of what the model is permitted to see.
    Patent Claim: Dependent Claim 3.1
    """

    model_config = {"frozen": True}

    allowed_control_object_ids: list[str] = Field(
        description="Explicit whitelist of control object UUIDs"
    )
    allowed_operational_planes: list[str] = Field(description="Operational planes in scope")
    max_graph_depth: int = Field(default=2, ge=1, le=5)
    allowed_relationship_types: list[str] = Field(
        default_factory=lambda: ["mitigates", "satisfies", "implements"]
    )
    data_classification_ceiling: str = Field(default="internal")
    scope_hash: str = Field(default="")

    @model_validator(mode="after")
    def compute_scope_hash(self) -> ScopeParameters:
        payload = (
            f"{sorted(self.allowed_control_object_ids)}"
            f"{sorted(self.allowed_operational_planes)}"
            f"{self.max_graph_depth}"
            f"{sorted(self.allowed_relationship_types)}"
            f"{self.data_classification_ceiling}"
        )
        object.__setattr__(self, "scope_hash", hashlib.sha256(payload.encode()).hexdigest())
        return self


class PolicyGateResult(BaseModel):
    """
    Result of the pre-inference policy gate check.
    Patent Claim: Flow 3, Steps 2-3 — DETERMINISTIC.
    """

    model_config = {"frozen": True}

    decision: PolicyDecision
    policy_id: str
    policy_version: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    denial_reason: str | None = None
    scope_parameters: ScopeParameters | None = None
    gate_signature: str = Field(default="")

    @model_validator(mode="after")
    def validate_consistency(self) -> PolicyGateResult:
        if self.decision == PolicyDecision.ALLOW and self.scope_parameters is None:
            raise ValueError("ALLOW decision must include scope parameters")
        if self.decision == PolicyDecision.DENY and self.denial_reason is None:
            raise ValueError("DENY decision must include denial_reason")
        return self

    @model_validator(mode="after")
    def compute_signature(self) -> PolicyGateResult:
        payload = (
            f"{self.decision}{self.policy_id}{self.policy_version}{self.evaluated_at.isoformat()}"
        )
        object.__setattr__(self, "gate_signature", hashlib.sha256(payload.encode()).hexdigest())
        return self


class TypedHypothesis(BaseModel):
    """
    The ONLY structured output type the Bounded Reasoning Layer can produce.
    Patent Claim: AI cannot produce executable output — enforced structurally.
    """

    hypothesis_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hypothesis_type: HypothesisType
    title: str = Field(max_length=200)
    findings: list[str] = Field(min_length=1)
    affected_control_object_ids: list[str]
    confidence_score: float = Field(ge=0.0, le=1.0)
    evidence_references: list[str]
    reasoning_trace: list[str]
    scope_hash_used: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    model_id: str
    is_executable: bool = Field(default=False)
    hypothesis_hash: str = Field(default="")

    @field_validator("is_executable", mode="before")
    @classmethod
    def enforce_non_executable(cls, v: Any) -> bool:
        return False  # Always. No exceptions. Architectural guarantee.

    @model_validator(mode="after")
    def compute_hypothesis_hash(self) -> TypedHypothesis:
        payload = (
            f"{self.hypothesis_id}{self.hypothesis_type}"
            f"{self.title}{self.findings}"
            f"{self.affected_control_object_ids}"
            f"{self.confidence_score}{self.scope_hash_used}"
            f"{self.generated_at.isoformat()}{self.model_id}"
        )
        self.hypothesis_hash = hashlib.sha256(payload.encode()).hexdigest()
        return self


class EvidenceRecord(BaseModel):
    """
    Immutable provenance record for every inference lifecycle.
    Patent Claim: 100% traceability — Theme 4.
    """

    model_config = {"frozen": True}

    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    request_hash: str
    policy_gate_signature: str
    scope_hash: str
    hypothesis_hash: str | None = None
    model_id: str
    inference_duration_ms: int = Field(ge=0)
    final_status: InferenceStatus
    rejection_reason: RejectionReason | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    chain_hash: str = Field(default="")

    @model_validator(mode="after")
    def compute_chain_hash(self) -> EvidenceRecord:
        payload = (
            f"{self.record_id}{self.session_id}{self.request_hash}"
            f"{self.policy_gate_signature}{self.scope_hash}"
            f"{self.hypothesis_hash}{self.model_id}"
            f"{self.inference_duration_ms}{self.final_status}"
            f"{self.rejection_reason}{self.created_at.isoformat()}"
        )
        object.__setattr__(self, "chain_hash", hashlib.sha256(payload.encode()).hexdigest())
        return self


class InferenceRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requesting_entity_id: str
    target_control_object_ids: list[str] = Field(min_length=1)
    target_operational_plane: str
    hypothesis_type_requested: HypothesisType
    context_data: dict[str, Any] = Field(default_factory=dict)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_hash: str = Field(default="")

    @model_validator(mode="after")
    def compute_request_hash(self) -> InferenceRequest:
        payload = (
            f"{self.request_id}{self.requesting_entity_id}"
            f"{sorted(self.target_control_object_ids)}"
            f"{self.target_operational_plane}"
            f"{self.hypothesis_type_requested}"
            f"{self.requested_at.isoformat()}"
        )
        self.request_hash = hashlib.sha256(payload.encode()).hexdigest()
        return self


class InferenceResponse(BaseModel):
    session_id: str
    request_id: str
    status: InferenceStatus
    hypothesis: TypedHypothesis | None = None
    rejection_reason: RejectionReason | None = None
    rejection_detail: str | None = None
    evidence_record: EvidenceRecord | None = None
    policy_gate_result: PolicyGateResult | None = None
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
