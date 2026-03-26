"""Tests for the approval, override, and escalation service."""

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
from app.schemas.pilot_case import PilotCaseCreate, PilotCaseState
from app.services.approval import ApprovalService
from app.services.pilot_cases import PilotCaseService
from app.services.state_machine import InvalidTransitionError

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000099")
USER = uuid.UUID("00000000-0000-0000-0000-000000000098")


@pytest.fixture
def services():
    case_svc = PilotCaseService()
    approval_svc = ApprovalService(case_svc)
    return case_svc, approval_svc


def _create_case_at_review(case_svc: PilotCaseService) -> uuid.UUID:
    case = case_svc.create_case(
        TENANT, PilotCaseCreate(title="Test", workflow_type="margin_diagnosis"), USER
    )
    case_svc.transition_state(case.id, PilotCaseState.EVIDENCE_READY, USER)
    case_svc.transition_state(case.id, PilotCaseState.WORKFLOW_EXECUTED, USER)
    case_svc.transition_state(case.id, PilotCaseState.VALIDATION_COMPLETED, USER)
    case_svc.transition_state(case.id, PilotCaseState.UNDER_REVIEW, USER)
    return case.id


class TestApprove:
    def test_approve_case(self, services):
        case_svc, approval_svc = services
        case_id = _create_case_at_review(case_svc)
        result = approval_svc.approve(
            case_id, USER, ApprovalRequest(reasoning="Correct determination")
        )
        assert result.approved_by == USER
        assert result.reasoning == "Correct determination"
        case = case_svc.get_case(case_id)
        assert case.state == PilotCaseState.APPROVED

    def test_approve_with_business_notes(self, services):
        case_svc, approval_svc = services
        case_id = _create_case_at_review(case_svc)
        result = approval_svc.approve(
            case_id,
            USER,
            ApprovalRequest(
                reasoning="Verified",
                business_impact_notes="Saves 15K monthly",
            ),
        )
        assert result.business_impact_notes == "Saves 15K monthly"

    def test_approve_invalid_state(self, services):
        case_svc, approval_svc = services
        case = case_svc.create_case(
            TENANT, PilotCaseCreate(title="Test", workflow_type="test"), USER
        )
        with pytest.raises(InvalidTransitionError):
            approval_svc.approve(case.id, USER, ApprovalRequest(reasoning="Test"))


class TestOverride:
    def test_override_case(self, services):
        case_svc, approval_svc = services
        case_id = _create_case_at_review(case_svc)
        result = approval_svc.override(
            case_id,
            USER,
            OverrideRequest(
                override_reason=OverrideReason.MODEL_ACCEPTABLE_COMMERCIAL_DIFFERS,
                override_detail="Contract clause 4.2 applies differently in this scenario",
                corrected_outcome={"verdict": "not_billable", "reason": "clause_4_2_override"},
            ),
        )
        assert result.override_reason == OverrideReason.MODEL_ACCEPTABLE_COMMERCIAL_DIFFERS
        assert result.corrected_outcome["verdict"] == "not_billable"
        case = case_svc.get_case(case_id)
        assert case.state == PilotCaseState.OVERRIDDEN

    def test_override_evidence_incomplete(self, services):
        case_svc, approval_svc = services
        case_id = _create_case_at_review(case_svc)
        result = approval_svc.override(
            case_id,
            USER,
            OverrideRequest(
                override_reason=OverrideReason.EVIDENCE_INCOMPLETE,
                override_detail="Missing field completion certificate",
            ),
        )
        assert result.override_reason == OverrideReason.EVIDENCE_INCOMPLETE

    def test_override_all_reasons(self, services):
        for reason in OverrideReason:
            case_svc, approval_svc = services
            case_id = _create_case_at_review(case_svc)
            result = approval_svc.override(
                case_id,
                USER,
                OverrideRequest(override_reason=reason, override_detail=f"Testing {reason.value}"),
            )
            assert result.override_reason == reason


class TestEscalate:
    def test_escalate_case(self, services):
        case_svc, approval_svc = services
        case_id = _create_case_at_review(case_svc)
        result = approval_svc.escalate(
            case_id,
            USER,
            EscalationRequest(
                escalation_route=EscalationRoute.COMMERCIAL_LEAD,
                escalation_reason="Requires commercial lead sign-off for high-value contract",
            ),
        )
        assert result.escalation_route == EscalationRoute.COMMERCIAL_LEAD
        case = case_svc.get_case(case_id)
        assert case.state == PilotCaseState.ESCALATED

    def test_escalate_to_governance(self, services):
        case_svc, approval_svc = services
        case_id = _create_case_at_review(case_svc)
        result = approval_svc.escalate(
            case_id,
            USER,
            EscalationRequest(
                escalation_route=EscalationRoute.GOVERNANCE_BOARD,
                escalation_reason="Policy exception required",
                urgency="urgent",
            ),
        )
        assert result.escalation_route == EscalationRoute.GOVERNANCE_BOARD
        assert result.urgency == "urgent"

    def test_escalate_all_routes(self, services):
        for route in EscalationRoute:
            case_svc, approval_svc = services
            case_id = _create_case_at_review(case_svc)
            result = approval_svc.escalate(
                case_id,
                USER,
                EscalationRequest(
                    escalation_route=route, escalation_reason=f"Testing {route.value}"
                ),
            )
            assert result.escalation_route == route


class TestGetRecords:
    def test_get_approvals(self, services):
        case_svc, approval_svc = services
        case_id = _create_case_at_review(case_svc)
        approval_svc.approve(case_id, USER, ApprovalRequest(reasoning="OK"))
        approvals = approval_svc.get_approvals(case_id)
        assert len(approvals) == 1

    def test_get_overrides(self, services):
        case_svc, approval_svc = services
        case_id = _create_case_at_review(case_svc)
        approval_svc.override(
            case_id,
            USER,
            OverrideRequest(override_reason=OverrideReason.OTHER, override_detail="Test"),
        )
        overrides = approval_svc.get_overrides(case_id)
        assert len(overrides) == 1

    def test_get_escalations(self, services):
        case_svc, approval_svc = services
        case_id = _create_case_at_review(case_svc)
        approval_svc.escalate(
            case_id,
            USER,
            EscalationRequest(
                escalation_route=EscalationRoute.DOMAIN_EXPERT, escalation_reason="Need expert"
            ),
        )
        escalations = approval_svc.get_escalations(case_id)
        assert len(escalations) == 1
