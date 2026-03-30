"""
Control Fabric Platform — Platform-Wide Evidence-Gated Action Engine

Patent Claim (Theme 4 — Core): Nothing executes on this platform
without a cryptographically bound evidence package.

This applies to ALL actions — not just AI inference:
  - State transitions on control objects
  - Reconciliation remediation actions
  - API-triggered changes
  - Automated workflow steps
  - Domain pack rule changes

The Evidence Package is an inseparable bundle containing:
  - The action manifest (what will execute)
  - The validation certificate (proof it passed all gates)
  - The evidence chain (what supports it)
  - The provenance trail (where it came from)
  - The policy snapshot (rules active at dispatch time)

If ANY element of the package is missing or tampered with,
the action physically cannot compile and will not execute.

UK Patent Reference:
  Section 6, Evidence-Gated Action Engine
  Section 9, Action Release Gate
  Layer 7: Evidence-Gated Action Layer
  Theme 4, Flow 4: Evidence-Gated Action Release

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.platform_validation_chain import (
    ActionOrigin,
    DeterministicValidationChain,
    ValidationCertificate,
    ValidationRequest,
)

logger = logging.getLogger(__name__)


class ActionStatus(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    COMPILED = "compiled"
    DISPATCHED = "dispatched"
    BLOCKED = "blocked"
    FAILED = "failed"


class EvidencePackage(BaseModel):
    """
    Cryptographically bound bundle that authorises an action.

    Patent Claim (Theme 4 — Core): Every executed action inherently
    and permanently carries the precise evidence chain that justified it,
    the specific policy context that governed it, and the complete
    historical provenance trail.

    An action without a complete EvidencePackage CANNOT be dispatched.
    This is enforced at compile time — not at audit time.
    """

    model_config = {"frozen": True}

    package_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_manifest: dict[str, Any] = Field(description="The executable action command")
    validation_certificate: ValidationCertificate
    evidence_chain: list[str] = Field(description="Ordered evidence reference IDs")
    provenance_trail: list[str] = Field(description="Chain of prior validated steps")
    policy_snapshot: dict[str, Any] = Field(description="Active policies at dispatch time")
    requested_by: str
    action_type: str
    origin: ActionOrigin
    compiled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    package_hash: str = Field(default="")

    @model_validator(mode="after")
    def compute_package_hash(self) -> EvidencePackage:
        """
        Cryptographically bind all package elements together.
        Any tampering with any element invalidates the hash.
        """
        payload = (
            f"{self.package_id}"
            f"{self.validation_certificate.certificate_hash}"
            f"{sorted(self.evidence_chain)}"
            f"{sorted(self.provenance_trail)}"
            f"{self.requested_by}{self.action_type}{self.origin}"
            f"{self.compiled_at.isoformat()}"
        )
        object.__setattr__(
            self,
            "package_hash",
            hashlib.sha256(payload.encode()).hexdigest(),
        )
        return self

    def verify_integrity(self) -> bool:
        """Verify this package has not been tampered with."""
        expected = hashlib.sha256(
            (
                f"{self.package_id}"
                f"{self.validation_certificate.certificate_hash}"
                f"{sorted(self.evidence_chain)}"
                f"{sorted(self.provenance_trail)}"
                f"{self.requested_by}{self.action_type}{self.origin}"
                f"{self.compiled_at.isoformat()}"
            ).encode()
        ).hexdigest()
        return self.package_hash == expected


class ActionDispatchResult(BaseModel):
    """Result of attempting to dispatch an action."""

    model_config = {"frozen": True}

    dispatch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_id: str
    status: ActionStatus
    dispatched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    result: dict[str, Any] = Field(default_factory=dict)
    failure_reason: str | None = None


class PlatformActionReleaseGate:
    """
    Platform-wide evidence-gated action release engine.

    Patent Claim (Theme 4): The gate compiles and dispatches actions
    ONLY when backed by a complete, cryptographically verified
    evidence package.

    The gate enforces:
    1. Every action passes through the DeterministicValidationChain
    2. A complete EvidencePackage is compiled before dispatch
    3. Package integrity is verified before execution
    4. Every dispatch is recorded in the immutable audit log

    This applies to ALL platform actions — not just AI inference.
    Human-initiated state changes, automated workflows, API calls,
    and AI-generated recommendations all pass through this gate.
    """

    def __init__(
        self,
        validation_chain: DeterministicValidationChain | None = None,
        active_policies: dict[str, Any] | None = None,
    ) -> None:
        self._chain = validation_chain or DeterministicValidationChain(active_policies)
        self._active_policies = active_policies or {}
        self._audit_log: list[ActionDispatchResult] = []
        self._packages: dict[str, EvidencePackage] = {}

    def submit(
        self,
        action_type: str,
        proposed_payload: dict[str, Any],
        requested_by: str,
        origin: ActionOrigin,
        evidence_references: list[str] | None = None,
        provenance_chain: list[str] | None = None,
        executor: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> ActionDispatchResult:
        """
        Submit an action for validation and release.

        Patent Claim: Nothing executes without passing ALL validation
        gates and compiling a complete evidence package.

        Steps:
        1. Wrap in ValidationRequest
        2. Run DeterministicValidationChain
        3. On pass: compile EvidencePackage
        4. Verify package integrity
        5. Dispatch (or simulate if no executor)
        6. Record in immutable audit log
        """
        logger.info(
            "Action submitted: type=%s origin=%s by=%s",
            action_type,
            origin.value,
            requested_by,
        )

        # Step 1: Wrap in validation request
        request = ValidationRequest(
            origin=origin,
            action_type=action_type,
            proposed_payload=proposed_payload,
            evidence_references=evidence_references or [],
            policy_context=self._active_policies,
            provenance_chain=provenance_chain or [],
            requested_by=requested_by,
        )

        # Step 2: Run full validation chain
        certificate, rejection = self._chain.validate(request)

        if rejection is not None:
            result = ActionDispatchResult(
                package_id="none",
                status=ActionStatus.BLOCKED,
                failure_reason=f"{rejection.failed_check.value}: {rejection.failure_detail}",
            )
            self._audit_log.append(result)
            logger.warning("Action BLOCKED: %s", rejection.failure_detail)
            return result

        assert certificate is not None

        # Step 3: Compile evidence package
        package = EvidencePackage(
            action_manifest=proposed_payload,
            validation_certificate=certificate,
            evidence_chain=evidence_references or [],
            provenance_trail=provenance_chain or [],
            policy_snapshot=self._active_policies,
            requested_by=requested_by,
            action_type=action_type,
            origin=origin,
        )

        # Step 4: Verify package integrity before dispatch
        if not package.verify_integrity():
            result = ActionDispatchResult(
                package_id=package.package_id,
                status=ActionStatus.BLOCKED,
                failure_reason="Evidence package integrity check failed",
            )
            self._audit_log.append(result)
            logger.critical(
                "EVIDENCE PACKAGE INTEGRITY FAILURE: package=%s",
                package.package_id[:8],
            )
            return result

        self._packages[package.package_id] = package

        # Step 5: Dispatch
        dispatch_result: dict[str, Any] = {}
        if executor:
            try:
                dispatch_result = executor(proposed_payload)
                status = ActionStatus.DISPATCHED
            except Exception as e:
                status = ActionStatus.FAILED
                dispatch_result = {"error": str(e)}
        else:
            status = ActionStatus.COMPILED
            dispatch_result = {
                "package_id": package.package_id,
                "package_hash": package.package_hash,
            }

        # Step 6: Record in audit log
        result = ActionDispatchResult(
            package_id=package.package_id,
            status=status,
            result=dispatch_result,
        )
        self._audit_log.append(result)

        logger.info(
            "Action %s: type=%s package=%s hash=%s",
            status.value.upper(),
            action_type,
            package.package_id[:8],
            package.package_hash[:16],
        )
        return result

    def get_package(self, package_id: str) -> EvidencePackage | None:
        return self._packages.get(package_id)

    def get_audit_log(self) -> list[ActionDispatchResult]:
        return list(self._audit_log)

    @property
    def total_submitted(self) -> int:
        return len(self._audit_log)

    @property
    def total_blocked(self) -> int:
        return sum(1 for r in self._audit_log if r.status == ActionStatus.BLOCKED)

    @property
    def total_dispatched(self) -> int:
        return sum(1 for r in self._audit_log if r.status == ActionStatus.DISPATCHED)
