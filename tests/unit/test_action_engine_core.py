"""Tests for action engine — evidence gating, validation gating, modes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.action.engine import ActionEngine
from app.core.action.manifest import build_manifest
from app.core.action.types import (
    ActionMode,
    ActionStatus,
    ActionType,
)
from app.core.control_link import ControlLinkCreate
from app.core.control_object import ControlObjectCreate
from app.core.errors import (
    ActionWithoutEvidenceError,
    ActionWithoutValidationError,
)
from app.core.graph.service import GraphService
from app.core.types import (
    AuditContext,
    ControlLinkType,
    ControlObjectId,
    ControlObjectType,
    ControlState,
    EvidenceRef,
    PlaneType,
)
from app.core.validation.chain import ValidationChain

TENANT = uuid.uuid4()
AUDIT = AuditContext(actor="test", action="test", timestamp=datetime.now(UTC))


def _setup_action_engine():
    svc = GraphService()
    chain = ValidationChain(svc)
    engine = ActionEngine(svc, chain)
    return svc, chain, engine


def _create_actionable_object(svc: GraphService, label: str = "Obj"):
    obj = svc.create_object(
        TENANT,
        ControlObjectCreate(
            object_type=ControlObjectType.OBLIGATION,
            plane=PlaneType.COMMERCIAL,
            domain="test",
            label=label,
            evidence=[EvidenceRef(evidence_type="doc", source_label="contract.pdf")],
        ),
    )
    # Give it a link for graph completeness
    obj2 = svc.create_object(
        TENANT,
        ControlObjectCreate(
            object_type=ControlObjectType.RATE_CARD,
            plane=PlaneType.COMMERCIAL,
            domain="test",
            label=f"{label} Support",
            evidence=[EvidenceRef(evidence_type="doc", source_label="rate.pdf")],
        ),
    )
    svc.create_link(
        TENANT,
        ControlLinkCreate(
            source_id=obj.id,
            target_id=obj2.id,
            link_type=ControlLinkType.DERIVES_FROM,
        ),
    )
    return obj


class TestActionGating:
    def test_action_without_evidence_raises(self):
        svc, chain, engine = _setup_action_engine()
        obj = svc.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="test",
                label="No Evidence",
            ),
        )
        with pytest.raises(ActionWithoutEvidenceError):
            engine.propose_action(TENANT, ActionType.CREDIT_NOTE, [obj.id])

    def test_action_with_failed_validation_raises(self):
        svc, chain, engine = _setup_action_engine()
        # Object with evidence but low confidence
        obj = svc.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="test",
                label="Low Conf",
                confidence=0.1,
                evidence=[EvidenceRef(evidence_type="doc", source_label="x")],
            ),
        )
        with pytest.raises(ActionWithoutValidationError, match="failed"):
            engine.propose_action(TENANT, ActionType.CREDIT_NOTE, [obj.id])


class TestActionModes:
    def test_approval_gated_proposal(self):
        svc, chain, engine = _setup_action_engine()
        obj = _create_actionable_object(svc)
        proposal = engine.propose_action(
            TENANT,
            ActionType.CREDIT_NOTE,
            [obj.id],
            mode=ActionMode.APPROVAL_GATED,
        )
        assert proposal.status == ActionStatus.PENDING_APPROVAL
        assert not proposal.is_releasable

    def test_approve_and_release(self):
        svc, chain, engine = _setup_action_engine()
        obj = _create_actionable_object(svc)
        proposal = engine.propose_action(
            TENANT,
            ActionType.CREDIT_NOTE,
            [obj.id],
            mode=ActionMode.APPROVAL_GATED,
        )
        engine.approve_action(proposal.id, "manager@test.com")
        assert proposal.status == ActionStatus.APPROVED
        assert proposal.is_releasable

        released = engine.release_action(proposal.id)
        assert released.status == ActionStatus.RELEASED

    def test_auto_release_proposal(self):
        svc, chain, engine = _setup_action_engine()
        obj = _create_actionable_object(svc)
        proposal = engine.propose_action(
            TENANT,
            ActionType.RATE_CORRECTION,
            [obj.id],
            mode=ActionMode.AUTO_RELEASE,
        )
        assert proposal.status == ActionStatus.VALIDATED
        assert proposal.is_releasable

    def test_dry_run_not_releasable(self):
        svc, chain, engine = _setup_action_engine()
        obj = _create_actionable_object(svc)
        proposal = engine.propose_action(
            TENANT,
            ActionType.CREDIT_NOTE,
            [obj.id],
            mode=ActionMode.DRY_RUN,
        )
        assert proposal.status == ActionStatus.DRY_RUN_COMPLETE
        assert not proposal.is_releasable

    def test_reject_action(self):
        svc, chain, engine = _setup_action_engine()
        obj = _create_actionable_object(svc)
        proposal = engine.propose_action(TENANT, ActionType.CREDIT_NOTE, [obj.id])
        engine.reject_action(proposal.id, "Not justified")
        assert proposal.status == ActionStatus.REJECTED
        assert not proposal.is_releasable


class TestActionManifest:
    def test_manifest_has_decision_hash(self):
        svc, chain, engine = _setup_action_engine()
        obj = _create_actionable_object(svc)
        proposal = engine.propose_action(TENANT, ActionType.CREDIT_NOTE, [obj.id])
        assert proposal.manifest.decision_hash != ""

    def test_manifest_contains_evidence(self):
        svc, chain, engine = _setup_action_engine()
        obj = _create_actionable_object(svc)
        proposal = engine.propose_action(TENANT, ActionType.CREDIT_NOTE, [obj.id])
        assert len(proposal.manifest.evidence_refs) >= 1

    def test_build_manifest_standalone(self):
        from app.core.control_object import build_control_object

        obj = build_control_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="test",
                label="Manifest Test",
                evidence=[EvidenceRef(evidence_type="doc", source_label="x")],
            ),
        )
        manifest = build_manifest(TENANT, ActionType.CREDIT_NOTE, [obj])
        assert len(manifest.target_object_ids) == 1
        assert manifest.decision_hash != ""
