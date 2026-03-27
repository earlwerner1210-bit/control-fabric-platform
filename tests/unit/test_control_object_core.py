"""Tests for ControlObject lifecycle, guards, and construction."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.control_object import (
    ControlObject,
    ControlObjectCreate,
    build_control_object,
    supersede_object,
)
from app.core.errors import (
    ControlObjectFrozenError,
    ControlObjectStateError,
    InvalidControlObjectError,
)
from app.core.types import (
    AuditContext,
    ConfidenceScore,
    ControlObjectType,
    ControlProvenance,
    ControlState,
    EvidenceRef,
    PlaneType,
)

TENANT = uuid.uuid4()
AUDIT = AuditContext(actor="test", action="test", timestamp=datetime.now(UTC))


def _make_create(**overrides):
    defaults = dict(
        object_type=ControlObjectType.OBLIGATION,
        plane=PlaneType.COMMERCIAL,
        domain="contract_margin",
        label="Test Obligation",
    )
    defaults.update(overrides)
    return ControlObjectCreate(**defaults)


class TestControlObjectConstruction:
    def test_build_creates_draft(self):
        obj = build_control_object(TENANT, _make_create())
        assert obj.state == ControlState.DRAFT
        assert obj.tenant_id == TENANT
        assert obj.domain == "contract_margin"
        assert len(obj.audit_trail) == 1
        assert obj.audit_trail[0].action == "created"

    def test_build_rejects_empty_label(self):
        with pytest.raises(InvalidControlObjectError, match="label"):
            build_control_object(TENANT, _make_create(label=""))

    def test_build_rejects_empty_domain(self):
        with pytest.raises(InvalidControlObjectError, match="domain"):
            build_control_object(TENANT, _make_create(domain=""))

    def test_build_rejects_invalid_confidence(self):
        with pytest.raises(InvalidControlObjectError, match="Confidence"):
            build_control_object(TENANT, _make_create(confidence=1.5))

    def test_build_with_payload_and_tags(self):
        obj = build_control_object(
            TENANT,
            _make_create(payload={"rate": 100}, tags=["important"]),
        )
        assert obj.payload == {"rate": 100}
        assert "important" in obj.tags

    def test_build_preserves_provenance(self):
        prov = ControlProvenance(
            created_by="extractor",
            creation_method="deterministic",
            domain_pack="contract_margin",
        )
        obj = build_control_object(TENANT, _make_create(provenance=prov))
        assert obj.provenance.created_by == "extractor"
        assert obj.provenance.domain_pack == "contract_margin"

    def test_each_object_gets_unique_id(self):
        obj1 = build_control_object(TENANT, _make_create())
        obj2 = build_control_object(TENANT, _make_create())
        assert obj1.id != obj2.id


class TestControlObjectLifecycle:
    def test_draft_to_active(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        assert obj.state == ControlState.ACTIVE

    def test_active_to_enriched(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.enrich({"extra": "data"}, AUDIT)
        assert obj.state == ControlState.ENRICHED
        assert obj.payload["extra"] == "data"

    def test_active_to_frozen(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        assert obj.state == ControlState.FROZEN

    def test_enriched_to_frozen(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.enrich({"x": 1}, AUDIT)
        obj.freeze(AUDIT)
        assert obj.state == ControlState.FROZEN

    def test_frozen_to_reconciled(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        obj.mark_reconciled(AUDIT)
        assert obj.state == ControlState.RECONCILED

    def test_reconciled_to_actioned(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        obj.mark_reconciled(AUDIT)
        obj.mark_actioned(AUDIT)
        assert obj.state == ControlState.ACTIONED

    def test_frozen_to_disputed(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        obj.mark_disputed(AUDIT)
        assert obj.state == ControlState.DISPUTED

    def test_disputed_to_active(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        obj.mark_disputed(AUDIT)
        obj.activate(AUDIT)
        assert obj.state == ControlState.ACTIVE

    def test_active_to_superseded(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        new_id = uuid.uuid4()
        obj.supersede(new_id, AUDIT)
        assert obj.state == ControlState.SUPERSEDED
        assert obj.superseded_by == new_id

    def test_active_to_deprecated(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.deprecate(AUDIT)
        assert obj.state == ControlState.DEPRECATED

    def test_superseded_is_terminal(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.supersede(uuid.uuid4(), AUDIT)
        with pytest.raises(ControlObjectStateError):
            obj.activate(AUDIT)

    def test_deprecated_is_terminal(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.deprecate(AUDIT)
        with pytest.raises(ControlObjectStateError):
            obj.activate(AUDIT)

    def test_invalid_transition_raises(self):
        obj = build_control_object(TENANT, _make_create())
        with pytest.raises(ControlObjectStateError):
            obj.freeze(AUDIT)  # draft → frozen not valid


class TestControlObjectGuards:
    def test_frozen_rejects_enrich(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        with pytest.raises(ControlObjectFrozenError):
            obj.enrich({"x": 1}, AUDIT)

    def test_frozen_rejects_evidence(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        with pytest.raises(ControlObjectFrozenError):
            obj.attach_evidence(EvidenceRef(evidence_type="doc", source_label="test"))

    def test_is_mutable_false_when_frozen(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        assert obj.is_mutable
        obj.freeze(AUDIT)
        assert not obj.is_mutable

    def test_audit_trail_accumulates(self):
        obj = build_control_object(TENANT, _make_create())
        obj.activate(AUDIT)
        obj.enrich({"x": 1}, AUDIT)
        obj.freeze(AUDIT)
        assert len(obj.audit_trail) >= 4  # created + activate + enrich + freeze


class TestSupersede:
    def test_supersede_creates_new_version(self):
        original = build_control_object(TENANT, _make_create())
        original.activate(AUDIT)
        update = _make_create(label="Updated Obligation")
        new_obj = supersede_object(original, update, "test")
        assert new_obj.version == 2
        assert new_obj.derived_from == [original.id]
        assert original.state == ControlState.SUPERSEDED
        assert original.superseded_by == new_obj.id

    def test_supersede_preserves_tenant(self):
        original = build_control_object(TENANT, _make_create())
        original.activate(AUDIT)
        new_obj = supersede_object(original, _make_create(label="V2"), "test")
        assert new_obj.tenant_id == TENANT
