"""Integration tests — end-to-end fabric workflows through all layers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.action.types import ActionMode, ActionType
from app.core.control_link import ControlLinkCreate
from app.core.control_object import ControlObjectCreate
from app.core.domain_integration import register_all_domain_packs
from app.core.fabric_service import ControlFabricService
from app.core.graph.service import GraphService
from app.core.reasoning.types import (
    ReasoningMode,
    ReasoningPolicy,
    ReasoningRequest,
)
from app.core.reconciliation.types import ReconciliationStatus
from app.core.registry import FabricRegistry
from app.core.types import (
    AuditContext,
    ControlLinkType,
    ControlObjectId,
    ControlObjectType,
    ControlState,
    EvidenceRef,
    PlaneType,
    ReasoningScope,
)

TENANT = uuid.uuid4()
AUDIT = AuditContext(actor="test", action="test", timestamp=datetime.now(UTC))


class TestFullFabricLifecycle:
    """Tests the complete lifecycle: create → enrich → link → freeze → reconcile → validate → action."""

    def test_contract_margin_lifecycle(self):
        registry = FabricRegistry()
        register_all_domain_packs(registry)
        fabric = ControlFabricService(registry=registry)

        # 1. Create commercial objects
        clause = fabric.graph.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                object_kind="extracted_clause",
                plane=PlaneType.COMMERCIAL,
                domain="contract_margin",
                label="Payment Terms Clause",
                payload={"clause_text": "Net 30", "clause_type": "payment", "rate": 100.0},
                evidence=[
                    EvidenceRef(evidence_type="clause_extraction", source_label="contract.pdf")
                ],
            ),
        )
        rate_card = fabric.graph.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.RATE_CARD,
                object_kind="rate_card_entry",
                plane=PlaneType.COMMERCIAL,
                domain="contract_margin",
                label="Standard Rate",
                payload={"rate": 100.0, "unit": "per_hour"},
                evidence=[
                    EvidenceRef(evidence_type="rate_extraction", source_label="contract.pdf")
                ],
            ),
        )

        # 2. Create field object
        work_order = fabric.graph.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.WORK_ORDER,
                object_kind="work_order",
                plane=PlaneType.FIELD,
                domain="contract_margin",
                label="WO-001",
                payload={"rate": 120.0, "quantity": 10, "work_order_id": "WO-001"},
                evidence=[EvidenceRef(evidence_type="field_report", source_label="wo-001.json")],
            ),
        )

        # 3. Link them
        fabric.graph.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=clause.id,
                target_id=rate_card.id,
                link_type=ControlLinkType.DERIVES_FROM,
            ),
        )
        fabric.graph.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=rate_card.id,
                target_id=work_order.id,
                link_type=ControlLinkType.FULFILLS,
            ),
        )

        # 4. Freeze
        fabric.graph.freeze_object(clause.id)
        fabric.graph.freeze_object(rate_card.id)
        fabric.graph.freeze_object(work_order.id)

        # 5. Reconcile
        recon = fabric.reconcile_planes(
            TENANT, PlaneType.COMMERCIAL, PlaneType.FIELD, "contract_margin"
        )
        assert recon.status == ReconciliationStatus.COMPLETED
        assert recon.decision_hash != ""
        # Rate deviation: 100 vs 120
        assert recon.score.mismatch_count >= 1

        # 6. Check consistency
        report = fabric.graph.check_consistency(TENANT)
        assert report.is_consistent

        # 7. Validate for action
        validation = fabric.validate_for_action(TENANT, [rate_card.id], "credit_note")
        assert validation.is_actionable

        # 8. Propose action
        proposal = fabric.propose_action(
            TENANT,
            ActionType.CREDIT_NOTE,
            [rate_card.id],
            mode=ActionMode.APPROVAL_GATED,
            description="Rate deviation credit note",
        )
        assert proposal.manifest.decision_hash != ""

        # 9. Approve and release
        fabric.action.approve_action(proposal.id, "manager@test.com")
        released = fabric.action.release_action(proposal.id)
        assert released.status.value == "released"

    def test_cross_domain_graph_traversal(self):
        registry = FabricRegistry()
        register_all_domain_packs(registry)
        fabric = ControlFabricService(registry=registry)

        # Create objects across 3 planes
        obligation = fabric.graph.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="contract_margin",
                label="SLA Obligation",
                evidence=[EvidenceRef(evidence_type="doc", source_label="sla.pdf")],
            ),
        )
        wo = fabric.graph.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.WORK_ORDER,
                plane=PlaneType.FIELD,
                domain="utilities_field",
                label="Field WO",
                evidence=[EvidenceRef(evidence_type="doc", source_label="wo.pdf")],
            ),
        )
        incident = fabric.graph.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.INCIDENT_STATE,
                plane=PlaneType.SERVICE,
                domain="telco_ops",
                label="INC-001",
                evidence=[EvidenceRef(evidence_type="doc", source_label="inc.json")],
            ),
        )

        # Link across planes
        fabric.graph.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=obligation.id,
                target_id=wo.id,
                link_type=ControlLinkType.FULFILLS,
            ),
        )
        fabric.graph.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=wo.id,
                target_id=incident.id,
                link_type=ControlLinkType.CORRELATES_WITH,
            ),
        )

        # Path traversal
        path = fabric.graph.find_path(obligation.id, incident.id)
        assert path is not None
        assert len(path) == 3

        # Graph slice from obligation
        objects, links = fabric.graph.get_graph_slice([obligation.id], max_depth=3)
        assert len(objects) == 3
        cross_plane_links = [l for l in links if l.is_cross_plane]
        assert len(cross_plane_links) >= 2


class TestFabricReasoningIntegration:
    def test_reasoning_with_graph_context(self):
        fabric = ControlFabricService()
        obj = fabric.graph.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="test",
                label="Test Obligation",
            ),
        )
        result = fabric.reason(
            ReasoningRequest(
                tenant_id=TENANT,
                scope=ReasoningScope.SINGLE_OBJECT,
                target_object_ids=[obj.id],
                question="Is this obligation valid?",
                policy=ReasoningPolicy(
                    allowed_scopes=[ReasoningScope.SINGLE_OBJECT],
                ),
            )
        )
        assert result.conclusion != ""
        assert result.decision_hash != ""
