"""Tests for the Reconciliation Engine."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.control_fabric import (
    ControlLinkType,
    ControlObjectStatus,
    ControlPlane,
    FabricLinkCreate,
    FabricObjectCreate,
)
from app.schemas.reconciliation import (
    ConflictResolution,
    ConflictResolutionRequest,
    ConflictType,
    ReconciliationRunRequest,
)
from app.services.control_fabric.service import ControlFabricService
from app.services.reconciliation.service import ReconciliationEngine

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _setup():
    fabric = ControlFabricService()
    engine = ReconciliationEngine(fabric)
    return fabric, engine


def _add_obj(
    fabric,
    label,
    plane=ControlPlane.COMMERCIAL,
    domain="contract_margin",
    control_type="obligation",
    confidence=1.0,
):
    return fabric.register_object(
        TENANT,
        FabricObjectCreate(
            control_type=control_type,
            plane=plane,
            domain=domain,
            label=label,
            confidence=confidence,
        ),
    )


def _link(fabric, src, tgt, lt=ControlLinkType.DEPENDS_ON):
    return fabric.link_objects(
        TENANT,
        FabricLinkCreate(source_id=src.id, target_id=tgt.id, link_type=lt),
    )


class TestContradictionDetection:
    def test_detects_contradiction(self):
        fabric, engine = _setup()
        a = _add_obj(fabric, "Billable", plane=ControlPlane.COMMERCIAL)
        b = _add_obj(fabric, "Not Billable", plane=ControlPlane.FIELD)
        _link(fabric, a, b, ControlLinkType.CONTRADICTS)

        result = engine.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))
        assert result.total_conflicts >= 1
        assert "contradiction" in result.conflicts_by_type

    def test_no_contradictions(self):
        fabric, engine = _setup()
        _add_obj(fabric, "A")
        _add_obj(fabric, "B")

        result = engine.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))
        assert result.conflicts_by_type.get("contradiction", 0) == 0


class TestMissingDependency:
    def test_detects_missing_dependency(self):
        fabric, engine = _setup()
        a = _add_obj(fabric, "A")
        missing_id = uuid.uuid4()
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=a.id,
                target_id=missing_id,
                link_type=ControlLinkType.DEPENDS_ON,
            ),
        )

        result = engine.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))
        assert result.total_conflicts >= 1
        assert "missing_dependency" in result.conflicts_by_type


class TestConfidenceDivergence:
    def test_detects_confidence_gap(self):
        fabric, engine = _setup()
        a = _add_obj(fabric, "HighConf", confidence=0.95)
        b = _add_obj(fabric, "LowConf", confidence=0.3)
        _link(fabric, a, b, ControlLinkType.SATISFIES)

        result = engine.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))
        assert "confidence_divergence" in result.conflicts_by_type


class TestAuthorizationGap:
    def test_detects_missing_authorization(self):
        fabric, engine = _setup()
        _add_obj(fabric, "Billing Action", control_type="billing_adjustment")

        result = engine.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))
        assert "authorization_gap" in result.conflicts_by_type
        assert "critical" in result.conflicts_by_severity


class TestDomainBoundaryViolation:
    def test_detects_cross_domain_authorization(self):
        fabric, engine = _setup()
        a = _add_obj(fabric, "Auth", domain="contract_margin")
        b = _add_obj(fabric, "Action", domain="telco_ops")
        _link(fabric, a, b, ControlLinkType.AUTHORIZES)

        result = engine.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))
        assert "domain_boundary_violation" in result.conflicts_by_type


class TestStaleReference:
    def test_detects_stale_reference(self):
        fabric, engine = _setup()
        a = _add_obj(fabric, "Active")
        b = _add_obj(fabric, "Old")
        _link(fabric, a, b, ControlLinkType.DEPENDS_ON)
        fabric.update_object_status(b.id, ControlObjectStatus.SUPERSEDED)

        result = engine.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))
        assert "stale_reference" in result.conflicts_by_type


class TestConflictResolution:
    def test_resolve_conflict(self):
        fabric, engine = _setup()
        a = _add_obj(fabric, "A")
        b = _add_obj(fabric, "B")
        _link(fabric, a, b, ControlLinkType.CONTRADICTS)

        run = engine.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))
        conflict_id = run.conflicts[0].id

        resolved = engine.resolve_conflict(
            conflict_id,
            ConflictResolutionRequest(
                resolution=ConflictResolution.MANUAL_REQUIRED,
                resolution_detail="Needs review",
            ),
        )
        assert resolved is not None
        assert resolved.resolution == ConflictResolution.MANUAL_REQUIRED


class TestReconciliationSummary:
    def test_summary(self):
        fabric, engine = _setup()
        a = _add_obj(fabric, "A")
        b = _add_obj(fabric, "B")
        _link(fabric, a, b, ControlLinkType.CONTRADICTS)

        engine.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))

        summary = engine.get_summary(TENANT)
        assert summary.total_runs == 1
        assert summary.total_conflicts >= 1
        assert summary.unresolved_conflicts >= 1

    def test_scope_filter(self):
        fabric, engine = _setup()
        _add_obj(fabric, "Com1", plane=ControlPlane.COMMERCIAL)
        _add_obj(fabric, "Field1", plane=ControlPlane.FIELD)

        result = engine.run_reconciliation(
            ReconciliationRunRequest(
                tenant_id=TENANT,
                scope_planes=[ControlPlane.COMMERCIAL],
            )
        )
        assert result.status == "completed"
