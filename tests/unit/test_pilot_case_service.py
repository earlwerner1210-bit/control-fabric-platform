"""Tests for the pilot case management service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.pilot_case import (
    BusinessImpact,
    CaseSeverity,
    PilotCaseCreate,
    PilotCaseState,
)
from app.services.pilot_cases import PilotCaseService
from app.services.state_machine import InvalidTransitionError

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000099")
USER = uuid.UUID("00000000-0000-0000-0000-000000000098")


@pytest.fixture
def svc() -> PilotCaseService:
    return PilotCaseService()


def _make_case_data(**kwargs) -> PilotCaseCreate:
    defaults = {
        "title": "Test Margin Case",
        "workflow_type": "margin_diagnosis",
        "severity": CaseSeverity.HIGH,
        "business_impact": BusinessImpact.MAJOR,
    }
    defaults.update(kwargs)
    return PilotCaseCreate(**defaults)


class TestCreateCase:
    def test_create_returns_response(self, svc: PilotCaseService):
        case = svc.create_case(TENANT, _make_case_data(), USER)
        assert case.title == "Test Margin Case"
        assert case.state == PilotCaseState.CREATED
        assert case.tenant_id == TENANT
        assert case.workflow_type == "margin_diagnosis"

    def test_create_with_external_refs(self, svc: PilotCaseService):
        data = _make_case_data(external_refs={"ticket_id": "TK-001", "contract_ref": "MSA-2024"})
        case = svc.create_case(TENANT, data, USER)
        assert case.external_refs["ticket_id"] == "TK-001"

    def test_create_with_tags(self, svc: PilotCaseService):
        data = _make_case_data(tags=["pilot_wave_1", "spen"])
        case = svc.create_case(TENANT, data, USER)
        assert "pilot_wave_1" in case.tags

    def test_create_assigns_uuid(self, svc: PilotCaseService):
        case = svc.create_case(TENANT, _make_case_data(), USER)
        assert case.id is not None
        assert isinstance(case.id, uuid.UUID)


class TestListCases:
    def test_list_empty(self, svc: PilotCaseService):
        items, total = svc.list_cases(TENANT)
        assert total == 0
        assert items == []

    def test_list_returns_created(self, svc: PilotCaseService):
        svc.create_case(TENANT, _make_case_data(), USER)
        svc.create_case(TENANT, _make_case_data(title="Second"), USER)
        items, total = svc.list_cases(TENANT)
        assert total == 2

    def test_list_filter_by_state(self, svc: PilotCaseService):
        svc.create_case(TENANT, _make_case_data(), USER)
        items, total = svc.list_cases(TENANT, state=PilotCaseState.CREATED)
        assert total == 1
        items, total = svc.list_cases(TENANT, state=PilotCaseState.APPROVED)
        assert total == 0

    def test_list_filter_by_workflow_type(self, svc: PilotCaseService):
        svc.create_case(TENANT, _make_case_data(workflow_type="contract_compile"), USER)
        svc.create_case(TENANT, _make_case_data(workflow_type="margin_diagnosis"), USER)
        items, total = svc.list_cases(TENANT, workflow_type="contract_compile")
        assert total == 1
        assert items[0].workflow_type == "contract_compile"

    def test_list_pagination(self, svc: PilotCaseService):
        for i in range(5):
            svc.create_case(TENANT, _make_case_data(title=f"Case {i}"), USER)
        items, total = svc.list_cases(TENANT, page=1, page_size=2)
        assert total == 5
        assert len(items) == 2
        items2, _ = svc.list_cases(TENANT, page=2, page_size=2)
        assert len(items2) == 2

    def test_list_tenant_isolation(self, svc: PilotCaseService):
        other_tenant = uuid.uuid4()
        svc.create_case(TENANT, _make_case_data(), USER)
        svc.create_case(other_tenant, _make_case_data(), USER)
        items, total = svc.list_cases(TENANT)
        assert total == 1


class TestGetCase:
    def test_get_existing(self, svc: PilotCaseService):
        created = svc.create_case(TENANT, _make_case_data(), USER)
        fetched = svc.get_case(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_missing(self, svc: PilotCaseService):
        assert svc.get_case(uuid.uuid4()) is None


class TestArtifacts:
    def test_add_artifact(self, svc: PilotCaseService):
        case = svc.create_case(TENANT, _make_case_data(), USER)
        artifact = svc.add_artifact(case.id, "document", uuid.uuid4(), label="MSA Contract")
        assert artifact["artifact_type"] == "document"
        assert artifact["label"] == "MSA Contract"

    def test_add_artifact_missing_case(self, svc: PilotCaseService):
        with pytest.raises(ValueError, match="not found"):
            svc.add_artifact(uuid.uuid4(), "document", uuid.uuid4())


class TestAssignment:
    def test_assign_reviewer(self, svc: PilotCaseService):
        case = svc.create_case(TENANT, _make_case_data(), USER)
        reviewer = uuid.uuid4()
        assignment = svc.assign_reviewer(case.id, reviewer, USER, notes="Senior reviewer")
        assert assignment.reviewer_id == reviewer
        updated = svc.get_case(case.id)
        assert updated.assigned_reviewer_id == reviewer

    def test_assign_missing_case(self, svc: PilotCaseService):
        with pytest.raises(ValueError, match="not found"):
            svc.assign_reviewer(uuid.uuid4(), uuid.uuid4(), USER)


class TestTimeline:
    def test_timeline_has_creation_event(self, svc: PilotCaseService):
        case = svc.create_case(TENANT, _make_case_data(), USER)
        timeline = svc.get_timeline(case.id)
        assert len(timeline) >= 1
        assert timeline[0].event_type == "case_created"

    def test_timeline_includes_assignment(self, svc: PilotCaseService):
        case = svc.create_case(TENANT, _make_case_data(), USER)
        svc.assign_reviewer(case.id, uuid.uuid4(), USER)
        timeline = svc.get_timeline(case.id)
        events = [e.event_type for e in timeline]
        assert "reviewer_assigned" in events

    def test_timeline_includes_transitions(self, svc: PilotCaseService):
        case = svc.create_case(TENANT, _make_case_data(), USER)
        svc.transition_state(case.id, PilotCaseState.EVIDENCE_READY, USER)
        timeline = svc.get_timeline(case.id)
        events = [e.event_type for e in timeline]
        assert "state_transition" in events


class TestStateTransition:
    def test_valid_transition(self, svc: PilotCaseService):
        case = svc.create_case(TENANT, _make_case_data(), USER)
        result = svc.transition_state(case.id, PilotCaseState.EVIDENCE_READY, USER)
        assert result["to_state"] == PilotCaseState.EVIDENCE_READY
        updated = svc.get_case(case.id)
        assert updated.state == PilotCaseState.EVIDENCE_READY

    def test_invalid_transition_raises(self, svc: PilotCaseService):
        case = svc.create_case(TENANT, _make_case_data(), USER)
        with pytest.raises(InvalidTransitionError):
            svc.transition_state(case.id, PilotCaseState.APPROVED, USER)

    def test_full_lifecycle(self, svc: PilotCaseService):
        case = svc.create_case(TENANT, _make_case_data(), USER)
        svc.transition_state(case.id, PilotCaseState.EVIDENCE_READY, USER)
        svc.transition_state(case.id, PilotCaseState.WORKFLOW_EXECUTED, USER)
        svc.transition_state(case.id, PilotCaseState.VALIDATION_COMPLETED, USER)
        svc.transition_state(case.id, PilotCaseState.UNDER_REVIEW, USER)
        svc.transition_state(case.id, PilotCaseState.APPROVED, USER)
        svc.transition_state(case.id, PilotCaseState.EXPORTED, USER)
        svc.transition_state(case.id, PilotCaseState.CLOSED, USER)
        final = svc.get_case(case.id)
        assert final.state == PilotCaseState.CLOSED

    def test_override_lifecycle(self, svc: PilotCaseService):
        case = svc.create_case(TENANT, _make_case_data(), USER)
        svc.transition_state(case.id, PilotCaseState.EVIDENCE_READY, USER)
        svc.transition_state(case.id, PilotCaseState.WORKFLOW_EXECUTED, USER)
        svc.transition_state(case.id, PilotCaseState.VALIDATION_COMPLETED, USER)
        svc.transition_state(case.id, PilotCaseState.UNDER_REVIEW, USER)
        svc.transition_state(
            case.id, PilotCaseState.OVERRIDDEN, USER, reason="Commercial truth differs"
        )
        updated = svc.get_case(case.id)
        assert updated.state == PilotCaseState.OVERRIDDEN

    def test_escalation_lifecycle(self, svc: PilotCaseService):
        case = svc.create_case(TENANT, _make_case_data(), USER)
        svc.transition_state(case.id, PilotCaseState.EVIDENCE_READY, USER)
        svc.transition_state(case.id, PilotCaseState.WORKFLOW_EXECUTED, USER)
        svc.transition_state(case.id, PilotCaseState.VALIDATION_COMPLETED, USER)
        svc.transition_state(case.id, PilotCaseState.UNDER_REVIEW, USER)
        svc.transition_state(case.id, PilotCaseState.ESCALATED, USER)
        svc.transition_state(case.id, PilotCaseState.UNDER_REVIEW, USER)
        svc.transition_state(case.id, PilotCaseState.APPROVED, USER)
        final = svc.get_case(case.id)
        assert final.state == PilotCaseState.APPROVED

    def test_transition_missing_case(self, svc: PilotCaseService):
        with pytest.raises(ValueError, match="not found"):
            svc.transition_state(uuid.uuid4(), PilotCaseState.EVIDENCE_READY, USER)
