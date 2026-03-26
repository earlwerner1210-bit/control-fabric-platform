"""Tests for the KPI service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.kpi import KpiMeasurementCreate
from app.schemas.pilot_case import PilotCaseState
from app.services.kpi import KpiService


@pytest.fixture
def svc() -> KpiService:
    return KpiService()


CASE_ID = uuid.uuid4()


class TestRecordMeasurement:
    def test_record_measurement(self, svc: KpiService):
        result = svc.record_measurement(
            CASE_ID,
            KpiMeasurementCreate(
                metric_name="time_to_decision",
                metric_value=4.5,
                metric_unit="hours",
                dimension="workflow_type",
                dimension_value="margin_diagnosis",
            ),
        )
        assert result.metric_name == "time_to_decision"
        assert result.metric_value == 4.5
        assert result.metric_unit == "hours"
        assert result.pilot_case_id == CASE_ID

    def test_record_multiple(self, svc: KpiService):
        svc.record_measurement(CASE_ID, KpiMeasurementCreate(metric_name="m1", metric_value=1.0))
        svc.record_measurement(CASE_ID, KpiMeasurementCreate(metric_name="m2", metric_value=2.0))
        measurements = svc.get_case_measurements(CASE_ID)
        assert len(measurements) == 2


class TestGetCaseMeasurements:
    def test_empty(self, svc: KpiService):
        assert svc.get_case_measurements(uuid.uuid4()) == []


class TestComputeSummary:
    def test_empty_summary(self, svc: KpiService):
        summary = svc.compute_summary([])
        assert summary.total_cases == 0
        assert summary.approval_rate == 0.0

    def test_summary_with_cases(self, svc: KpiService):
        cases = [
            {"id": uuid.uuid4(), "state": PilotCaseState.APPROVED, "workflow_type": "margin_diagnosis"},
            {"id": uuid.uuid4(), "state": PilotCaseState.APPROVED, "workflow_type": "margin_diagnosis"},
            {"id": uuid.uuid4(), "state": PilotCaseState.OVERRIDDEN, "workflow_type": "contract_compile"},
            {"id": uuid.uuid4(), "state": PilotCaseState.ESCALATED, "workflow_type": "margin_diagnosis"},
        ]
        summary = svc.compute_summary(cases)
        assert summary.total_cases == 4
        assert summary.approval_rate == 0.5  # 2 approved out of 4 resolved
        assert summary.override_rate == 0.25
        assert summary.escalation_rate == 0.25
        assert summary.cases_by_workflow_type["margin_diagnosis"] == 3

    def test_summary_with_comparisons(self, svc: KpiService):
        cases = [{"id": uuid.uuid4(), "state": "approved", "workflow_type": "test"}]
        comparisons = [
            {"match_type": "exact_match"},
            {"match_type": "false_positive"},
            {"match_type": "exact_match"},
        ]
        summary = svc.compute_summary(cases, comparisons=comparisons)
        assert summary.exact_match_rate == pytest.approx(2 / 3)
        assert summary.false_positive_rate == pytest.approx(1 / 3)

    def test_summary_with_review_decisions(self, svc: KpiService):
        cases = [{"id": uuid.uuid4(), "state": "approved", "workflow_type": "test"}]
        decisions = [{"confidence": 0.9}, {"confidence": 0.8}]
        summary = svc.compute_summary(cases, review_decisions=decisions)
        assert summary.avg_reviewer_confidence == pytest.approx(0.85)


class TestWorkflowBreakdown:
    def test_breakdown(self, svc: KpiService):
        cases = [
            {"id": uuid.uuid4(), "state": PilotCaseState.APPROVED, "workflow_type": "margin_diagnosis"},
            {"id": uuid.uuid4(), "state": PilotCaseState.OVERRIDDEN, "workflow_type": "margin_diagnosis"},
            {"id": uuid.uuid4(), "state": PilotCaseState.APPROVED, "workflow_type": "contract_compile"},
        ]
        breakdown = svc.compute_workflow_breakdown(cases)
        assert len(breakdown) == 2
        margin = next(b for b in breakdown if b.workflow_type == "margin_diagnosis")
        assert margin.total_cases == 2
        assert margin.approved == 1
        assert margin.overridden == 1

    def test_breakdown_empty(self, svc: KpiService):
        assert svc.compute_workflow_breakdown([]) == []
