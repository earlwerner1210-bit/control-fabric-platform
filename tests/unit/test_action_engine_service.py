"""Tests for the Action Engine Service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.action_engine import (
    ActionBlockRequest,
    ActionReleaseRequest,
    ActionStatus,
    ActionType,
    CandidateActionCreate,
)
from app.schemas.validation_chain import ValidationStage
from app.services.action_engine.service import ActionEngineService
from app.services.validation_chain.service import ValidationChainService

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
CASE = uuid.UUID("00000000-0000-0000-0000-000000000099")
USER = uuid.UUID("00000000-0000-0000-0000-000000000010")


def _make_action(
    action_type: ActionType = ActionType.BILLING_ADJUSTMENT,
    label: str = "Test Action",
    confidence: float = 0.95,
) -> CandidateActionCreate:
    return CandidateActionCreate(
        pilot_case_id=CASE,
        action_type=action_type,
        label=label,
        confidence=confidence,
    )


class TestCandidateCreation:
    def test_create_candidate(self):
        svc = ActionEngineService()
        action = svc.create_candidate(TENANT, _make_action())
        assert action.id is not None
        assert action.status == ActionStatus.CANDIDATE
        assert action.action_type == ActionType.BILLING_ADJUSTMENT

    def test_get_action(self):
        svc = ActionEngineService()
        action = svc.create_candidate(TENANT, _make_action())
        fetched = svc.get_action(action.id)
        assert fetched is not None
        assert fetched.id == action.id

    def test_get_missing(self):
        svc = ActionEngineService()
        assert svc.get_action(uuid.uuid4()) is None

    def test_list_actions(self):
        svc = ActionEngineService()
        svc.create_candidate(TENANT, _make_action(label="A1"))
        svc.create_candidate(TENANT, _make_action(label="A2"))
        actions = svc.list_actions(CASE)
        assert len(actions) == 2

    def test_list_by_status(self):
        svc = ActionEngineService()
        svc.create_candidate(TENANT, _make_action())
        svc.create_candidate(TENANT, _make_action())
        results = svc.list_by_status(TENANT, ActionStatus.CANDIDATE)
        assert len(results) == 2


class TestReleaseWithoutChain:
    def test_validate_and_release_no_chain(self):
        svc = ActionEngineService()
        action = svc.create_candidate(TENANT, _make_action())
        released = svc.validate_and_release(action.id)
        assert released is not None
        assert released.status == ActionStatus.RELEASED
        assert released.released_at is not None

    def test_manual_release(self):
        svc = ActionEngineService()
        action = svc.create_candidate(TENANT, _make_action())
        released = svc.release(
            action.id,
            ActionReleaseRequest(released_by=USER, reasoning="Approved"),
        )
        assert released is not None
        assert released.status == ActionStatus.RELEASED


class TestReleaseWithChain:
    def test_chain_released(self):
        chain = ValidationChainService()
        svc = ActionEngineService(validation_chain=chain)
        action = svc.create_candidate(TENANT, _make_action())

        released = svc.validate_and_release(
            action.id,
            context={
                "schema_valid": True,
                "evidence_completeness": 1.0,
                "boundary_valid": True,
                "failed_rules": [],
                "cross_plane_conflicts": 0,
                "policy_compliant": True,
                "confidence": 0.95,
                "confidence_threshold": 0.7,
            },
        )
        assert released is not None
        assert released.status == ActionStatus.RELEASED
        assert released.validation_chain_id is not None

    def test_chain_blocked(self):
        chain = ValidationChainService()
        svc = ActionEngineService(validation_chain=chain)
        action = svc.create_candidate(TENANT, _make_action())

        blocked = svc.validate_and_release(
            action.id,
            context={
                "schema_valid": False,
            },
        )
        assert blocked is not None
        assert blocked.status == ActionStatus.BLOCKED
        assert blocked.blocking_reason is not None

    def test_chain_warn_released(self):
        chain = ValidationChainService()
        svc = ActionEngineService(validation_chain=chain)
        action = svc.create_candidate(TENANT, _make_action())

        result = svc.validate_and_release(
            action.id,
            context={
                "evidence_completeness": 0.6,
            },
        )
        assert result is not None
        assert result.status == ActionStatus.RELEASED


class TestBlocking:
    def test_block_action(self):
        svc = ActionEngineService()
        action = svc.create_candidate(TENANT, _make_action())
        blocked = svc.block(
            action.id,
            ActionBlockRequest(blocked_by=USER, blocking_reason="Policy violation"),
        )
        assert blocked is not None
        assert blocked.status == ActionStatus.BLOCKED

    def test_escalate_action(self):
        svc = ActionEngineService()
        action = svc.create_candidate(TENANT, _make_action())
        escalated = svc.block(
            action.id,
            ActionBlockRequest(
                blocked_by=USER,
                blocking_reason="Needs senior review",
                escalate=True,
            ),
        )
        assert escalated is not None
        assert escalated.status == ActionStatus.ESCALATED


class TestExecution:
    def test_mark_executed(self):
        svc = ActionEngineService()
        action = svc.create_candidate(TENANT, _make_action())
        svc.release(action.id, ActionReleaseRequest(released_by=USER))
        executed = svc.mark_executed(action.id)
        assert executed is not None
        assert executed.status == ActionStatus.EXECUTED
        assert executed.executed_at is not None

    def test_rollback(self):
        svc = ActionEngineService()
        action = svc.create_candidate(TENANT, _make_action())
        svc.release(action.id, ActionReleaseRequest(released_by=USER))
        svc.mark_executed(action.id)
        rolled = svc.rollback(action.id)
        assert rolled is not None
        assert rolled.status == ActionStatus.ROLLED_BACK


class TestSummary:
    def test_summary(self):
        svc = ActionEngineService()
        a1 = svc.create_candidate(TENANT, _make_action(label="A1"))
        a2 = svc.create_candidate(
            TENANT, _make_action(label="A2", action_type=ActionType.ESCALATION)
        )
        a3 = svc.create_candidate(TENANT, _make_action(label="A3"))

        svc.release(a1.id, ActionReleaseRequest(released_by=USER))
        svc.block(a2.id, ActionBlockRequest(blocked_by=USER, blocking_reason="No"))
        svc.release(a3.id, ActionReleaseRequest(released_by=USER))
        svc.mark_executed(a3.id)

        summary = svc.get_summary(TENANT)
        assert summary.total_candidates == 3
        assert summary.released == 1
        assert summary.blocked == 1
        assert summary.executed == 1
        assert summary.by_type["billing_adjustment"] == 2
        assert summary.by_type["escalation"] == 1
