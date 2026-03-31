from __future__ import annotations

import json

import pytest


class TestComplianceReportGenerator:
    def test_generates_report_for_default_tenant(self) -> None:
        from app.core.reporting.compliance_report import ComplianceReportGenerator

        gen = ComplianceReportGenerator()
        report = gen.generate("default", period_days=30)
        assert report.tenant_id == "default"
        assert report.audit_readiness_grade in ("A", "B", "C", "D")
        assert 0 <= report.audit_readiness_score <= 100
        assert len(report.report_hash) == 16

    def test_control_coverage_covers_all_frameworks(self) -> None:
        from app.core.reporting.compliance_report import (
            CONTROL_FRAMEWORKS,
            ComplianceReportGenerator,
        )

        gen = ComplianceReportGenerator()
        report = gen.generate("default")
        framework_names = {c.framework for c in report.control_coverage}
        for framework in CONTROL_FRAMEWORKS:
            assert framework in framework_names

    def test_nis2_controls_all_assessed(self) -> None:
        from app.core.reporting.compliance_report import (
            CONTROL_FRAMEWORKS,
            ComplianceReportGenerator,
        )

        gen = ComplianceReportGenerator()
        report = gen.generate("default")
        nis2_controls = [c for c in report.control_coverage if "NIS2" in c.framework]
        expected = len(CONTROL_FRAMEWORKS["NIS2 Directive (EU) 2022/2555"])
        assert len(nis2_controls) == expected

    def test_executive_summary_is_non_empty(self) -> None:
        from app.core.reporting.compliance_report import ComplianceReportGenerator

        gen = ComplianceReportGenerator()
        report = gen.generate("default")
        assert len(report.executive_summary) > 50

    def test_csv_export_has_headers(self) -> None:
        from app.core.reporting.compliance_report import ComplianceReportGenerator

        gen = ComplianceReportGenerator()
        report = gen.generate("default")
        rows = gen.to_csv_rows(report)
        assert len(rows) > 0
        assert "section" in rows[0]

    def test_coverage_statuses_are_valid(self) -> None:
        from app.core.reporting.compliance_report import ComplianceReportGenerator

        gen = ComplianceReportGenerator()
        report = gen.generate("default")
        valid_statuses = {"covered", "partial", "not_covered"}
        for ctrl in report.control_coverage:
            assert ctrl.status in valid_statuses


class TestAnalyticsEngine:
    def test_returns_trend_structure(self) -> None:
        from app.core.reporting.analytics import AnalyticsEngine

        engine = AnalyticsEngine()
        result = engine.get_trends("default", period_days=30, granularity="weekly")
        assert "trends" in result
        assert "summary" in result
        assert "gate_submissions" in result["trends"]
        assert "block_rate" in result["trends"]

    def test_trend_points_match_period(self) -> None:
        from app.core.reporting.analytics import AnalyticsEngine

        engine = AnalyticsEngine()
        result = engine.get_trends("default", period_days=28, granularity="weekly")
        points = result["trends"]["block_rate"]["points"]
        assert len(points) == 4  # 28 days = 4 weeks

    def test_performance_report_has_velocity(self) -> None:
        from app.core.reporting.analytics import AnalyticsEngine

        engine = AnalyticsEngine()
        result = engine.get_performance("default", period_days=30)
        assert "governance_velocity" in result
        assert "block_rate_pct" in result

    def test_insights_are_generated(self) -> None:
        from app.core.reporting.analytics import AnalyticsEngine

        engine = AnalyticsEngine()
        result = engine.get_trends("default", period_days=30)
        assert isinstance(result["insights"], list)
        assert len(result["insights"]) >= 1


class TestProductionReadinessChecker:
    def test_returns_readiness_report(self) -> None:
        from app.core.reporting.readiness_checker import ProductionReadinessChecker

        checker = ProductionReadinessChecker()
        report = checker.check()
        assert isinstance(report.passed, bool)
        assert 0 <= report.score <= 100
        assert report.grade in ("A", "B", "C", "F")
        assert isinstance(report.checks, list)

    def test_all_checks_have_required_fields(self) -> None:
        from app.core.reporting.readiness_checker import ProductionReadinessChecker

        checker = ProductionReadinessChecker()
        report = checker.check()
        for check in report.checks:
            assert check.name
            assert isinstance(check.passed, bool)
            assert check.detail
            assert check.severity in ("error", "warning", "info")

    def test_ready_for_demo_when_score_sufficient(self) -> None:
        from app.core.reporting.readiness_checker import ProductionReadinessChecker

        checker = ProductionReadinessChecker()
        report = checker.check()
        if report.score >= 60:
            assert "demo" in report.ready_for


class TestPackAuthoringSDK:
    def test_build_simple_pack(self) -> None:
        from app.core.pack_authoring.sdk import PackBuilder

        pack = (
            PackBuilder("test-pack-v1")
            .name("Test Pack")
            .description("A test pack for unit testing the SDK")
            .version("1.0.0")
            .domain("telecom")
            .add_rule(
                rule_id="TEST-001",
                description="Test rule for SDK validation",
                source_plane="operations",
                target_plane="compliance",
                severity="high",
            )
            .build()
        )
        assert pack.pack_id == "test-pack-v1"
        assert len(pack.rules) == 1
        assert pack.rules[0].rule_id == "TEST-001"

    def test_build_without_description_raises(self) -> None:
        from app.core.pack_authoring.sdk import PackBuilder

        with pytest.raises(ValueError, match="must have a description"):
            PackBuilder("no-desc-v1").add_rule(
                rule_id="R1",
                description="rule",
                source_plane="ops",
                target_plane="comp",
            ).build()

    def test_build_without_rules_raises(self) -> None:
        from app.core.pack_authoring.sdk import PackBuilder

        with pytest.raises(ValueError, match="no rules"):
            PackBuilder("no-rules-v1").description("Has a description").build()

    def test_pack_serialises_to_json(self) -> None:
        from app.core.pack_authoring.sdk import PackBuilder

        pack = (
            PackBuilder("json-pack-v1")
            .name("JSON Test Pack")
            .description("Tests JSON serialisation")
            .add_rule("R1", "A rule", "ops", "compliance")
            .build()
        )
        json_str = pack.to_json()
        parsed = json.loads(json_str)
        assert parsed["pack_id"] == "json-pack-v1"
        assert len(parsed["rules"]) == 1

    def test_pack_roundtrip_json(self) -> None:
        from app.core.pack_authoring.sdk import PackBuilder

        pack = (
            PackBuilder("roundtrip-v1")
            .name("Roundtrip Pack")
            .description("Tests JSON roundtrip")
            .domain("banking")
            .add_rule("RT-001", "Roundtrip rule", "risk", "compliance")
            .build()
        )
        json_str = pack.to_json()
        restored = PackBuilder.from_json(json_str)
        assert restored.pack_id == pack.pack_id
        assert len(restored.rules) == len(pack.rules)

    def test_example_telecom_pack_builds(self) -> None:
        from app.core.pack_authoring.sdk import build_example_telecom_pack

        pack = build_example_telecom_pack()
        assert pack.pack_id == "vodafone-network-ops-v1"
        assert len(pack.rules) == 4
        assert "force_deploy" in pack.blocked_action_types
