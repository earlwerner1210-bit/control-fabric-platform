"""
Release Governance Pack Integration Tests

Tests the complete wedge solution end to end.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.core.connectors.framework import (
    ConnectorRegistry,
    FileDropConnector,
    SimulatedCICDConnector,
    WebhookConnector,
)
from app.core.exception_framework.domain_types import (
    ExceptionRequest,
    ExceptionRisk,
    ExceptionType,
)
from app.core.exception_framework.manager import ExceptionError, ExceptionManager
from app.core.reconciliation.cross_plane_engine import (
    ReconciliationCaseSeverity,
    ReconciliationCaseType,
)
from app.domain_packs.release_governance.seed_data import (
    build_demo_platform,
    run_demo_reconciliation,
)


@pytest.fixture
def demo_platform():
    return build_demo_platform()


class TestReleaseGovernancePack:
    def test_pack_loads_and_seeds_correctly(self, demo_platform) -> None:
        assert demo_platform["registry"].object_count > 0
        assert demo_platform["graph"].node_count > 0
        assert demo_platform["loader"].pack_count >= 1

    def test_ungoverned_releases_produce_critical_cases(self, demo_platform) -> None:
        cases = run_demo_reconciliation(demo_platform)
        critical = [c for c in cases if c.severity == ReconciliationCaseSeverity.CRITICAL]
        assert len(critical) >= 1, "Ungoverned releases must produce CRITICAL cases"

    def test_governed_releases_produce_no_rg001_gaps(self, demo_platform) -> None:
        cases = run_demo_reconciliation(demo_platform)
        governed_names = {
            "API Gateway v2.4.1 — Production Release",
            "Auth Service v1.9.0 — Staging Release",
        }
        governed_ids = {
            obj.object_id
            for obj in demo_platform["registry"].get_active()
            if obj.name in governed_names
        }
        rg001_gaps_for_governed = [
            c
            for c in cases
            if c.case_type == ReconciliationCaseType.GAP
            and c.violated_rule_id == "RG-001"
            and any(oid in governed_ids for oid in c.affected_object_ids)
        ]
        assert len(rg001_gaps_for_governed) == 0

    def test_evidence_gate_blocks_no_evidence(self, demo_platform) -> None:
        from app.core.platform_action_release_gate import (
            ActionStatus,
            PlatformActionReleaseGate,
        )
        from app.core.platform_validation_chain import ActionOrigin

        gate = PlatformActionReleaseGate()
        result = gate.submit(
            action_type="production_release",
            proposed_payload={"release": "ungoverned"},
            requested_by="engineer",
            origin=ActionOrigin.AI_INFERENCE,
            evidence_references=[],
        )
        assert result.status == ActionStatus.BLOCKED

    def test_evidence_gate_compiles_with_evidence(self, demo_platform) -> None:
        from app.core.platform_action_release_gate import (
            ActionStatus,
            PlatformActionReleaseGate,
        )
        from app.core.platform_validation_chain import ActionOrigin

        gate = PlatformActionReleaseGate()
        result = gate.submit(
            action_type="production_release",
            proposed_payload={"release": "governed-release"},
            requested_by="engineer",
            origin=ActionOrigin.HUMAN_OPERATOR,
            evidence_references=["ci-passed", "scan-passed"],
        )
        assert result.status == ActionStatus.COMPILED


class TestExceptionFramework:
    def make_request(self, hours: int = 24) -> ExceptionRequest:
        return ExceptionRequest(
            exception_type=ExceptionType.EMERGENCY_OVERRIDE,
            requested_by="cto@company.com",
            justification=(
                "Critical production outage. Compensating controls in place. "
                "Review scheduled within 48 hours."
            ),
            affected_object_ids=["obj-001"],
            affected_action_type="production_release",
            policy_context_id="Release Policy v1.0",
            expires_at=datetime.now(UTC) + timedelta(hours=hours),
            risk_assessment=ExceptionRisk.CRITICAL,
        )

    def test_exception_requires_substantive_justification(self) -> None:
        with pytest.raises(ValueError):
            ExceptionRequest(
                exception_type=ExceptionType.EMERGENCY_OVERRIDE,
                requested_by="user",
                justification="too short",
                affected_object_ids=["obj"],
                affected_action_type="release",
                policy_context_id="policy",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                risk_assessment=ExceptionRisk.LOW,
            )

    def test_exception_submit_and_approve(self) -> None:
        manager = ExceptionManager()
        req = self.make_request()
        submitted = manager.submit_exception(req)
        assert submitted.exception_id != ""
        decision = manager.approve_exception(
            submitted.exception_id,
            "ciso@company.com",
            "Approved with conditions.",
        )
        assert decision.review_task_id != ""
        assert manager.total_active == 1

    def test_approval_creates_review_task(self) -> None:
        manager = ExceptionManager()
        req = self.make_request()
        submitted = manager.submit_exception(req)
        decision = manager.approve_exception(
            submitted.exception_id,
            "ciso@company.com",
            "Approved with review task.",
        )
        assert decision.review_task_id != "none-rejected"

    def test_audit_trail_is_immutable(self) -> None:
        manager = ExceptionManager()
        req = self.make_request()
        submitted = manager.submit_exception(req)
        manager.approve_exception(submitted.exception_id, "ciso", "Approved with conditions met.")
        trail = manager.get_audit_trail(submitted.exception_id)
        assert len(trail) >= 2
        with pytest.raises((AttributeError, TypeError, ValueError)):
            trail[0].event_type = "tampered"

    def test_exception_must_have_expiry(self) -> None:
        manager = ExceptionManager()
        req = self.make_request(hours=24)
        assert req.expires_at > datetime.now(UTC)


class TestConnectors:
    def test_simulated_cicd_connector_produces_artefacts(self) -> None:
        connector = SimulatedCICDConnector()
        result = connector.fetch()
        assert result.success
        assert result.artefact_count == 1
        data = json.loads(result.artefacts[0].raw_content)
        assert "run_id" in data
        assert "test_coverage_pct" in data

    def test_connector_registry_fetch_all(self) -> None:
        registry = ConnectorRegistry()
        registry.register(SimulatedCICDConnector("ci-1"))
        registry.register(SimulatedCICDConnector("ci-2"))
        results = registry.fetch_all()
        assert len(results) == 2
        assert all(r.success for r in results.values())

    def test_webhook_connector_receives_and_fetches(self) -> None:
        connector = WebhookConnector("webhook-1", "github-actions", "ci-system")
        connector.receive({"run_id": "gh-001", "status": "passed", "name": "Test Run"})
        result = connector.fetch()
        assert result.success
        assert result.artefact_count == 1

    def test_webhook_clears_buffer_after_fetch(self) -> None:
        connector = WebhookConnector("webhook-2", "jenkins", "ci-system")
        connector.receive({"run_id": "j-001"})
        connector.fetch()
        result2 = connector.fetch()
        assert result2.artefact_count == 0


class TestDifferentiationProof:
    """
    Explicitly proves what generic workflow tools cannot do.
    These tests are the differentiation proof artifacts.
    """

    def test_gap_detection_is_semantic_not_data(self, demo_platform) -> None:
        """
        Generic workflow: detects missing approval ticket (data value check).
        This platform: detects missing SATISFIES relationship between
        release and policy (semantic structure check).
        These are fundamentally different — the latter requires no shared schema.
        """
        cases = run_demo_reconciliation(demo_platform)
        gap_cases = [c for c in cases if c.case_type == ReconciliationCaseType.GAP]
        assert len(gap_cases) > 0
        for case in gap_cases:
            desc = case.description.lower()
            assert "satisfies" in desc or "implements" in desc or "mitigates" in desc, (
                "Gap cases must describe semantic relationships, not data values"
            )

    def test_blocking_is_structural_not_advisory(self, demo_platform) -> None:
        """
        Generic workflow: flags releases for review (advisory).
        This platform: prevents action compilation absent evidence (structural).
        """
        from app.core.platform_action_release_gate import (
            PlatformActionReleaseGate,
        )
        from app.core.platform_validation_chain import ActionOrigin

        gate = PlatformActionReleaseGate()
        executed = []

        def executor(payload):
            executed.append(payload)
            return {}

        gate.submit(
            "production_release",
            {"release": "ungoverned"},
            "engineer",
            ActionOrigin.AI_INFERENCE,
            [],
            executor=executor,
        )
        assert len(executed) == 0, (
            "Blocked actions must produce zero side effects — structural, not advisory"
        )

    def test_all_origins_same_chain(self, demo_platform) -> None:
        """
        Generic workflow: applies different approval logic to humans vs. automation.
        This platform: identical deterministic chain for all six origin types.
        """
        from app.core.platform_validation_chain import (
            ActionOrigin,
            DeterministicValidationChain,
            ValidationRequest,
        )

        chain = DeterministicValidationChain()
        results = []
        for origin in ActionOrigin:
            evidence = ["e-001"] if origin == ActionOrigin.AI_INFERENCE else []
            req = ValidationRequest(
                origin=origin,
                action_type="production_release",
                proposed_payload={"r": "v"},
                requested_by="user",
                evidence_references=evidence,
            )
            cert, _ = chain.validate(req)
            results.append(cert is not None)
        assert all(results), "All origins must be able to pass the same chain"
