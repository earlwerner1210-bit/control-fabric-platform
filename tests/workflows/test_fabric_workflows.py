"""Tests for fabric-native workflows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.action.types import ActionMode, ActionType
from app.core.control_link import ControlLinkCreate
from app.core.control_object import ControlObjectCreate
from app.core.domain_integration import register_all_domain_packs
from app.core.fabric_service import ControlFabricService
from app.core.registry import FabricRegistry
from app.core.types import (
    ControlLinkType,
    ControlObjectType,
    ControlState,
    EvidenceRef,
    PlaneType,
)
from app.workflows.fabric_core.action_release_workflow import (
    GovernedActionReleaseWorkflow,
)
from app.workflows.fabric_core.consistency_workflow import (
    GraphConsistencyAuditWorkflow,
)
from app.workflows.fabric_core.enrichment_workflow import (
    ObjectEnrichmentWorkflow,
)
from app.workflows.fabric_core.reconciliation_workflow import (
    FabricReconciliationWorkflow,
)

TENANT = uuid.uuid4()


def _setup_fabric():
    registry = FabricRegistry()
    register_all_domain_packs(registry)
    return ControlFabricService(registry=registry)


def _create_cross_plane_objects(fabric: ControlFabricService):
    src = fabric.graph.create_object(
        TENANT,
        ControlObjectCreate(
            object_type=ControlObjectType.RATE_CARD,
            plane=PlaneType.COMMERCIAL,
            domain="contract_margin",
            label="Rate Card",
            payload={"rate": 100.0},
            evidence=[EvidenceRef(evidence_type="doc", source_label="contract.pdf")],
        ),
    )
    tgt = fabric.graph.create_object(
        TENANT,
        ControlObjectCreate(
            object_type=ControlObjectType.WORK_ORDER,
            plane=PlaneType.FIELD,
            domain="contract_margin",
            label="Work Order",
            payload={"rate": 150.0},
            evidence=[EvidenceRef(evidence_type="doc", source_label="wo.pdf")],
        ),
    )
    fabric.graph.create_link(
        TENANT,
        ControlLinkCreate(
            source_id=src.id,
            target_id=tgt.id,
            link_type=ControlLinkType.FULFILLS,
        ),
    )
    return src, tgt


class TestReconciliationWorkflow:
    def test_freeze_and_reconcile(self):
        fabric = _setup_fabric()
        src, tgt = _create_cross_plane_objects(fabric)
        wf = FabricReconciliationWorkflow(fabric)
        result = wf.run(TENANT, "commercial", "field", "contract_margin")
        assert result["frozen_count"] >= 2
        assert result["reconciliation"]["mismatch_count"] >= 1
        assert result["reconciliation"]["decision_hash"] != ""
        assert result["consistency"]["is_consistent"]


class TestActionReleaseWorkflow:
    def test_validate_propose_auto_release(self):
        fabric = _setup_fabric()
        src, tgt = _create_cross_plane_objects(fabric)
        # Need to freeze + reconcile first for clean state
        fabric.graph.freeze_object(src.id)
        fabric.graph.freeze_object(tgt.id)

        wf = GovernedActionReleaseWorkflow(fabric)
        result = wf.run(
            TENANT,
            "rate_correction",
            [str(src.id)],
            mode="auto_release",
        )
        assert result["status"] == "released"

    def test_validation_failure_stops_workflow(self):
        fabric = _setup_fabric()
        # Create object with low confidence → should fail validation
        obj = fabric.graph.create_object(
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
        wf = GovernedActionReleaseWorkflow(fabric)
        result = wf.run(TENANT, "credit_note", [str(obj.id)])
        assert result["status"] == "validation_failed"


class TestEnrichmentWorkflow:
    def test_enrich_object_with_evidence_and_links(self):
        fabric = _setup_fabric()
        src, tgt = _create_cross_plane_objects(fabric)
        wf = ObjectEnrichmentWorkflow(fabric)
        result = wf.run(
            TENANT,
            src.id,
            {"additional_info": "updated rate", "new_rate": 105.0},
            evidence=[
                {"evidence_type": "amendment", "source_label": "amendment.pdf"},
            ],
            link_targets=[
                {"target_id": str(tgt.id), "link_type": "correlates_with"},
            ],
        )
        assert result["status"] == "enriched"
        assert result["evidence_attached"] == 1
        assert result["links_created"] == 1

    def test_enrich_missing_object(self):
        fabric = _setup_fabric()
        wf = ObjectEnrichmentWorkflow(fabric)
        result = wf.run(TENANT, uuid.uuid4(), {"x": 1})
        assert result["status"] == "error"


class TestConsistencyWorkflow:
    def test_full_graph_audit(self):
        fabric = _setup_fabric()
        src, tgt = _create_cross_plane_objects(fabric)
        wf = GraphConsistencyAuditWorkflow(fabric)
        result = wf.run(TENANT)
        assert result["full_report"]["total_objects"] >= 2
        assert "commercial" in result["plane_reports"]
        assert "field" in result["plane_reports"]
        assert "service" in result["plane_reports"]

    def test_contradictions_reported(self):
        fabric = _setup_fabric()
        a = fabric.graph.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="test",
                label="A",
            ),
        )
        b = fabric.graph.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="test",
                label="B",
            ),
        )
        fabric.graph.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id,
                target_id=b.id,
                link_type=ControlLinkType.CONTRADICTS,
            ),
        )
        wf = GraphConsistencyAuditWorkflow(fabric)
        result = wf.run(TENANT)
        assert result["contradiction_count"] == 1
