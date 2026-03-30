"""Tests for the pilot reporting service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.approval import (
    ApprovalRequest,
    EscalationRequest,
    EscalationRoute,
    OverrideReason,
    OverrideRequest,
)
from app.schemas.evidence import EvidenceBundleCreate
from app.schemas.pilot_case import CaseSeverity, PilotCaseCreate, PilotCaseState
from app.schemas.report import BaselineExpectation
from app.schemas.review import ReviewDecisionCreate, ReviewOutcome, ReviewRequest
from app.services.approval import ApprovalService
from app.services.baseline import BaselineComparisonService
from app.services.evidence import EvidenceService
from app.services.feedback import FeedbackService
from app.services.kpi import KpiService
from app.services.pilot_cases import PilotCaseService
from app.services.reporting.pilot_reporting import PilotReportingService
from app.services.review import ReviewService

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
ANALYST = uuid.UUID("00000000-0000-0000-0000-000000000010")
REVIEWER = uuid.UUID("00000000-0000-0000-0000-000000000020")


def _advance_to_review(case_svc, case_id):
    for state in [
        PilotCaseState.EVIDENCE_READY,
        PilotCaseState.WORKFLOW_EXECUTED,
        PilotCaseState.VALIDATION_COMPLETED,
        PilotCaseState.UNDER_REVIEW,
    ]:
        case_svc.transition_state(case_id, state, ANALYST)


@pytest.fixture
def platform():
    case_svc = PilotCaseService()
    approval_svc = ApprovalService(case_svc)
    review_svc = ReviewService()
    evidence_svc = EvidenceService()
    baseline_svc = BaselineComparisonService()
    kpi_svc = KpiService()
    feedback_svc = FeedbackService()

    reporting_svc = PilotReportingService(
        case_service=case_svc,
        review_service=review_svc,
        approval_service=approval_svc,
        evidence_service=evidence_svc,
        baseline_service=baseline_svc,
        kpi_service=kpi_svc,
        feedback_service=feedback_svc,
    )

    return {
        "case": case_svc,
        "approval": approval_svc,
        "review": review_svc,
        "evidence": evidence_svc,
        "baseline": baseline_svc,
        "kpi": kpi_svc,
        "feedback": feedback_svc,
        "reporting": reporting_svc,
    }


class TestPilotCaseReport:
    def test_report_for_approved_case(self, platform):
        p = platform
        case = p["case"].create_case(
            TENANT,
            PilotCaseCreate(
                title="Report Test",
                workflow_type="margin_diagnosis",
                severity=CaseSeverity.HIGH,
            ),
            ANALYST,
        )
        p["evidence"].create_bundle(
            EvidenceBundleCreate(pilot_case_id=case.id, completeness_score=0.9)
        )
        _advance_to_review(p["case"], case.id)
        p["review"].create_review(case.id, ReviewRequest())
        p["review"].add_decision(
            case.id,
            REVIEWER,
            ReviewDecisionCreate(
                outcome=ReviewOutcome.ACCEPT,
                reasoning="OK",
                confidence=0.95,
            ),
        )
        p["approval"].approve(case.id, REVIEWER, ApprovalRequest(reasoning="Verified"))

        report = p["reporting"].get_pilot_case_report(case.id)
        assert report is not None
        assert report.state == "approved"
        assert report.evidence_completeness == 0.9
        assert report.review_outcome == "accept"
        assert report.approval_type == "approval"
        assert report.timeline_events > 0

    def test_report_for_missing_case(self, platform):
        report = platform["reporting"].get_pilot_case_report(uuid.uuid4())
        assert report is None


class TestPilotSummaryReport:
    def test_summary_with_cases(self, platform):
        p = platform
        for title, wt in [("C1", "margin"), ("C2", "margin"), ("C3", "contract")]:
            p["case"].create_case(TENANT, PilotCaseCreate(title=title, workflow_type=wt), ANALYST)

        report = p["reporting"].get_pilot_summary_report(TENANT)
        assert report.total_cases == 3
        assert report.cases_by_workflow["margin"] == 2

    def test_empty_summary(self, platform):
        report = platform["reporting"].get_pilot_summary_report(uuid.uuid4())
        assert report.total_cases == 0


class TestWorkflowBreakdownReport:
    def test_breakdown(self, platform):
        p = platform
        for title, wt in [("C1", "margin"), ("C2", "margin"), ("C3", "contract")]:
            case = p["case"].create_case(
                TENANT, PilotCaseCreate(title=title, workflow_type=wt), ANALYST
            )
            if title == "C1":
                _advance_to_review(p["case"], case.id)
                p["review"].create_review(case.id, ReviewRequest())
                p["review"].add_decision(
                    case.id,
                    REVIEWER,
                    ReviewDecisionCreate(outcome=ReviewOutcome.ACCEPT, reasoning="OK"),
                )
                p["approval"].approve(case.id, REVIEWER, ApprovalRequest(reasoning="OK"))

        breakdown = p["reporting"].get_workflow_breakdown_report(TENANT)
        assert len(breakdown) == 2
        margin = next(b for b in breakdown if b.workflow_type == "margin")
        assert margin.total_cases == 2
        assert margin.approved == 1


class TestOverrideEscalationReport:
    def test_override_report(self, platform):
        p = platform
        case = p["case"].create_case(
            TENANT,
            PilotCaseCreate(title="Override", workflow_type="margin"),
            ANALYST,
        )
        _advance_to_review(p["case"], case.id)
        p["approval"].override(
            case.id,
            REVIEWER,
            OverrideRequest(
                override_reason=OverrideReason.EVIDENCE_INCOMPLETE,
                override_detail="Missing docs",
                corrected_outcome={"verdict": "not_billable"},
            ),
        )

        report = p["reporting"].get_override_escalation_report(TENANT)
        assert report.total_overrides == 1
        assert "evidence_incomplete" in report.overrides_by_reason

    def test_escalation_report(self, platform):
        p = platform
        case = p["case"].create_case(
            TENANT,
            PilotCaseCreate(title="Escalate", workflow_type="ops"),
            ANALYST,
        )
        _advance_to_review(p["case"], case.id)
        p["approval"].escalate(
            case.id,
            REVIEWER,
            EscalationRequest(
                escalation_route=EscalationRoute.GOVERNANCE_BOARD,
                escalation_reason="Policy exception",
            ),
        )

        report = p["reporting"].get_override_escalation_report(TENANT)
        assert report.total_escalations == 1
        assert "governance_board" in report.escalations_by_route


class TestBaselineComparisonReport:
    def test_baseline_report(self, platform):
        p = platform
        case = p["case"].create_case(
            TENANT,
            PilotCaseCreate(title="BL", workflow_type="margin"),
            ANALYST,
        )
        p["baseline"].store_expectation(case.id, BaselineExpectation(expected_outcome="billable"))
        p["baseline"].compare(case.id, platform_outcome="billable")

        report = p["reporting"].get_baseline_comparison_report(TENANT)
        assert report.total_compared == 1
        assert report.exact_matches == 1
        assert report.accuracy_rate == 1.0

    def test_empty_baseline_report(self, platform):
        report = platform["reporting"].get_baseline_comparison_report(TENANT)
        assert report.total_compared == 0
