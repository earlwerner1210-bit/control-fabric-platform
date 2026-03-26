"""Regression tests for pilot hardening with realistic fixtures."""

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
from app.schemas.pilot_case import BusinessImpact, CaseSeverity, PilotCaseCreate, PilotCaseState
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
from app.services.state_machine import InvalidTransitionError

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
ANALYST = uuid.UUID("00000000-0000-0000-0000-000000000010")
REVIEWER_A = uuid.UUID("00000000-0000-0000-0000-000000000020")
REVIEWER_B = uuid.UUID("00000000-0000-0000-0000-000000000021")


@pytest.fixture
def platform():
    case_svc = PilotCaseService()
    return {
        "case": case_svc,
        "approval": ApprovalService(case_svc),
        "review": ReviewService(),
        "evidence": EvidenceService(),
        "baseline": BaselineComparisonService(),
        "kpi": KpiService(),
        "feedback": FeedbackService(),
        "export": ExportService(),
    }


def _advance_to_review(case_svc, case_id):
    for state in [
        PilotCaseState.EVIDENCE_READY,
        PilotCaseState.WORKFLOW_EXECUTED,
        PilotCaseState.VALIDATION_COMPLETED,
        PilotCaseState.UNDER_REVIEW,
    ]:
        case_svc.transition_state(case_id, state, ANALYST)


class TestMarginDiagnosisApproved:
    """Regression: standard margin diagnosis case approved on first review."""

    def test_margin_approved_first_pass(self, platform):
        p = platform
        case = p["case"].create_case(TENANT, PilotCaseCreate(
            title="SPEN Margin Case #14",
            workflow_type="margin_diagnosis",
            severity=CaseSeverity.HIGH,
            business_impact=BusinessImpact.MAJOR,
            external_refs={"ticket_id": "TK-14", "contract_ref": "MSA-SPEN-2024"},
            tags=["pilot_wave_1", "spen", "margin"],
        ), ANALYST)

        p["case"].assign_reviewer(case.id, REVIEWER_A, ANALYST, notes="Margin specialist")
        p["evidence"].create_bundle(EvidenceBundleCreate(
            pilot_case_id=case.id,
            items=[
                EvidenceItem(evidence_type="document", source_id=uuid.uuid4(), source_label="MSA Contract v3.2"),
                EvidenceItem(evidence_type="document", source_id=uuid.uuid4(), source_label="Rate Card 2024-Q1"),
                EvidenceItem(evidence_type="chunk", source_id=uuid.uuid4(), confidence=0.94),
                EvidenceItem(evidence_type="control_object", source_id=uuid.uuid4(), source_label="Scope Line Item"),
            ],
            chain_stages=["contract_basis", "work_authorization", "execution_evidence", "billing_evidence"],
            completeness_score=0.96,
        ))
        p["evidence"].store_trace(
            case.id,
            documents=[{"object_type": "contract", "object_id": str(uuid.uuid4()), "label": "MSA"}],
            rules_fired=[
                {"rule_id": "R001", "result": "pass", "description": "Rate card match"},
                {"rule_id": "R002", "result": "pass", "description": "Scope coverage"},
            ],
        )
        p["baseline"].store_expectation(case.id, BaselineExpectation(
            expected_outcome="billable",
            expected_confidence=0.95,
            source="human_expert",
            expected_reasoning="Standard rate card with full scope coverage",
        ))

        _advance_to_review(p["case"], case.id)

        p["review"].create_review(case.id, ReviewRequest(
            model_output_summary={"verdict": "billable", "confidence": 0.94, "scope": "full"},
            validation_result_summary={"status": "passed", "rules": 8, "warnings": 0},
        ))
        p["review"].add_decision(case.id, REVIEWER_A, ReviewDecisionCreate(
            outcome=ReviewOutcome.ACCEPT,
            reasoning="Model output matches contract terms. Rate card verified.",
            confidence=0.96,
            business_impact_notes="Standard billing applies, ~£15K monthly",
        ))
        p["approval"].approve(case.id, REVIEWER_A, ApprovalRequest(
            reasoning="Fully verified margin case",
            business_impact_notes="Saves £15K monthly in margin leakage",
        ))

        comparison = p["baseline"].compare(case.id, platform_outcome="billable")
        assert comparison.match_type == BaselineMatchType.EXACT_MATCH

        p["kpi"].record_measurement(case.id, KpiMeasurementCreate(
            metric_name="time_to_decision", metric_value=1.8, metric_unit="hours",
        ))
        p["kpi"].record_measurement(case.id, KpiMeasurementCreate(
            metric_name="evidence_completeness", metric_value=0.96,
        ))

        export = p["export"].export_case(
            case.id, ANALYST,
            {"id": case.id, "title": "SPEN Margin Case #14", "workflow_type": "margin_diagnosis", "state": "approved"},
            CaseExportRequest(format=ExportFormat.MARKDOWN),
        )

        final = p["case"].get_case(case.id)
        assert final.state == PilotCaseState.APPROVED
        assert final.external_refs["contract_ref"] == "MSA-SPEN-2024"
        assert "markdown" in export.content


class TestMarginDiagnosisOverridden:
    """Regression: margin case where model is wrong, reviewer overrides."""

    def test_margin_overridden(self, platform):
        p = platform
        case = p["case"].create_case(TENANT, PilotCaseCreate(
            title="SPEN Margin Override #7",
            workflow_type="margin_diagnosis",
            severity=CaseSeverity.HIGH,
            tags=["pilot_wave_1", "override"],
        ), ANALYST)

        p["baseline"].store_expectation(case.id, BaselineExpectation(
            expected_outcome="not_billable",
            source="human_expert",
            expected_reasoning="Clause 4.2 exception applies",
        ))

        _advance_to_review(p["case"], case.id)

        p["review"].create_review(case.id, ReviewRequest(
            model_output_summary={"verdict": "billable", "confidence": 0.78},
        ))
        p["review"].add_decision(case.id, REVIEWER_A, ReviewDecisionCreate(
            outcome=ReviewOutcome.REJECT,
            reasoning="Model missed clause 4.2 exception",
        ))

        p["approval"].override(case.id, REVIEWER_A, OverrideRequest(
            override_reason=OverrideReason.MODEL_ACCEPTABLE_COMMERCIAL_DIFFERS,
            override_detail="Clause 4.2 exception makes this non-billable",
            corrected_outcome={"verdict": "not_billable", "reason": "clause_4_2_exception"},
        ))

        comparison = p["baseline"].compare(
            case.id,
            platform_outcome="billable",
            reviewer_outcome="not_billable",
        )
        assert comparison.match_type == BaselineMatchType.EXACT_MATCH

        p["feedback"].submit_feedback(case.id, REVIEWER_A, FeedbackEntryCreate(
            category=FeedbackCategory.RULE_ACCURACY,
            severity=FeedbackSeverity.HIGH,
            title="Clause 4.2 not modeled",
            description="Rule engine does not account for clause 4.2 exceptions",
            affected_component="rule_engine",
            suggested_improvement="Add clause 4.2 exception rule to margin_diagnosis pack",
        ))

        assert p["case"].get_case(case.id).state == PilotCaseState.OVERRIDDEN


class TestEscalatedFieldOpsCase:
    """Regression: field ops case escalated to governance then approved."""

    def test_escalation_to_governance(self, platform):
        p = platform
        case = p["case"].create_case(TENANT, PilotCaseCreate(
            title="Field Ops Governance Escalation",
            workflow_type="work_order_readiness",
            severity=CaseSeverity.CRITICAL,
            business_impact=BusinessImpact.SEVERE,
        ), ANALYST)

        _advance_to_review(p["case"], case.id)

        p["review"].create_review(case.id, ReviewRequest())
        p["review"].add_decision(case.id, REVIEWER_A, ReviewDecisionCreate(
            outcome=ReviewOutcome.ESCALATE,
            reasoning="Policy exception required for non-standard work order",
        ))

        p["approval"].escalate(case.id, REVIEWER_A, EscalationRequest(
            escalation_route=EscalationRoute.GOVERNANCE_BOARD,
            escalation_reason="Non-standard work order requires governance sign-off",
            urgency="urgent",
        ))
        assert p["case"].get_case(case.id).state == PilotCaseState.ESCALATED

        # Governance resolves, return to review
        p["case"].transition_state(case.id, PilotCaseState.UNDER_REVIEW, ANALYST)
        p["review"].add_decision(case.id, REVIEWER_B, ReviewDecisionCreate(
            outcome=ReviewOutcome.ACCEPT,
            reasoning="Governance approved exception",
            confidence=0.99,
        ))
        p["approval"].approve(case.id, REVIEWER_B, ApprovalRequest(
            reasoning="Governance-approved exception case",
        ))

        assert p["case"].get_case(case.id).state == PilotCaseState.APPROVED
        summary = p["review"].get_summary(case.id)
        assert summary.total_decisions == 2


class TestCannotApproveWithoutReview:
    """Regression: ensure state machine prevents skipping review."""

    def test_cannot_jump_to_approved(self, platform):
        p = platform
        case = p["case"].create_case(TENANT, PilotCaseCreate(
            title="Skip Test", workflow_type="test",
        ), ANALYST)
        with pytest.raises(InvalidTransitionError):
            p["case"].transition_state(case.id, PilotCaseState.APPROVED, ANALYST)

    def test_cannot_approve_from_evidence_ready(self, platform):
        p = platform
        case = p["case"].create_case(TENANT, PilotCaseCreate(
            title="Skip Test 2", workflow_type="test",
        ), ANALYST)
        p["case"].transition_state(case.id, PilotCaseState.EVIDENCE_READY, ANALYST)
        with pytest.raises(InvalidTransitionError):
            p["case"].transition_state(case.id, PilotCaseState.APPROVED, ANALYST)


class TestMultiCasePilotReport:
    """Regression: pilot report across many cases."""

    def test_pilot_report_generation(self, platform):
        p = platform
        case_data = []
        for i in range(10):
            case = p["case"].create_case(TENANT, PilotCaseCreate(
                title=f"Batch Case {i}",
                workflow_type="margin_diagnosis" if i % 2 == 0 else "contract_compile",
            ), ANALYST)
            case_data.append({
                "id": case.id,
                "title": case.title,
                "state": "approved" if i < 6 else "overridden" if i < 8 else "escalated",
                "workflow_type": case.workflow_type,
            })

        report = p["export"].generate_pilot_report(case_data)
        assert report.total_cases == 10
        assert report.cases_by_state["approved"] == 6
        assert report.cases_by_state["overridden"] == 2
        assert report.cases_by_state["escalated"] == 2

        summary = p["kpi"].compute_summary(case_data)
        assert summary.total_cases == 10

        breakdown = p["kpi"].compute_workflow_breakdown(case_data)
        assert len(breakdown) == 2


class TestClosedCaseCannotTransition:
    """Regression: closed cases are truly terminal."""

    def test_closed_is_terminal(self, platform):
        p = platform
        case = p["case"].create_case(TENANT, PilotCaseCreate(title="Close Test", workflow_type="test"), ANALYST)
        p["case"].transition_state(case.id, PilotCaseState.CLOSED, ANALYST)
        with pytest.raises(InvalidTransitionError):
            p["case"].transition_state(case.id, PilotCaseState.CREATED, ANALYST)
        with pytest.raises(InvalidTransitionError):
            p["case"].transition_state(case.id, PilotCaseState.UNDER_REVIEW, ANALYST)


class TestTenantIsolation:
    """Regression: tenant isolation holds across all operations."""

    def test_cases_isolated_by_tenant(self, platform):
        p = platform
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        p["case"].create_case(tenant_a, PilotCaseCreate(title="T-A", workflow_type="test"), ANALYST)
        p["case"].create_case(tenant_a, PilotCaseCreate(title="T-A-2", workflow_type="test"), ANALYST)
        p["case"].create_case(tenant_b, PilotCaseCreate(title="T-B", workflow_type="test"), ANALYST)

        items_a, total_a = p["case"].list_cases(tenant_a)
        items_b, total_b = p["case"].list_cases(tenant_b)
        assert total_a == 2
        assert total_b == 1
