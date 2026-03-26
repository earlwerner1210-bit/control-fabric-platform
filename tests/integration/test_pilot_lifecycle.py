"""Integration tests for full pilot case lifecycle flows."""

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
from app.schemas.evidence import EvidenceBundleCreate, EvidenceItem
from app.schemas.feedback import FeedbackCategory, FeedbackEntryCreate, FeedbackSeverity
from app.schemas.kpi import KpiMeasurementCreate
from app.schemas.pilot_case import CaseSeverity, PilotCaseCreate, PilotCaseState
from app.schemas.report import (
    BaselineExpectation,
    BaselineMatchType,
    CaseExportRequest,
    ExportFormat,
)
from app.schemas.review import ReviewDecisionCreate, ReviewOutcome, ReviewRequest
from app.services.approval import ApprovalService
from app.services.baseline import BaselineComparisonService
from app.services.evidence import EvidenceService
from app.services.export import ExportService
from app.services.feedback import FeedbackService
from app.services.kpi import KpiService
from app.services.pilot_cases import PilotCaseService
from app.services.review import ReviewService

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000099")
USER = uuid.UUID("00000000-0000-0000-0000-000000000098")
REVIEWER = uuid.UUID("00000000-0000-0000-0000-000000000097")


@pytest.fixture
def services():
    case_svc = PilotCaseService()
    approval_svc = ApprovalService(case_svc)
    review_svc = ReviewService()
    evidence_svc = EvidenceService()
    baseline_svc = BaselineComparisonService()
    kpi_svc = KpiService()
    feedback_svc = FeedbackService()
    export_svc = ExportService()
    return {
        "case": case_svc,
        "approval": approval_svc,
        "review": review_svc,
        "evidence": evidence_svc,
        "baseline": baseline_svc,
        "kpi": kpi_svc,
        "feedback": feedback_svc,
        "export": export_svc,
    }


def _advance_to_review(case_svc: PilotCaseService, case_id: uuid.UUID):
    case_svc.transition_state(case_id, PilotCaseState.EVIDENCE_READY, USER)
    case_svc.transition_state(case_id, PilotCaseState.WORKFLOW_EXECUTED, USER)
    case_svc.transition_state(case_id, PilotCaseState.VALIDATION_COMPLETED, USER)
    case_svc.transition_state(case_id, PilotCaseState.UNDER_REVIEW, USER)


class TestApprovedMarginCase:
    """Full lifecycle: create -> review -> approve -> export."""

    def test_full_approved_lifecycle(self, services):
        s = services
        # Create case
        case = s["case"].create_case(
            TENANT,
            PilotCaseCreate(
                title="Margin Case Alpha",
                workflow_type="margin_diagnosis",
                severity=CaseSeverity.HIGH,
            ),
            USER,
        )
        case_id = case.id

        # Assign reviewer
        s["case"].assign_reviewer(case_id, REVIEWER, USER, notes="Senior margin reviewer")

        # Store evidence
        bundle = s["evidence"].create_bundle(
            EvidenceBundleCreate(
                pilot_case_id=case_id,
                items=[
                    EvidenceItem(
                        evidence_type="document",
                        source_id=uuid.uuid4(),
                        source_label="MSA Contract",
                    ),
                    EvidenceItem(evidence_type="chunk", source_id=uuid.uuid4(), confidence=0.92),
                ],
                chain_stages=["contract_basis", "work_authorization", "execution_evidence"],
                completeness_score=0.92,
            )
        )

        # Store baseline expectation
        s["baseline"].store_expectation(
            case_id,
            BaselineExpectation(
                expected_outcome="billable",
                expected_confidence=0.95,
                source="human_expert",
            ),
        )

        # Advance to review
        _advance_to_review(s["case"], case_id)

        # Create review and add decision
        s["review"].create_review(
            case_id,
            ReviewRequest(
                model_output_summary={"verdict": "billable", "confidence": 0.92},
                evidence_bundle_id=bundle.id,
            ),
        )
        s["review"].add_decision(
            case_id,
            REVIEWER,
            ReviewDecisionCreate(
                outcome=ReviewOutcome.ACCEPT,
                reasoning="Correct billability determination",
                confidence=0.95,
            ),
        )

        # Approve
        s["approval"].approve(
            case_id,
            REVIEWER,
            ApprovalRequest(
                reasoning="Verified against contract terms",
                business_impact_notes="Standard rate card applies",
            ),
        )

        # Compare baseline
        comparison = s["baseline"].compare(case_id, platform_outcome="billable")
        assert comparison.match_type == BaselineMatchType.EXACT_MATCH

        # Record KPI
        s["kpi"].record_measurement(
            case_id,
            KpiMeasurementCreate(
                metric_name="time_to_decision",
                metric_value=2.5,
                metric_unit="hours",
            ),
        )

        # Export
        export = s["export"].export_case(
            case_id,
            USER,
            {
                "id": case_id,
                "title": "Margin Case Alpha",
                "workflow_type": "margin_diagnosis",
                "state": "approved",
            },
            CaseExportRequest(format=ExportFormat.MARKDOWN),
        )
        assert "markdown" in export.content

        # Verify final state
        final_case = s["case"].get_case(case_id)
        assert final_case.state == PilotCaseState.APPROVED

        # Verify timeline
        timeline = s["case"].get_timeline(case_id)
        event_types = [e.event_type for e in timeline]
        assert "case_created" in event_types
        assert "reviewer_assigned" in event_types
        assert "state_transition" in event_types


class TestOverriddenMarginCase:
    """Lifecycle: create -> review -> override."""

    def test_override_lifecycle(self, services):
        s = services
        case = s["case"].create_case(
            TENANT,
            PilotCaseCreate(title="Override Case", workflow_type="margin_diagnosis"),
            USER,
        )
        _advance_to_review(s["case"], case.id)

        s["review"].create_review(
            case.id,
            ReviewRequest(
                model_output_summary={"verdict": "billable", "confidence": 0.88},
            ),
        )
        s["review"].add_decision(
            case.id,
            REVIEWER,
            ReviewDecisionCreate(
                outcome=ReviewOutcome.REJECT,
                reasoning="Commercial truth differs from model output",
            ),
        )

        s["approval"].override(
            case.id,
            REVIEWER,
            OverrideRequest(
                override_reason=OverrideReason.MODEL_ACCEPTABLE_COMMERCIAL_DIFFERS,
                override_detail="Contract clause 4.2 applies differently",
                corrected_outcome={"verdict": "not_billable", "reason": "clause_4_2"},
            ),
        )

        s["baseline"].store_expectation(
            case.id, BaselineExpectation(expected_outcome="not_billable")
        )
        comparison = s["baseline"].compare(
            case.id, platform_outcome="billable", reviewer_outcome="not_billable"
        )
        assert comparison.match_type == BaselineMatchType.EXACT_MATCH

        final = s["case"].get_case(case.id)
        assert final.state == PilotCaseState.OVERRIDDEN


class TestEscalatedFieldCase:
    """Lifecycle: create -> review -> escalate -> re-review -> approve."""

    def test_escalation_round_trip(self, services):
        s = services
        case = s["case"].create_case(
            TENANT,
            PilotCaseCreate(title="Field Escalation", workflow_type="work_order_readiness"),
            USER,
        )
        _advance_to_review(s["case"], case.id)

        s["review"].create_review(case.id, ReviewRequest())
        s["review"].add_decision(
            case.id,
            REVIEWER,
            ReviewDecisionCreate(
                outcome=ReviewOutcome.ESCALATE,
                reasoning="Requires commercial lead sign-off",
            ),
        )

        s["approval"].escalate(
            case.id,
            REVIEWER,
            EscalationRequest(
                escalation_route=EscalationRoute.COMMERCIAL_LEAD,
                escalation_reason="High-value contract exception",
                urgency="urgent",
            ),
        )
        assert s["case"].get_case(case.id).state == PilotCaseState.ESCALATED

        # Return to review after escalation
        s["case"].transition_state(case.id, PilotCaseState.UNDER_REVIEW, USER)
        s["review"].add_decision(
            case.id,
            REVIEWER,
            ReviewDecisionCreate(
                outcome=ReviewOutcome.ACCEPT,
                reasoning="Commercial lead approved",
                confidence=0.98,
            ),
        )

        # Final approval
        s["approval"].approve(case.id, REVIEWER, ApprovalRequest(reasoning="Escalation resolved"))
        assert s["case"].get_case(case.id).state == PilotCaseState.APPROVED

        # Review summary
        summary = s["review"].get_summary(case.id)
        assert summary.total_decisions == 2
        assert summary.latest_outcome == ReviewOutcome.ACCEPT


class TestFeedbackLoop:
    """Test feedback capture across multiple cases."""

    def test_feedback_aggregation(self, services):
        s = services
        case1 = s["case"].create_case(
            TENANT, PilotCaseCreate(title="C1", workflow_type="margin_diagnosis"), USER
        )
        case2 = s["case"].create_case(
            TENANT, PilotCaseCreate(title="C2", workflow_type="contract_compile"), USER
        )

        s["feedback"].submit_feedback(
            case1.id,
            USER,
            FeedbackEntryCreate(
                category=FeedbackCategory.RULE_ACCURACY,
                severity=FeedbackSeverity.CRITICAL,
                title="Rate card rule broken",
                description="Weekend rates not applied",
                affected_component="rule_engine",
            ),
        )
        s["feedback"].submit_feedback(
            case2.id,
            USER,
            FeedbackEntryCreate(
                category=FeedbackCategory.EVIDENCE_GAP,
                severity=FeedbackSeverity.HIGH,
                title="Missing document",
                description="Field completion certificate missing",
                affected_component="evidence",
            ),
        )

        summary = s["feedback"].get_summary()
        assert summary.total_entries == 2
        assert summary.top_issues[0].severity == FeedbackSeverity.CRITICAL


class TestKpiAcrossCases:
    """Test KPI aggregation across multiple cases."""

    def test_kpi_summary(self, services):
        s = services
        cases_data = []
        for title, wt, final_state in [
            ("C1", "margin_diagnosis", PilotCaseState.APPROVED),
            ("C2", "margin_diagnosis", PilotCaseState.OVERRIDDEN),
            ("C3", "contract_compile", PilotCaseState.APPROVED),
            ("C4", "contract_compile", PilotCaseState.ESCALATED),
        ]:
            case = s["case"].create_case(
                TENANT, PilotCaseCreate(title=title, workflow_type=wt), USER
            )
            cases_data.append({"id": case.id, "state": final_state, "workflow_type": wt})

        summary = s["kpi"].compute_summary(cases_data)
        assert summary.total_cases == 4
        assert summary.cases_by_workflow_type["margin_diagnosis"] == 2

        breakdown = s["kpi"].compute_workflow_breakdown(cases_data)
        assert len(breakdown) == 2
