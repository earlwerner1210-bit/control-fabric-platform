"""Workflow tests for pilot proof layer — end-to-end flows."""

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
from app.services.evidence.completeness import score_evidence_completeness
from app.services.export import ExportService
from app.services.feedback import FeedbackService
from app.services.kpi import KpiService
from app.services.pilot_cases import PilotCaseService
from app.services.reporting.pilot_reporting import PilotReportingService
from app.services.review import ReviewService
from app.workflows.pilot_case_lifecycle import (
    PilotCaseLifecycleActivities,
    PilotCaseLifecycleInput,
    PilotCaseLifecycleWorkflow,
)
from app.workflows.review_and_approval import (
    ReviewAndApprovalActivities,
    ReviewAndApprovalInput,
    ReviewAndApprovalWorkflow,
)

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


class TestFullPilotProofLoop:
    """End-to-end: lifecycle workflow -> evidence -> review -> baseline -> KPI -> report."""

    def test_approved_margin_case_full_proof(self):
        # Services
        case_svc = PilotCaseService()
        approval_svc = ApprovalService(case_svc)
        review_svc = ReviewService()
        evidence_svc = EvidenceService()
        baseline_svc = BaselineComparisonService()
        kpi_svc = KpiService()
        feedback_svc = FeedbackService()
        export_svc = ExportService()
        reporting_svc = PilotReportingService(
            case_service=case_svc,
            review_service=review_svc,
            approval_service=approval_svc,
            evidence_service=evidence_svc,
            baseline_service=baseline_svc,
            kpi_service=kpi_svc,
            feedback_service=feedback_svc,
        )

        # 1. Lifecycle workflow creates case
        lifecycle = PilotCaseLifecycleWorkflow(PilotCaseLifecycleActivities())
        case_id = str(uuid.uuid4())
        lc_result = lifecycle.run(
            PilotCaseLifecycleInput(
                pilot_case_id=case_id,
                tenant_id=str(TENANT),
                workflow_type="margin_diagnosis",
                title="Full Proof Loop Case",
                created_by=str(ANALYST),
                reviewer_id=str(REVIEWER),
                baseline_expectation={"expected_outcome": "billable", "expected_confidence": 0.95},
            )
        )
        assert lc_result.final_state == "under_review"

        # 2. Create real case in service layer
        case = case_svc.create_case(
            TENANT,
            PilotCaseCreate(
                title="Full Proof Loop Case",
                workflow_type="margin_diagnosis",
                severity=CaseSeverity.HIGH,
            ),
            ANALYST,
        )

        # 3. Evidence assembly with completeness scoring
        items = [
            {"evidence_type": "document", "source_id": str(uuid.uuid4()), "source_label": "MSA"},
            {"evidence_type": "chunk", "source_id": str(uuid.uuid4()), "confidence": 0.94},
            {"evidence_type": "control_object", "source_id": str(uuid.uuid4())},
        ]
        trace = {"rules_fired": [{"rule_id": "R001"}], "cross_plane_conflicts": []}
        validation_trace = {"validators_run": [{"name": "rate_check"}]}
        model_lineage = {"model_id": "claude-3-opus", "model_version": "20240229"}

        completeness = score_evidence_completeness(
            items=items,
            chain_stages=[
                "contract_basis",
                "work_authorization",
                "execution_evidence",
                "billing_evidence",
            ],
            trace=trace,
            validation_trace=validation_trace,
            model_lineage=model_lineage,
        )
        assert completeness.normalized == pytest.approx(1.0)

        evidence_svc.create_bundle(
            EvidenceBundleCreate(
                pilot_case_id=case.id,
                items=[
                    EvidenceItem(
                        **{k: uuid.UUID(v) if k == "source_id" else v for k, v in item.items()}
                    )
                    for item in items
                ],
                chain_stages=[
                    "contract_basis",
                    "work_authorization",
                    "execution_evidence",
                    "billing_evidence",
                ],
                completeness_score=completeness.normalized,
            )
        )
        evidence_svc.store_trace(
            case.id,
            documents=[{"object_type": "contract", "object_id": str(uuid.uuid4()), "label": "MSA"}],
            rules_fired=[{"rule_id": "R001", "result": "pass"}],
        )
        evidence_svc.store_model_lineage(
            case.id,
            model_id="claude-3-opus",
            model_version="20240229",
            inference_provider="anthropic",
            input_tokens=1500,
            output_tokens=800,
        )

        # 4. Baseline expectation
        baseline_svc.store_expectation(
            case.id,
            BaselineExpectation(expected_outcome="billable", expected_confidence=0.95),
        )

        # 5. Advance to review and add decision
        _advance_to_review(case_svc, case.id)
        review_svc.create_review(
            case.id,
            ReviewRequest(
                model_output_summary={"verdict": "billable", "confidence": 0.94},
            ),
        )
        review_svc.add_decision(
            case.id,
            REVIEWER,
            ReviewDecisionCreate(
                outcome=ReviewOutcome.ACCEPT,
                reasoning="Verified correct",
                confidence=0.96,
            ),
        )

        # 6. Review and approval workflow
        ra_workflow = ReviewAndApprovalWorkflow(ReviewAndApprovalActivities())
        ra_result = ra_workflow.run(
            ReviewAndApprovalInput(
                pilot_case_id=str(case.id),
                tenant_id=str(TENANT),
                reviewer_id=str(REVIEWER),
                workflow_output={"verdict": "billable", "confidence": 0.94},
                baseline_expectation={"expected_outcome": "billable"},
            ),
            review_outcome="accept",
            review_confidence=0.96,
        )
        assert ra_result.final_state == "approved"

        # 7. Approve in service layer
        approval_svc.approve(case.id, REVIEWER, ApprovalRequest(reasoning="Verified"))

        # 8. Baseline comparison
        comparison = baseline_svc.compare(case.id, platform_outcome="billable")
        assert comparison.match_type == BaselineMatchType.EXACT_MATCH

        # 9. KPI recording
        kpi_svc.record_measurement(
            case.id,
            KpiMeasurementCreate(
                metric_name="time_to_decision",
                metric_value=1.5,
                metric_unit="hours",
            ),
        )
        kpi_svc.record_measurement(
            case.id,
            KpiMeasurementCreate(
                metric_name="evidence_completeness",
                metric_value=completeness.normalized,
            ),
        )

        # 10. Export
        export = export_svc.export_case(
            case.id,
            ANALYST,
            {
                "id": case.id,
                "title": case.title,
                "workflow_type": "margin_diagnosis",
                "state": "approved",
            },
            CaseExportRequest(format=ExportFormat.MARKDOWN),
        )
        assert "markdown" in export.content

        # 11. Report generation
        report = reporting_svc.get_pilot_case_report(case.id)
        assert report is not None
        assert report.state == "approved"
        assert report.evidence_completeness == pytest.approx(1.0)
        assert report.review_outcome == "accept"
        assert report.baseline_match_type == "exact_match"
        assert report.approval_type == "approval"
        assert len(report.kpi_measurements) == 2

        # 12. Summary report
        summary = reporting_svc.get_pilot_summary_report(TENANT)
        assert summary.total_cases >= 1


class TestOverriddenCaseProofLoop:
    """End-to-end: case is overridden, baseline captures the correction."""

    def test_override_proof_loop(self):
        case_svc = PilotCaseService()
        approval_svc = ApprovalService(case_svc)
        review_svc = ReviewService()
        baseline_svc = BaselineComparisonService()
        kpi_svc = KpiService()
        reporting_svc = PilotReportingService(
            case_service=case_svc,
            approval_service=approval_svc,
            baseline_service=baseline_svc,
            kpi_service=kpi_svc,
        )

        case = case_svc.create_case(
            TENANT,
            PilotCaseCreate(title="Override Proof", workflow_type="margin_diagnosis"),
            ANALYST,
        )

        baseline_svc.store_expectation(
            case.id,
            BaselineExpectation(expected_outcome="not_billable"),
        )

        _advance_to_review(case_svc, case.id)

        review_svc.create_review(
            case.id,
            ReviewRequest(
                model_output_summary={"verdict": "billable", "confidence": 0.78},
            ),
        )
        review_svc.add_decision(
            case.id,
            REVIEWER,
            ReviewDecisionCreate(
                outcome=ReviewOutcome.REJECT,
                reasoning="Model missed clause exception",
            ),
        )

        approval_svc.override(
            case.id,
            REVIEWER,
            OverrideRequest(
                override_reason=OverrideReason.MODEL_ACCEPTABLE_COMMERCIAL_DIFFERS,
                override_detail="Clause 4.2 exception",
                corrected_outcome={"verdict": "not_billable"},
            ),
        )

        # Reviewer outcome matches baseline
        comparison = baseline_svc.compare(
            case.id,
            platform_outcome="billable",
            reviewer_outcome="not_billable",
        )
        assert comparison.match_type == BaselineMatchType.EXACT_MATCH

        # Override report shows it
        report = reporting_svc.get_override_escalation_report(TENANT)
        assert report.total_overrides == 1

        # Baseline report shows accuracy
        bl_report = reporting_svc.get_baseline_comparison_report(TENANT)
        assert bl_report.total_compared == 1
        assert bl_report.accuracy_rate == 1.0


class TestMultiCaseReportingWorkflow:
    """Test reporting across multiple cases of mixed outcomes."""

    def test_multi_case_reporting(self):
        case_svc = PilotCaseService()
        approval_svc = ApprovalService(case_svc)
        baseline_svc = BaselineComparisonService()
        reporting_svc = PilotReportingService(
            case_service=case_svc,
            approval_service=approval_svc,
            baseline_service=baseline_svc,
        )

        # Create 5 cases with different outcomes
        for i, (title, wt, final_state) in enumerate(
            [
                ("Approved 1", "margin", PilotCaseState.APPROVED),
                ("Approved 2", "contract", PilotCaseState.APPROVED),
                ("Overridden", "margin", PilotCaseState.OVERRIDDEN),
                ("Escalated", "ops", PilotCaseState.ESCALATED),
                ("Under Review", "margin", PilotCaseState.UNDER_REVIEW),
            ]
        ):
            case = case_svc.create_case(
                TENANT,
                PilotCaseCreate(title=title, workflow_type=wt),
                ANALYST,
            )
            _advance_to_review(case_svc, case.id)

            if final_state == PilotCaseState.APPROVED:
                approval_svc.approve(case.id, REVIEWER, ApprovalRequest(reasoning="OK"))
            elif final_state == PilotCaseState.OVERRIDDEN:
                approval_svc.override(
                    case.id,
                    REVIEWER,
                    OverrideRequest(
                        override_reason=OverrideReason.EVIDENCE_INCOMPLETE,
                        override_detail="Missing",
                        corrected_outcome={},
                    ),
                )
            elif final_state == PilotCaseState.ESCALATED:
                approval_svc.escalate(
                    case.id,
                    REVIEWER,
                    EscalationRequest(
                        escalation_route=EscalationRoute.COMMERCIAL_LEAD,
                        escalation_reason="Needs lead",
                    ),
                )

        summary = reporting_svc.get_pilot_summary_report(TENANT)
        assert summary.total_cases == 5
        assert summary.cases_by_state["approved"] == 2
        assert summary.cases_by_state["overridden"] == 1
        assert summary.cases_by_state["escalated"] == 1

        breakdown = reporting_svc.get_workflow_breakdown_report(TENANT)
        assert len(breakdown) == 3

        override_report = reporting_svc.get_override_escalation_report(TENANT)
        assert override_report.total_overrides == 1
        assert override_report.total_escalations == 1
