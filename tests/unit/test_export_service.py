"""Tests for the export service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.report import CaseExportRequest, ExportFormat
from app.services.export import ExportService


@pytest.fixture
def svc() -> ExportService:
    return ExportService()


CASE_ID = uuid.uuid4()
USER = uuid.uuid4()


def _case_data(**kwargs):
    defaults = {
        "id": CASE_ID,
        "title": "Test Margin Case",
        "workflow_type": "margin_diagnosis",
        "state": "approved",
        "severity": "high",
        "business_impact": "major",
    }
    defaults.update(kwargs)
    return defaults


class TestExportCase:
    def test_export_json(self, svc: ExportService):
        result = svc.export_case(
            CASE_ID, USER, _case_data(),
            CaseExportRequest(format=ExportFormat.JSON),
        )
        assert result.pilot_case_id == CASE_ID
        assert result.format == ExportFormat.JSON
        assert result.exported_by == USER
        assert "case" in result.content

    def test_export_markdown(self, svc: ExportService):
        result = svc.export_case(
            CASE_ID, USER, _case_data(),
            CaseExportRequest(format=ExportFormat.MARKDOWN),
        )
        assert "markdown" in result.content
        assert "# Pilot Case Export" in result.content["markdown"]
        assert "Test Margin Case" in result.content["markdown"]

    def test_export_with_evidence(self, svc: ExportService):
        evidence = {"completeness_score": 0.95, "chain_stages": ["contract_basis"]}
        result = svc.export_case(
            CASE_ID, USER, _case_data(),
            CaseExportRequest(include_evidence=True),
            evidence=evidence,
        )
        assert "evidence" in result.content

    def test_export_without_evidence(self, svc: ExportService):
        result = svc.export_case(
            CASE_ID, USER, _case_data(),
            CaseExportRequest(include_evidence=False),
        )
        assert "evidence" not in result.content

    def test_export_with_review(self, svc: ExportService):
        review = {"decisions": [{"outcome": "accept"}], "notes": []}
        result = svc.export_case(
            CASE_ID, USER, _case_data(),
            CaseExportRequest(include_review=True),
            review=review,
        )
        assert "review" in result.content

    def test_export_with_baseline(self, svc: ExportService):
        baseline = {"expected_outcome": "billable", "platform_outcome": "billable", "match_type": "exact_match"}
        result = svc.export_case(
            CASE_ID, USER, _case_data(),
            CaseExportRequest(include_baseline=True, format=ExportFormat.MARKDOWN),
            baseline=baseline,
        )
        assert "baseline" in result.content
        assert "Baseline Comparison" in result.content["markdown"]


class TestGetExports:
    def test_get_exports(self, svc: ExportService):
        svc.export_case(CASE_ID, USER, _case_data(), CaseExportRequest())
        svc.export_case(CASE_ID, USER, _case_data(), CaseExportRequest(format=ExportFormat.MARKDOWN))
        exports = svc.get_exports(CASE_ID)
        assert len(exports) == 2

    def test_get_empty(self, svc: ExportService):
        assert svc.get_exports(uuid.uuid4()) == []


class TestPilotReport:
    def test_empty_report(self, svc: ExportService):
        report = svc.generate_pilot_report([])
        assert report.total_cases == 0
        assert report.decision_summaries == []

    def test_report_with_cases(self, svc: ExportService):
        cases = [
            {"id": uuid.uuid4(), "title": "Case 1", "state": "approved", "workflow_type": "margin_diagnosis"},
            {"id": uuid.uuid4(), "title": "Case 2", "state": "overridden", "workflow_type": "contract_compile"},
            {"id": uuid.uuid4(), "title": "Case 3", "state": "approved", "workflow_type": "margin_diagnosis"},
        ]
        report = svc.generate_pilot_report(cases)
        assert report.total_cases == 3
        assert report.cases_by_state["approved"] == 2
        assert report.cases_by_state["overridden"] == 1
        assert report.cases_by_workflow["margin_diagnosis"] == 2
        assert len(report.decision_summaries) == 3
