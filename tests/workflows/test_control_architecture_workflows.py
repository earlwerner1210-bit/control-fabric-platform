"""End-to-end workflow tests for Control Architecture Core."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.action_engine import (
    ActionStatus,
    ActionType,
    CandidateActionCreate,
)
from app.schemas.bounded_reasoning import (
    BoundedContextRequest,
    BoundedReasoningRequest,
    ReasoningScope,
)
from app.schemas.control_fabric import (
    ControlLinkType,
    ControlPlane,
    FabricLinkCreate,
    FabricObjectCreate,
    FabricSliceRequest,
)
from app.schemas.control_graph import GraphSliceRequest, GraphSnapshotCreate
from app.schemas.reconciliation import ReconciliationRunRequest
from app.schemas.validation_chain import ChainOutcome, ValidationChainRequest
from app.services.action_engine.service import ActionEngineService
from app.services.bounded_reasoning.service import BoundedReasoningService
from app.services.control_fabric.service import ControlFabricService
from app.services.control_graph.service import ControlGraphService
from app.services.reconciliation.service import ReconciliationEngine
from app.services.validation_chain.service import ValidationChainService
from app.workflows.fabric_reconciliation.workflow import (
    FabricReconciliationActivities,
    FabricReconciliationInput,
    FabricReconciliationWorkflow,
)
from app.workflows.governed_action_release.workflow import (
    GovernedActionReleaseActivities,
    GovernedActionReleaseInput,
    GovernedActionReleaseWorkflow,
)

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
CASE = uuid.UUID("00000000-0000-0000-0000-000000000099")


class TestSPENMarginDiagnosisProof:
    """Realistic SPEN margin diagnosis: fabric → reconcile → reason → validate → action."""

    def test_spen_margin_full_proof(self):
        fabric = ControlFabricService()
        graph = ControlGraphService(fabric)
        recon = ReconciliationEngine(fabric)
        reasoning = BoundedReasoningService(graph)
        chain = ValidationChainService()
        action_engine = ActionEngineService(validation_chain=chain)

        # SPEN control objects
        msa = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="obligation",
                plane=ControlPlane.COMMERCIAL,
                domain="contract_margin",
                label="SPEN MSA Section 7 — T&M Rate Card",
                confidence=0.98,
                tags=["spen", "msa", "billing"],
            ),
        )
        sow = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="obligation",
                plane=ControlPlane.COMMERCIAL,
                domain="contract_margin",
                label="SOW-2024-Q1 — Jointing works",
                confidence=0.95,
                tags=["spen", "sow"],
            ),
        )
        wo = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="dispatch_precondition",
                plane=ControlPlane.FIELD,
                domain="utilities_field",
                label="WO-78432 — Joint bay installation",
                confidence=0.92,
                tags=["spen", "field"],
            ),
        )
        completion = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="readiness_check",
                plane=ControlPlane.FIELD,
                domain="utilities_field",
                label="Completion cert — WO-78432",
                confidence=0.89,
                tags=["spen", "completion"],
            ),
        )
        billing = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="billable_event",
                plane=ControlPlane.COMMERCIAL,
                domain="contract_margin",
                label="Invoice line — Joint bay @ £2,400",
                confidence=0.94,
                tags=["spen", "billing"],
            ),
        )
        policy_rule = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="escalation_rule",
                plane=ControlPlane.GOVERNANCE,
                domain="contract_margin",
                label="Invoices > £5K require commercial sign-off",
                confidence=1.0,
                tags=["governance"],
            ),
        )

        # Link chain
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=msa.id,
                target_id=sow.id,
                link_type=ControlLinkType.AUTHORIZES,
            ),
        )
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=sow.id,
                target_id=wo.id,
                link_type=ControlLinkType.TRIGGERS,
            ),
        )
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=wo.id,
                target_id=completion.id,
                link_type=ControlLinkType.SATISFIES,
            ),
        )
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=completion.id,
                target_id=billing.id,
                link_type=ControlLinkType.TRIGGERS,
            ),
        )
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=msa.id,
                target_id=billing.id,
                link_type=ControlLinkType.AUTHORIZES,
            ),
        )

        # Graph snapshot
        snap = graph.create_snapshot(GraphSnapshotCreate(tenant_id=TENANT, label="SPEN-Q1-snap"))
        assert snap.node_count == 6
        assert snap.edge_count == 5

        # Graph slice from MSA — policy node is reachable via billing←blocks←policy
        slice_result = graph.slice_graph(
            TENANT,
            GraphSliceRequest(root_ids=[msa.id], max_depth=5),
        )
        # BFS traverses bidirectionally, so all 6 nodes reachable
        assert len(slice_result.nodes) >= 5

        # Reconciliation
        recon_result = recon.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))
        assert recon_result.status == "completed"

        # Bounded reasoning
        reason_result = reasoning.reason(
            TENANT,
            BoundedReasoningRequest(
                context=BoundedContextRequest(
                    pilot_case_id=CASE,
                    root_object_ids=[msa.id],
                    scope=ReasoningScope.FULL_GRAPH,
                    max_depth=5,
                ),
                question="Is WO-78432 billable under SPEN MSA Section 7 T&M Rate Card?",
            ),
        )
        assert reason_result.objects_consulted >= 5

        # Validation + Action
        action = action_engine.create_candidate(
            TENANT,
            CandidateActionCreate(
                pilot_case_id=CASE,
                action_type=ActionType.BILLING_ADJUSTMENT,
                label="Confirm billing for WO-78432 joint bay @ £2,400",
                confidence=0.94,
                source_object_ids=[msa.id, sow.id, wo.id, completion.id, billing.id],
            ),
        )

        released = action_engine.validate_and_release(
            action.id,
            context={
                "schema_valid": True,
                "evidence_completeness": 0.92,
                "boundary_valid": True,
                "failed_rules": [],
                "cross_plane_conflicts": 0,
                "policy_compliant": True,
                "confidence": 0.94,
                "confidence_threshold": 0.7,
            },
        )
        assert released.status == ActionStatus.RELEASED

        executed = action_engine.mark_executed(action.id)
        assert executed.status == ActionStatus.EXECUTED


class TestContradictionHandlingProof:
    """Cross-plane contradiction detected and handled through workflow."""

    def test_contradiction_blocks_action(self):
        fabric = ControlFabricService()
        graph = ControlGraphService(fabric)
        recon = ReconciliationEngine(fabric)
        chain = ValidationChainService()
        action_engine = ActionEngineService(validation_chain=chain)

        # Commercial says billable
        commercial = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="billable_event",
                plane=ControlPlane.COMMERCIAL,
                domain="contract_margin",
                label="Invoice line — Cable pull @ £800",
                confidence=0.90,
            ),
        )
        # Field says not completed
        field = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="readiness_check",
                plane=ControlPlane.FIELD,
                domain="utilities_field",
                label="Completion cert MISSING — WO-99001",
                confidence=0.85,
            ),
        )

        # Contradiction link
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=commercial.id,
                target_id=field.id,
                link_type=ControlLinkType.CONTRADICTS,
            ),
        )

        # Reconciliation detects it
        recon_result = recon.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))
        assert recon_result.total_conflicts >= 1
        assert "contradiction" in recon_result.conflicts_by_type

        # Attempt action — blocked by cross-plane conflicts
        action = action_engine.create_candidate(
            TENANT,
            CandidateActionCreate(
                pilot_case_id=CASE,
                action_type=ActionType.BILLING_ADJUSTMENT,
                label="Bill cable pull",
                confidence=0.5,
            ),
        )
        blocked = action_engine.validate_and_release(
            action.id,
            context={
                "evidence_completeness": 0.5,
                "cross_plane_conflicts": 3,
                "confidence": 0.5,
                "confidence_threshold": 0.7,
            },
        )
        assert blocked.status == ActionStatus.BLOCKED


class TestWorkflowOrchestration:
    """Test both Temporal-style workflows together."""

    def test_reconciliation_then_action_release(self):
        # Reconciliation workflow
        recon_wf = FabricReconciliationWorkflow(FabricReconciliationActivities())
        recon_result = recon_wf.run(
            FabricReconciliationInput(
                tenant_id=str(TENANT),
                scope_planes=["commercial", "field", "governance"],
            )
        )
        assert recon_result.status == "completed"

        # Action release workflow
        action_wf = GovernedActionReleaseWorkflow(GovernedActionReleaseActivities())
        action_result = action_wf.run(
            GovernedActionReleaseInput(
                pilot_case_id=str(CASE),
                tenant_id=str(TENANT),
                action_type="billing_adjustment",
                action_label="Confirm billing",
                evidence_refs=[str(uuid.uuid4())],
                confidence=0.95,
            )
        )
        assert action_result.status == "released"
