"""Tests for the case state machine service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.pilot_case import PilotCaseState
from app.services.state_machine import (
    VALID_TRANSITIONS,
    CaseStateMachineService,
    InvalidTransitionError,
)


@pytest.fixture
def sm() -> CaseStateMachineService:
    return CaseStateMachineService()


class TestValidTransitions:
    def test_created_can_go_to_evidence_ready(self, sm: CaseStateMachineService):
        assert sm.validate_transition(PilotCaseState.CREATED, PilotCaseState.EVIDENCE_READY)

    def test_created_cannot_go_to_approved(self, sm: CaseStateMachineService):
        assert not sm.validate_transition(PilotCaseState.CREATED, PilotCaseState.APPROVED)

    def test_evidence_ready_to_workflow_executed(self, sm: CaseStateMachineService):
        assert sm.validate_transition(PilotCaseState.EVIDENCE_READY, PilotCaseState.WORKFLOW_EXECUTED)

    def test_workflow_executed_to_validation_completed(self, sm: CaseStateMachineService):
        assert sm.validate_transition(PilotCaseState.WORKFLOW_EXECUTED, PilotCaseState.VALIDATION_COMPLETED)

    def test_validation_completed_to_under_review(self, sm: CaseStateMachineService):
        assert sm.validate_transition(PilotCaseState.VALIDATION_COMPLETED, PilotCaseState.UNDER_REVIEW)

    def test_under_review_to_approved(self, sm: CaseStateMachineService):
        assert sm.validate_transition(PilotCaseState.UNDER_REVIEW, PilotCaseState.APPROVED)

    def test_under_review_to_overridden(self, sm: CaseStateMachineService):
        assert sm.validate_transition(PilotCaseState.UNDER_REVIEW, PilotCaseState.OVERRIDDEN)

    def test_under_review_to_escalated(self, sm: CaseStateMachineService):
        assert sm.validate_transition(PilotCaseState.UNDER_REVIEW, PilotCaseState.ESCALATED)

    def test_approved_to_exported(self, sm: CaseStateMachineService):
        assert sm.validate_transition(PilotCaseState.APPROVED, PilotCaseState.EXPORTED)

    def test_overridden_can_return_to_review(self, sm: CaseStateMachineService):
        assert sm.validate_transition(PilotCaseState.OVERRIDDEN, PilotCaseState.UNDER_REVIEW)

    def test_escalated_can_return_to_review(self, sm: CaseStateMachineService):
        assert sm.validate_transition(PilotCaseState.ESCALATED, PilotCaseState.UNDER_REVIEW)

    def test_escalated_can_go_to_approved(self, sm: CaseStateMachineService):
        assert sm.validate_transition(PilotCaseState.ESCALATED, PilotCaseState.APPROVED)

    def test_closed_has_no_transitions(self, sm: CaseStateMachineService):
        valid = sm.get_valid_transitions(PilotCaseState.CLOSED)
        assert valid == []

    def test_every_state_can_reach_closed(self, sm: CaseStateMachineService):
        for state in PilotCaseState:
            if state == PilotCaseState.CLOSED:
                continue
            assert sm.validate_transition(state, PilotCaseState.CLOSED), f"{state} should be able to close"

    def test_all_states_have_transitions_defined(self):
        for state in PilotCaseState:
            assert state in VALID_TRANSITIONS


class TestTransitionExecution:
    def test_valid_transition_returns_record(self, sm: CaseStateMachineService):
        actor = uuid.uuid4()
        result = sm.transition(PilotCaseState.CREATED, PilotCaseState.EVIDENCE_READY, actor, reason="Evidence uploaded")
        assert result["from_state"] == PilotCaseState.CREATED
        assert result["to_state"] == PilotCaseState.EVIDENCE_READY
        assert result["actor_id"] == actor
        assert result["reason"] == "Evidence uploaded"
        assert "transitioned_at" in result

    def test_invalid_transition_raises(self, sm: CaseStateMachineService):
        with pytest.raises(InvalidTransitionError) as exc_info:
            sm.transition(PilotCaseState.CREATED, PilotCaseState.APPROVED, uuid.uuid4())
        assert "Invalid transition" in str(exc_info.value)
        assert "created" in str(exc_info.value)
        assert "approved" in str(exc_info.value)

    def test_transition_with_metadata(self, sm: CaseStateMachineService):
        result = sm.transition(
            PilotCaseState.UNDER_REVIEW,
            PilotCaseState.OVERRIDDEN,
            uuid.uuid4(),
            metadata={"override_reason": "commercial_truth_differs"},
        )
        assert result["metadata"]["override_reason"] == "commercial_truth_differs"

    def test_closed_to_anything_raises(self, sm: CaseStateMachineService):
        with pytest.raises(InvalidTransitionError):
            sm.transition(PilotCaseState.CLOSED, PilotCaseState.CREATED, uuid.uuid4())


class TestGetValidTransitions:
    def test_created_transitions(self, sm: CaseStateMachineService):
        valid = sm.get_valid_transitions(PilotCaseState.CREATED)
        assert PilotCaseState.EVIDENCE_READY in valid
        assert PilotCaseState.CLOSED in valid
        assert len(valid) == 2

    def test_under_review_transitions(self, sm: CaseStateMachineService):
        valid = sm.get_valid_transitions(PilotCaseState.UNDER_REVIEW)
        assert PilotCaseState.APPROVED in valid
        assert PilotCaseState.OVERRIDDEN in valid
        assert PilotCaseState.ESCALATED in valid
        assert PilotCaseState.CLOSED in valid
        assert len(valid) == 4
