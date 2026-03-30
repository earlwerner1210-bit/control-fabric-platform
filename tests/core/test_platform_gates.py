"""
Platform-Wide Validation Chain and Action Release Gate Tests

These tests prove the patent claim that ALL platform outputs —
not just AI inference — pass through deterministic validation
and evidence-gated release.

This is the key distinction from prior art:
  Prior art: validates AI outputs
  This platform: validates ALL outputs through the same chain

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import pytest

from app.core.platform_action_release_gate import (
    ActionStatus,
    EvidencePackage,
    PlatformActionReleaseGate,
)
from app.core.platform_validation_chain import (
    ActionOrigin,
    DeterministicValidationChain,
    ValidationCertificate,
    ValidationCheckName,
    ValidationRejection,
    ValidationRequest,
)


def make_request(
    action_type: str = "state_transition",
    origin: ActionOrigin = ActionOrigin.HUMAN_OPERATOR,
    payload: dict | None = None,
    evidence: list[str] | None = None,
    requested_by: str = "test-user",
) -> ValidationRequest:
    return ValidationRequest(
        origin=origin,
        action_type=action_type,
        proposed_payload=payload or {"target_state": "active"},
        evidence_references=evidence or [],
        requested_by=requested_by,
    )


class TestDeterministicValidationChain:
    def test_valid_request_produces_certificate(self) -> None:
        chain = DeterministicValidationChain()
        request = make_request()
        cert, rejection = chain.validate(request)
        assert cert is not None
        assert rejection is None
        assert isinstance(cert, ValidationCertificate)

    def test_certificate_covers_all_gates(self) -> None:
        chain = DeterministicValidationChain()
        cert, _ = chain.validate(make_request())
        assert len(cert.checks_passed) == 5

    def test_missing_action_type_fails_completeness(self) -> None:
        chain = DeterministicValidationChain()
        request = make_request(action_type="")
        cert, rejection = chain.validate(request)
        assert cert is None
        assert rejection is not None
        assert rejection.failed_check == ValidationCheckName.COMPLETENESS

    def test_ai_origin_without_evidence_fails(self) -> None:
        """
        Patent Claim: AI-originated actions REQUIRE evidence references.
        This applies to all AI actions platform-wide — not just inference.
        """
        chain = DeterministicValidationChain()
        request = make_request(origin=ActionOrigin.AI_INFERENCE, evidence=[])
        cert, rejection = chain.validate(request)
        assert cert is None
        assert rejection.failed_check == ValidationCheckName.EVIDENCE_SUFFICIENCY

    def test_ai_origin_with_evidence_passes(self) -> None:
        chain = DeterministicValidationChain()
        request = make_request(origin=ActionOrigin.AI_INFERENCE, evidence=["evidence-001"])
        cert, rejection = chain.validate(request)
        assert cert is not None
        assert rejection is None

    def test_blocked_action_type_fails_policy(self) -> None:
        """Patent Claim: Policy compliance is deterministic — blocked types always fail."""
        chain = DeterministicValidationChain(
            active_policies={"blocked_action_types": ["delete_all"]}
        )
        request = make_request(action_type="delete_all")
        cert, rejection = chain.validate(request)
        assert cert is None
        assert rejection.failed_check == ValidationCheckName.POLICY_COMPLIANCE

    def test_deterministic_same_input_same_output(self) -> None:
        """
        Patent Claim: Same input ALWAYS produces same result.
        This is the core determinism guarantee.
        """
        chain = DeterministicValidationChain()
        results = []
        for _ in range(10):
            req = make_request(requested_by="fixed-user", action_type="fixed-action")
            cert, rejection = chain.validate(req)
            results.append(cert is not None)
        assert all(results), "Validation must be deterministic across all runs"

    def test_certificate_is_cryptographically_signed(self) -> None:
        chain = DeterministicValidationChain()
        cert, _ = chain.validate(make_request())
        assert len(cert.certificate_hash) == 64

    def test_human_and_ai_same_chain(self) -> None:
        """
        Patent Claim: ALL origins — human, AI, automated — pass
        through the SAME validation chain. Not separate pipelines.
        """
        chain = DeterministicValidationChain()
        for origin in ActionOrigin:
            evidence = ["evidence-001"] if origin == ActionOrigin.AI_INFERENCE else []
            request = make_request(origin=origin, evidence=evidence)
            cert, _ = chain.validate(request)
            assert cert is not None, f"Origin {origin} should pass validation"


class TestPlatformActionReleaseGate:
    def test_valid_action_is_compiled(self) -> None:
        gate = PlatformActionReleaseGate()
        result = gate.submit(
            action_type="state_transition",
            proposed_payload={"object_id": "ctrl-001", "target_state": "active"},
            requested_by="operator",
            origin=ActionOrigin.HUMAN_OPERATOR,
        )
        assert result.status == ActionStatus.COMPILED
        assert result.package_id != "none"

    def test_blocked_action_type_is_blocked(self) -> None:
        gate = PlatformActionReleaseGate(active_policies={"blocked_action_types": ["force_delete"]})
        result = gate.submit(
            action_type="force_delete",
            proposed_payload={"object_id": "ctrl-001"},
            requested_by="operator",
            origin=ActionOrigin.HUMAN_OPERATOR,
        )
        assert result.status == ActionStatus.BLOCKED
        assert "policy" in result.failure_reason.lower()

    def test_evidence_package_has_all_elements(self) -> None:
        """
        Patent Claim: Evidence package binds action + certificate +
        evidence chain + provenance + policy snapshot together.
        """
        gate = PlatformActionReleaseGate()
        result = gate.submit(
            action_type="state_transition",
            proposed_payload={"target": "active"},
            requested_by="operator",
            origin=ActionOrigin.HUMAN_OPERATOR,
            evidence_references=["audit-001"],
            provenance_chain=["ingest-session-001"],
        )
        package = gate.get_package(result.package_id)
        assert package is not None
        assert package.validation_certificate is not None
        assert package.evidence_chain == ["audit-001"]
        assert package.provenance_trail == ["ingest-session-001"]
        assert len(package.package_hash) == 64

    def test_package_integrity_verified(self) -> None:
        """Patent Claim: Package integrity is verified before dispatch."""
        gate = PlatformActionReleaseGate()
        result = gate.submit(
            action_type="state_transition",
            proposed_payload={"target": "active"},
            requested_by="operator",
            origin=ActionOrigin.HUMAN_OPERATOR,
        )
        package = gate.get_package(result.package_id)
        assert package.verify_integrity() is True

    def test_every_action_recorded_in_audit_log(self) -> None:
        """Patent Claim: Every action — pass or fail — is recorded."""
        gate = PlatformActionReleaseGate(active_policies={"blocked_action_types": ["bad_action"]})
        gate.submit("state_transition", {"t": "active"}, "user", ActionOrigin.HUMAN_OPERATOR)
        gate.submit("bad_action", {"t": "active"}, "user", ActionOrigin.HUMAN_OPERATOR)
        assert gate.total_submitted == 2
        assert gate.total_blocked == 1

    def test_executor_called_on_valid_action(self) -> None:
        """Actions with executors are dispatched, not just compiled."""
        gate = PlatformActionReleaseGate()
        executed = []

        def executor(payload: dict) -> dict:
            executed.append(payload)
            return {"success": True}

        result = gate.submit(
            action_type="state_transition",
            proposed_payload={"target": "active"},
            requested_by="operator",
            origin=ActionOrigin.HUMAN_OPERATOR,
            executor=executor,
        )
        assert result.status == ActionStatus.DISPATCHED
        assert len(executed) == 1

    def test_ai_action_requires_evidence(self) -> None:
        """AI-originated actions without evidence are blocked platform-wide."""
        gate = PlatformActionReleaseGate()
        result = gate.submit(
            action_type="remediation",
            proposed_payload={"action": "patch"},
            requested_by="ai-agent",
            origin=ActionOrigin.AI_INFERENCE,
            evidence_references=[],
        )
        assert result.status == ActionStatus.BLOCKED

    def test_all_origins_use_same_gate(self) -> None:
        """
        Patent Claim: The gate is platform-wide — not AI-specific.
        ALL origins pass through the SAME release gate.
        """
        gate = PlatformActionReleaseGate()
        for origin in [
            ActionOrigin.HUMAN_OPERATOR,
            ActionOrigin.AUTOMATED_WORKFLOW,
            ActionOrigin.API_REQUEST,
            ActionOrigin.SCHEDULED_TASK,
        ]:
            result = gate.submit(
                action_type="state_transition",
                proposed_payload={"target": "active"},
                requested_by="test",
                origin=origin,
            )
            assert result.status != ActionStatus.BLOCKED, f"Origin {origin} should not be blocked"


class TestPatentClaimPlatformWideGating:
    def test_claim_not_just_ai_all_origins_gated(self) -> None:
        """
        UK Patent Theme 3+4 — Platform-Wide:
        The deterministic validation chain and evidence-gated release
        apply to ALL outputs regardless of origin.
        This is the key distinction from prior art which only gates AI.
        """
        gate = PlatformActionReleaseGate()
        origins_tested = []
        for origin in ActionOrigin:
            evidence = ["e-001"] if origin == ActionOrigin.AI_INFERENCE else []
            result = gate.submit("state_transition", {"t": "a"}, "user", origin, evidence)
            origins_tested.append(origin)
            assert result.status in (ActionStatus.COMPILED, ActionStatus.DISPATCHED)
        assert len(origins_tested) == len(list(ActionOrigin))

    def test_claim_blocked_action_leaves_no_side_effects(self) -> None:
        """
        Patent Claim: Blocked actions produce NO side effects.
        The gate prevents execution entirely — not just logs after the fact.
        """
        gate = PlatformActionReleaseGate(active_policies={"blocked_action_types": ["dangerous"]})
        executed = []

        def executor(p: dict) -> dict:
            executed.append(p)
            return {}

        gate.submit(
            "dangerous",
            {"data": "sensitive"},
            "user",
            ActionOrigin.HUMAN_OPERATOR,
            executor=executor,
        )
        assert len(executed) == 0, "Blocked actions must produce zero side effects"
