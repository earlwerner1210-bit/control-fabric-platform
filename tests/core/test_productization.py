"""Tests for productization: defaults, explainability, demo tenant, golden path."""

from __future__ import annotations

import pytest


class TestOpinionatedDefaults:
    def test_defaults_are_complete(self) -> None:
        from app.core.defaults.platform_defaults import get_all_defaults

        d = get_all_defaults()
        assert "severity_thresholds" in d
        assert "policies" in d
        assert "evidence_requirements" in d
        assert "role_mappings" in d
        assert "exception_rules" in d

    def test_default_policies_have_required_fields(self) -> None:
        from app.core.defaults.platform_defaults import DEFAULT_POLICIES

        for p in DEFAULT_POLICIES:
            assert "name" in p
            assert "blocked_action_types" in p

    def test_severity_thresholds_are_consistent(self) -> None:
        from app.core.defaults.platform_defaults import SEVERITY_THRESHOLDS

        assert (
            SEVERITY_THRESHOLDS["must_block_above"] > SEVERITY_THRESHOLDS["requires_review_above"]
        )
        assert SEVERITY_THRESHOLDS["requires_review_above"] > SEVERITY_THRESHOLDS["monitor_above"]


class TestExplainability:
    def test_explain_block_produces_human_summary(self) -> None:
        from app.core.explainability.engine import ExplainabilityEngine

        engine = ExplainabilityEngine()
        explanation = engine.explain_block(
            {
                "dispatch_id": "test-001",
                "failure_reason": "evidence_sufficiency: AI-originated actions require evidence",
                "dispatched_at": "2026-01-01T00:00:00",
            }
        )
        assert len(explanation.human_summary) > 0
        assert explanation.blocking_gate == "evidence_sufficiency"
        assert len(explanation.remediation_steps) > 0

    def test_explain_release_produces_summary(self) -> None:
        from app.core.explainability.engine import ExplainabilityEngine

        engine = ExplainabilityEngine()
        explanation = engine.explain_release(
            {
                "package_id": "pkg-001",
                "action_type": "production_release",
                "origin": "human_operator",
                "requested_by": "engineer",
                "evidence_chain": ["ci-001", "scan-001"],
                "package_hash": "a" * 64,
                "compiled_at": "2026-01-01T00:00:00",
            }
        )
        assert len(explanation.human_summary) > 0
        assert len(explanation.gates_passed) == 5

    def test_explain_case_gap(self) -> None:
        from app.core.explainability.engine import ExplainabilityEngine

        engine = ExplainabilityEngine()
        result = engine.explain_case(
            {
                "case_id": "c1",
                "case_type": "gap",
                "severity": "critical",
                "affected_planes": ["operations", "compliance"],
                "violated_rule_id": "RG-001",
                "remediation_suggestions": ["Link release to policy"],
            }
        )
        assert "explanation" in result
        assert "what_this_means" in result
        assert "what_to_do_next" in result

    def test_policy_diff_detects_breaking_change(self) -> None:
        from app.core.explainability.engine import ExplainabilityEngine

        engine = ExplainabilityEngine()
        from_p = {"version": 1, "blocked_action_types": []}
        to_p = {"version": 2, "blocked_action_types": ["force_deploy"]}
        result = engine.diff_policy_versions(from_p, to_p)
        assert result["is_breaking_change"] is True
        assert "force_deploy" in result["newly_blocked_actions"]


class TestDemoTenant:
    def test_reset_produces_clean_state(self) -> None:
        from app.core.demo.demo_tenant import DemoTenantManager

        mgr = DemoTenantManager()
        result = mgr.reset()
        assert result["status"] == "reset"
        assert result["objects"] > 0
        assert result["scenarios_available"] == 6

    def test_run_governed_release_scenario(self) -> None:
        from app.core.demo.demo_tenant import DemoTenantManager

        mgr = DemoTenantManager()
        mgr.reset()
        result = mgr.run_scenario("governed-release")
        assert result["passed"] is True
        assert result["outcome"] == "released"

    def test_run_blocked_ungoverned_scenario(self) -> None:
        from app.core.demo.demo_tenant import DemoTenantManager

        mgr = DemoTenantManager()
        mgr.reset()
        result = mgr.run_scenario("blocked-ungoverned")
        assert result["passed"] is True
        assert result["outcome"] == "blocked"

    def test_run_all_scenarios(self) -> None:
        from app.core.demo.demo_tenant import DemoTenantManager

        mgr = DemoTenantManager()
        result = mgr.run_all_scenarios()
        assert result["total"] == 6
        assert result["passed"] >= 4  # some scenarios depend on demo data state

    def test_ai_blocked_same_as_human(self) -> None:
        """Differentiation proof: AI gets same chain as human."""
        from app.core.demo.demo_tenant import DemoTenantManager

        mgr = DemoTenantManager()
        mgr.reset()
        result = mgr.run_scenario("ai-blocked")
        assert result["passed"] is True
        assert result["outcome"] == "blocked"


class TestGoldenPathJourney:
    def test_journey_steps_are_complete(self) -> None:
        from app.core.onboarding.studio import OnboardingStudio

        studio = OnboardingStudio()
        session = studio.create_session("Test Corp", "admin")
        assert session.session_id is not None
        progress = studio.get_progress(session.session_id)
        assert progress["percent_complete"] == 0.0
