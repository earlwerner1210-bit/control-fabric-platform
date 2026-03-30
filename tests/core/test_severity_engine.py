"""Comprehensive tests for all 5 new platform subsystems."""

from __future__ import annotations

import pytest

from app.core.onboarding import OnboardingSession, OnboardingStudio, StepOutcome, StepStatus
from app.core.pack_management import (
    PackInstallRequest,
    PackManifest,
    PackRegistry,
    PackStatus,
    PackVersion,
)
from app.core.policy_admin import PolicyDefinition, PolicyManager, PolicyStatus
from app.core.rbac import AccessController, Permission, Role
from app.core.severity import (
    OperatorUrgency,
    RouteCategory,
    ScoredCase,
    SeverityEngine,
    SeverityInput,
    SeverityWeight,
)

# ════════════════════════════════════════════════════════════
#  1. SEVERITY ENGINE
# ════════════════════════════════════════════════════════════


class TestSeverityScoring:
    def test_critical_case_scores_high(self):
        engine = SeverityEngine()
        inp = SeverityInput(
            case_id="C-001",
            case_type="MISSING_EVIDENCE",
            severity_raw="critical",
            financial_impact=500_000,
            affected_objects=50,
            rule_criticality="critical",
        )
        result = engine.score(inp)
        assert result.composite_score >= 60
        assert result.route == RouteCategory.MUST_BLOCK
        assert result.urgency == OperatorUrgency.IMMEDIATE

    def test_low_case_scores_low(self):
        engine = SeverityEngine()
        inp = SeverityInput(
            case_id="C-002",
            case_type="INFO",
            severity_raw="low",
            financial_impact=0,
            affected_objects=1,
            rule_criticality="low",
        )
        result = engine.score(inp)
        assert result.composite_score < 30
        assert result.route in (RouteCategory.MONITOR, RouteCategory.SUPPRESS)

    def test_batch_scoring_ranks_correctly(self):
        engine = SeverityEngine()
        inputs = [
            SeverityInput(case_id="C-low", case_type="A", severity_raw="low"),
            SeverityInput(
                case_id="C-high",
                case_type="B",
                severity_raw="critical",
                financial_impact=1_000_000,
                rule_criticality="critical",
            ),
        ]
        results = engine.score_batch(inputs)
        assert results[0].rank == 1
        assert results[0].case_id == "C-high"
        assert results[1].rank == 2

    def test_duplicate_suppression(self):
        engine = SeverityEngine()
        inputs = [
            SeverityInput(case_id="C-1", case_type="DRIFT", severity_raw="high", is_duplicate=True),
            SeverityInput(case_id="C-2", case_type="DRIFT", severity_raw="high", is_duplicate=True),
        ]
        results = engine.score_batch(inputs)
        suppressed = [r for r in results if r.route == RouteCategory.SUPPRESS]
        assert len(suppressed) >= 1

    def test_priority_queue_excludes_suppressed(self):
        engine = SeverityEngine()
        inputs = [
            SeverityInput(case_id="C-a", case_type="X", severity_raw="critical"),
            SeverityInput(case_id="C-b", case_type="X", severity_raw="low", is_duplicate=True),
            SeverityInput(case_id="C-c", case_type="X", severity_raw="low", is_duplicate=True),
        ]
        scored = engine.score_batch(inputs)
        queue = engine.get_priority_queue(scored)
        assert all(s.route != RouteCategory.SUPPRESS for s in queue)

    def test_custom_weights(self):
        weights = [
            SeverityWeight(dimension="severity_raw", weight=1.0),
            SeverityWeight(dimension="financial_impact", weight=0.0),
            SeverityWeight(dimension="affected_objects", weight=0.0),
            SeverityWeight(dimension="rule_criticality", weight=0.0),
        ]
        engine = SeverityEngine(weights=weights)
        inp = SeverityInput(case_id="C-w", case_type="T", severity_raw="critical")
        result = engine.score(inp)
        assert result.composite_score == 100.0

    def test_cluster_tracking(self):
        engine = SeverityEngine()
        engine.score(SeverityInput(case_id="C-1", case_type="A", cluster_id="cluster-1"))
        engine.score(SeverityInput(case_id="C-2", case_type="B", cluster_id="cluster-1"))
        assert len(engine.get_cluster("cluster-1")) == 2

    def test_scored_case_is_frozen(self):
        engine = SeverityEngine()
        result = engine.score(SeverityInput(case_id="C-f", case_type="T"))
        with pytest.raises(ValueError):
            result.composite_score = 999.0


# ════════════════════════════════════════════════════════════
#  2. ONBOARDING STUDIO
# ════════════════════════════════════════════════════════════


class TestOnboardingStudio:
    def test_create_session(self):
        studio = OnboardingStudio()
        session = studio.create_session("telco-billing", "admin@co.com")
        assert session.domain_name == "telco-billing"
        assert len(session.steps) == 7
        assert session.current_step == 0
        assert not session.completed

    def test_advance_through_all_steps(self):
        studio = OnboardingStudio()
        session = studio.create_session("test-domain", "user@co.com")
        for i in range(7):
            outcome = studio.advance_step(session.session_id)
            assert outcome.status == StepStatus.COMPLETED
        assert session.completed
        progress = studio.get_progress(session.session_id)
        assert progress["is_complete"] is True
        assert progress["percent_complete"] == 100.0

    def test_cannot_advance_completed_session(self):
        studio = OnboardingStudio()
        session = studio.create_session("done", "u@co.com")
        for _ in range(7):
            studio.advance_step(session.session_id)
        with pytest.raises(ValueError, match="already completed"):
            studio.advance_step(session.session_id)

    def test_fail_step(self):
        studio = OnboardingStudio()
        session = studio.create_session("fail-test", "u@co.com")
        outcome = studio.fail_step(session.session_id, "Schema validation failed")
        assert outcome.status == StepStatus.FAILED
        assert outcome.error == "Schema validation failed"

    def test_progress_tracking(self):
        studio = OnboardingStudio()
        session = studio.create_session("progress", "u@co.com")
        studio.advance_step(session.session_id)
        studio.advance_step(session.session_id)
        progress = studio.get_progress(session.session_id)
        assert progress["completed_steps"] == 2
        assert progress["total_steps"] == 7
        assert progress["percent_complete"] == pytest.approx(28.6, abs=0.1)

    def test_list_sessions(self):
        studio = OnboardingStudio()
        studio.create_session("d1", "u@co.com")
        studio.create_session("d2", "u@co.com")
        assert len(studio.list_sessions()) == 2


# ════════════════════════════════════════════════════════════
#  3. PACK MANAGEMENT
# ════════════════════════════════════════════════════════════


class TestPackManagement:
    def test_list_builtin_packs(self):
        registry = PackRegistry()
        packs = registry.list_packs()
        assert len(packs) >= 3
        ids = [p["pack_id"] for p in packs]
        assert "telco-ops" in ids
        assert "contract-margin" in ids
        assert "release-governance" in ids

    def test_install_and_uninstall(self):
        registry = PackRegistry()
        result = registry.install(PackInstallRequest(pack_id="telco-ops"))
        assert result["action"] == "install"
        assert registry.get_status("telco-ops") == PackStatus.INSTALLED

        result = registry.uninstall("telco-ops")
        assert result["action"] == "uninstall"
        assert registry.get_status("telco-ops") == PackStatus.AVAILABLE

    def test_cannot_reinstall_without_force(self):
        registry = PackRegistry()
        registry.install(PackInstallRequest(pack_id="telco-ops"))
        with pytest.raises(ValueError, match="already installed"):
            registry.install(PackInstallRequest(pack_id="telco-ops"))

    def test_force_reinstall(self):
        registry = PackRegistry()
        registry.install(PackInstallRequest(pack_id="telco-ops"))
        result = registry.install(PackInstallRequest(pack_id="telco-ops", force=True))
        assert result["action"] == "install"

    def test_version_compatibility(self):
        registry = PackRegistry()
        assert registry.check_compatibility("telco-ops", PackVersion(major=1, minor=5, patch=0))
        assert not registry.check_compatibility("telco-ops", PackVersion(major=2, minor=0, patch=0))

    def test_upgrade_compatible(self):
        registry = PackRegistry()
        registry.install(PackInstallRequest(pack_id="telco-ops"))
        new_manifest = PackManifest(
            pack_id="telco-ops",
            pack_name="Telco Operations",
            version=PackVersion(major=1, minor=1, patch=0),
            rule_count=7,
        )
        diff = registry.upgrade("telco-ops", new_manifest)
        assert diff.from_version == "1.0.0"
        assert diff.to_version == "1.1.0"
        assert not diff.breaking

    def test_upgrade_incompatible_raises(self):
        registry = PackRegistry()
        new_manifest = PackManifest(
            pack_id="telco-ops",
            pack_name="Telco Ops v2",
            version=PackVersion(major=2, minor=0, patch=0),
        )
        with pytest.raises(ValueError, match="Incompatible"):
            registry.upgrade("telco-ops", new_manifest)

    def test_install_log(self):
        registry = PackRegistry()
        registry.install(PackInstallRequest(pack_id="telco-ops"))
        log = registry.get_install_log()
        assert len(log) == 1
        assert log[0]["pack_id"] == "telco-ops"


# ════════════════════════════════════════════════════════════
#  4. POLICY ADMINISTRATION
# ════════════════════════════════════════════════════════════


class TestPolicyAdmin:
    def test_full_lifecycle(self):
        mgr = PolicyManager()
        policy = mgr.create_draft("Test Policy", rules=["R-001"], target_packs=["telco-ops"])
        assert policy.status == PolicyStatus.DRAFT

        sim = mgr.simulate(policy.policy_id)
        assert sim.cases_evaluated > 0

        published = mgr.publish(policy.policy_id)
        assert published.status == PolicyStatus.PUBLISHED
        assert published.published_at is not None

        rolled = mgr.rollback(policy.policy_id)
        assert rolled.status == PolicyStatus.ROLLED_BACK

        archived = mgr.archive(policy.policy_id)
        assert archived.status == PolicyStatus.ARCHIVED

    def test_conflict_detection_blocks_publish(self):
        mgr = PolicyManager()
        p1 = mgr.create_draft("Policy A", rules=["R-001"], target_packs=["telco-ops"])
        mgr.publish(p1.policy_id)

        p2 = mgr.create_draft("Policy B", rules=["R-001"], target_packs=["telco-ops"])
        with pytest.raises(ValueError, match="conflict"):
            mgr.publish(p2.policy_id)

    def test_cannot_publish_non_draft(self):
        mgr = PolicyManager()
        policy = mgr.create_draft("P", rules=["R-1"])
        mgr.publish(policy.policy_id)
        with pytest.raises(ValueError, match="draft"):
            mgr.publish(policy.policy_id)

    def test_cannot_rollback_non_published(self):
        mgr = PolicyManager()
        policy = mgr.create_draft("P")
        with pytest.raises(ValueError, match="published"):
            mgr.rollback(policy.policy_id)

    def test_cannot_archive_published(self):
        mgr = PolicyManager()
        policy = mgr.create_draft("P")
        mgr.publish(policy.policy_id)
        with pytest.raises(ValueError, match="rollback"):
            mgr.archive(policy.policy_id)

    def test_list_policies_by_status(self):
        mgr = PolicyManager()
        mgr.create_draft("Draft 1")
        mgr.create_draft("Draft 2")
        p3 = mgr.create_draft("To Publish")
        mgr.publish(p3.policy_id)
        assert len(mgr.list_policies(PolicyStatus.DRAFT)) == 2
        assert len(mgr.list_policies(PolicyStatus.PUBLISHED)) == 1

    def test_history_tracking(self):
        mgr = PolicyManager()
        p = mgr.create_draft("H")
        mgr.simulate(p.policy_id)
        mgr.publish(p.policy_id)
        history = mgr.get_history()
        actions = [h["action"] for h in history]
        assert "create_draft" in actions
        assert "simulate" in actions
        assert "publish" in actions


# ════════════════════════════════════════════════════════════
#  5. RBAC
# ════════════════════════════════════════════════════════════


class TestRBAC:
    def test_admin_has_all_permissions(self):
        ac = AccessController()
        ac.assign_role("admin-1", Role.PLATFORM_ADMIN)
        decision = ac.check_permission("admin-1", Permission.ADMIN_USERS)
        assert decision.granted

    def test_viewer_cannot_write(self):
        ac = AccessController()
        ac.assign_role("viewer-1", Role.VIEWER)
        decision = ac.check_permission("viewer-1", Permission.OBJECT_WRITE)
        assert not decision.granted

    def test_operator_can_read_cases(self):
        ac = AccessController()
        ac.assign_role("op-1", Role.OPERATOR)
        decision = ac.check_permission("op-1", Permission.CASE_READ)
        assert decision.granted

    def test_domain_restriction(self):
        ac = AccessController()
        ac.assign_role("owner-1", Role.DOMAIN_OWNER, domain_restriction="telco-ops")
        granted = ac.check_permission("owner-1", Permission.OBJECT_WRITE, domain="telco-ops")
        assert granted.granted
        denied = ac.check_permission("owner-1", Permission.OBJECT_WRITE, domain="contract-margin")
        assert not denied.granted

    def test_revoke_role(self):
        ac = AccessController()
        ac.assign_role("u-1", Role.OPERATOR)
        assert ac.revoke_role("u-1", Role.OPERATOR)
        assert not ac.revoke_role("u-1", Role.OPERATOR)

    def test_audit_log(self):
        ac = AccessController()
        ac.assign_role("u-1", Role.VIEWER)
        ac.check_permission("u-1", Permission.OBJECT_READ)
        ac.check_permission("u-1", Permission.OBJECT_WRITE)
        log = ac.get_audit_log("u-1")
        assert len(log) == 2
        assert log[0].granted
        assert not log[1].granted

    def test_permission_matrix(self):
        ac = AccessController()
        matrix = ac.get_permission_matrix()
        assert "platform_admin" in matrix
        assert len(matrix["platform_admin"]) == len(Permission)

    def test_check_any_permission(self):
        ac = AccessController()
        ac.assign_role("u-1", Role.VIEWER)
        decision = ac.check_any_permission("u-1", [Permission.OBJECT_WRITE, Permission.OBJECT_READ])
        assert decision.granted
        assert decision.permission == Permission.OBJECT_READ

    def test_multiple_roles(self):
        ac = AccessController()
        ac.assign_role("u-1", Role.VIEWER)
        ac.assign_role("u-1", Role.POLICY_AUTHOR)
        decision = ac.check_permission("u-1", Permission.POLICY_WRITE)
        assert decision.granted
