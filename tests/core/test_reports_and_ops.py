"""Tests for bulk case operations, reports, and explainability integration."""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.routes.case_ops_route import (
    BulkAssignBody,
    BulkResolveBody,
    BulkSuppressBody,
    bulk_assign,
    bulk_resolve,
    bulk_suppress,
    get_aging,
    get_case_stats,
    get_workload,
)
from app.api.routes.reports_route import get_report, get_report_summary
from app.core.explainability.engine import ExplainabilityEngine


class TestBulkAssign:
    def test_assign_multiple_cases(self):
        body = BulkAssignBody(case_ids=["c1", "c2", "c3"], assigned_to="operator@acme.com")
        result = bulk_assign(body)
        assert result["operation"] == "bulk_assign"
        assert result["requested"] == 3
        assert result["succeeded"] == 3
        assert result["failed"] == 0
        assert len(result["results"]) == 3
        assert all(r["assigned_to"] == "operator@acme.com" for r in result["results"])

    def test_assign_empty_list(self):
        body = BulkAssignBody(case_ids=[], assigned_to="op@acme.com")
        result = bulk_assign(body)
        assert result["requested"] == 0
        assert result["succeeded"] == 0


class TestBulkResolve:
    def test_resolve_returns_structure(self):
        body = BulkResolveBody(
            case_ids=["nonexistent-1"],
            resolved_by="admin@acme.com",
            resolution_note="Resolved in bulk test",
        )
        result = bulk_resolve(body)
        assert result["operation"] == "bulk_resolve"
        assert result["requested"] == 1


class TestBulkSuppress:
    def test_suppress_cases(self):
        body = BulkSuppressBody(
            case_ids=["c1", "c2"],
            suppressed_by="ciso@acme.com",
            reason="Accepted risk per review",
        )
        result = bulk_suppress(body)
        assert result["operation"] == "bulk_suppress"
        assert result["succeeded"] == 2
        assert all(r["status"] == "suppressed" for r in result["results"])


class TestCaseWorkload:
    def test_workload_structure(self):
        result = get_workload()
        assert "total_open" in result
        assert "by_severity" in result
        assert "unassigned" in result


class TestCaseAging:
    def test_aging_buckets(self):
        result = get_aging()
        assert "buckets" in result
        assert len(result["buckets"]) == 4
        for bucket in result["buckets"]:
            assert "label" in bucket
            assert "count" in bucket
            assert "oldest_hours" in bucket


class TestCaseStats:
    def test_stats_structure(self):
        result = get_case_stats()
        assert "total" in result
        assert "by_type" in result
        assert "by_severity" in result


class TestReportSummary:
    def test_summary_lists_all_reports(self):
        result = get_report_summary()
        assert "available_reports" in result
        assert len(result["available_reports"]) == 6
        ids = [r["report_id"] for r in result["available_reports"]]
        assert "governance-posture" in ids
        assert "release-gate-activity" in ids


class TestReportGeneration:
    def test_governance_posture_report(self):
        result = get_report("governance-posture", "30d")
        assert result["report_id"] == "governance-posture"
        assert result["window"] == "30d"
        assert "data" in result
        assert "coverage_pct" in result["data"]

    def test_release_gate_report_7d(self):
        result = get_report("release-gate-activity", "7d")
        assert result["data"]["total_submissions"] == 28

    def test_report_90d_window(self):
        result = get_report("reconciliation-trend", "90d")
        assert result["window"] == "90d"
        assert result["data"]["total_cases_detected"] == 180

    def test_unknown_report(self):
        result = get_report("nonexistent", "30d")
        assert "error" in result

    def test_all_reports_generate(self):
        for report_id in [
            "governance-posture",
            "release-gate-activity",
            "evidence-completeness",
            "exception-history",
            "reconciliation-trend",
            "policy-compliance",
        ]:
            result = get_report(report_id, "30d")
            assert result["report_id"] == report_id
            assert "data" in result


class TestExplainabilityIntegration:
    def test_explain_block_full_flow(self):
        engine = ExplainabilityEngine()
        audit = {
            "dispatch_id": "test-001",
            "action_type": "production_release",
            "origin": "ai_inference",
            "requested_by": "ai-agent",
            "dispatched_at": datetime.now(UTC).isoformat(),
            "failure_reason": "evidence_sufficiency: No evidence references provided",
        }
        explanation = engine.explain_block(audit)
        assert explanation.overall_outcome == "blocked"
        assert explanation.blocking_gate == "evidence_sufficiency"
        assert len(explanation.gates) > 0
        assert len(explanation.remediation_steps) > 0
        assert explanation.human_summary != ""

    def test_explain_release_full_flow(self):
        engine = ExplainabilityEngine()
        package = {
            "package_id": "pkg-001",
            "action_type": "production_release",
            "origin": "human_operator",
            "requested_by": "engineer",
            "evidence_chain": ["ci-001", "scan-001"],
            "package_hash": "abc123def456789012345678901234567890",
            "compiled_at": datetime.now(UTC).isoformat(),
        }
        explanation = engine.explain_release(package)
        assert explanation.overall_outcome == "released"
        assert len(explanation.gates_passed) == 5
        assert explanation.human_summary != ""

    def test_explain_case_gap(self):
        engine = ExplainabilityEngine()
        case = {
            "case_id": "case-001",
            "case_type": "gap",
            "severity": "critical",
            "violated_rule_id": "RG-001",
            "affected_planes": ["release", "policy"],
            "remediation_suggestions": ["Link release to policy"],
        }
        result = engine.explain_case(case)
        assert result["case_type"] == "gap"
        assert result["severity"] == "critical"
        assert "explanation" in result
        assert "what_this_means" in result

    def test_diff_policy_versions(self):
        engine = ExplainabilityEngine()
        v1 = {"version": 1, "blocked_action_types": ["force_deploy"]}
        v2 = {"version": 2, "blocked_action_types": ["force_deploy", "unreviewed_release"]}
        diff = engine.diff_policy_versions(v1, v2)
        assert diff["is_breaking_change"] is True
        assert "unreviewed_release" in diff["newly_blocked_actions"]
        assert diff["from_version"] == 1
        assert diff["to_version"] == 2
