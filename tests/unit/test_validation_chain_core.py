"""Tests for validation chain — 10 dimensions, gated outcomes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.control_link import ControlLinkCreate
from app.core.control_object import ControlObjectCreate
from app.core.errors import ValidationBypassAttempt
from app.core.graph.service import GraphService
from app.core.types import (
    AuditContext,
    ConfidenceScore,
    ControlLinkType,
    ControlObjectType,
    ControlState,
    EvidenceRef,
    PlaneType,
)
from app.core.validation.chain import ValidationChain
from app.core.validation.types import (
    ChainOutcome,
    DimensionVerdict,
    ValidationDimension,
)

TENANT = uuid.uuid4()
AUDIT = AuditContext(actor="test", action="test", timestamp=datetime.now(UTC))


def _make_validated_object(svc: GraphService, label: str = "Test"):
    """Create an object with evidence and links for passing validation."""
    obj = svc.create_object(
        TENANT,
        ControlObjectCreate(
            object_type=ControlObjectType.OBLIGATION,
            plane=PlaneType.COMMERCIAL,
            domain="test",
            label=label,
            evidence=[
                EvidenceRef(evidence_type="document", source_label="contract.pdf"),
            ],
        ),
    )
    return obj


class TestValidationChainExecution:
    def test_passes_with_good_object(self):
        svc = GraphService()
        obj = _make_validated_object(svc)
        # Give it a link so graph_completeness passes
        obj2 = _make_validated_object(svc, "Other")
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=obj.id,
                target_id=obj2.id,
                link_type=ControlLinkType.DERIVES_FROM,
            ),
        )
        chain = ValidationChain(svc)
        result = chain.validate(TENANT, [obj])
        assert result.outcome in (ChainOutcome.PASSED, ChainOutcome.PASSED_WITH_WARNINGS)
        assert result.is_actionable

    def test_fails_with_no_evidence(self):
        svc = GraphService()
        obj = svc.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="test",
                label="No Evidence",
            ),
        )
        chain = ValidationChain(svc)
        result = chain.validate(TENANT, [obj])
        assert result.outcome == ChainOutcome.FAILED
        assert result.failed_count >= 1
        evidence_step = next(
            (s for s in result.steps if s.dimension == ValidationDimension.EVIDENCE_SUFFICIENCY),
            None,
        )
        assert evidence_step is not None
        assert evidence_step.verdict == DimensionVerdict.FAIL

    def test_bypass_raises_on_empty_objects(self):
        svc = GraphService()
        chain = ValidationChain(svc)
        with pytest.raises(ValidationBypassAttempt):
            chain.validate(TENANT, [])

    def test_all_10_dimensions_checked(self):
        svc = GraphService()
        obj = _make_validated_object(svc)
        chain = ValidationChain(svc)
        result = chain.validate(TENANT, [obj])
        dimensions_checked = {s.dimension for s in result.steps}
        for dim in ValidationDimension:
            assert dim in dimensions_checked, f"Dimension {dim.value} not checked"

    def test_decision_hash_produced(self):
        svc = GraphService()
        obj = _make_validated_object(svc)
        chain = ValidationChain(svc)
        result = chain.validate(TENANT, [obj])
        assert result.decision_hash != ""

    def test_contradictory_evidence_fails(self):
        svc = GraphService()
        obj = _make_validated_object(svc)
        obj2 = _make_validated_object(svc, "Contradicted")
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=obj.id,
                target_id=obj2.id,
                link_type=ControlLinkType.CONTRADICTS,
            ),
        )
        chain = ValidationChain(svc)
        result = chain.validate(TENANT, [obj])
        contra_step = next(
            (s for s in result.steps if s.dimension == ValidationDimension.CONTRADICTORY_EVIDENCE),
            None,
        )
        assert contra_step is not None
        assert contra_step.verdict == DimensionVerdict.FAIL

    def test_low_confidence_fails(self):
        svc = GraphService()
        obj = svc.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="test",
                label="Low Confidence",
                confidence=0.1,
                evidence=[EvidenceRef(evidence_type="doc", source_label="x")],
            ),
        )
        chain = ValidationChain(svc)
        result = chain.validate(TENANT, [obj])
        conf_step = next(
            (s for s in result.steps if s.dimension == ValidationDimension.CONFIDENCE),
            None,
        )
        assert conf_step is not None
        assert conf_step.verdict == DimensionVerdict.FAIL

    def test_disputed_object_fails_reconciliation_state(self):
        svc = GraphService()
        obj = _make_validated_object(svc)
        obj.freeze(AUDIT)
        obj.mark_disputed(AUDIT)
        svc.repository.store_object(obj)
        chain = ValidationChain(svc)
        result = chain.validate(TENANT, [obj])
        recon_step = next(
            (s for s in result.steps if s.dimension == ValidationDimension.RECONCILIATION_STATE),
            None,
        )
        assert recon_step is not None
        assert recon_step.verdict == DimensionVerdict.FAIL
