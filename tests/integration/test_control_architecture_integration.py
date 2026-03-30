"""Integration tests for the Control Architecture Core — end-to-end flows."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.action_engine import (
    ActionReleaseRequest,
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
)
from app.schemas.reconciliation import (
    ConflictType,
    ReconciliationRunRequest,
)
from app.schemas.validation_chain import (
    ChainOutcome,
    ValidationChainRequest,
)
from app.services.action_engine.service import ActionEngineService
from app.services.bounded_reasoning.service import BoundedReasoningService
from app.services.control_fabric.service import ControlFabricService
from app.services.control_graph.service import ControlGraphService
from app.services.reconciliation.service import ReconciliationEngine
from app.services.validation_chain.service import ValidationChainService

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
CASE = uuid.UUID("00000000-0000-0000-0000-000000000099")
USER = uuid.UUID("00000000-0000-0000-0000-000000000010")


class TestFabricToReconciliationFlow:
    """Fabric registration → graph → reconciliation → conflict detection."""

    def test_full_reconciliation_flow(self):
        fabric = ControlFabricService()
        engine = ReconciliationEngine(fabric)

        # Register objects across planes
        msa = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="obligation",
                plane=ControlPlane.COMMERCIAL,
                domain="contract_margin",
                label="MSA Clause 4.2 — Billable at T&M",
                confidence=0.95,
            ),
        )
        field_report = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="dispatch_precondition",
                plane=ControlPlane.FIELD,
                domain="utilities_field",
                label="Field Report: Work completed 2024-01-15",
                confidence=0.88,
            ),
        )
        billing_event = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="billable_event",
                plane=ControlPlane.COMMERCIAL,
                domain="contract_margin",
                label="Invoice #INV-2024-001",
                confidence=0.92,
            ),
        )
        policy = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="escalation_rule",
                plane=ControlPlane.GOVERNANCE,
                domain="contract_margin",
                label="Governance: Margin > $50K requires approval",
                confidence=1.0,
            ),
        )

        # Create links
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=msa.id,
                target_id=billing_event.id,
                link_type=ControlLinkType.AUTHORIZES,
            ),
        )
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=field_report.id,
                target_id=billing_event.id,
                link_type=ControlLinkType.SATISFIES,
            ),
        )
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=policy.id,
                target_id=billing_event.id,
                link_type=ControlLinkType.BLOCKS,
            ),
        )

        # Run reconciliation
        result = engine.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))
        assert result.status == "completed"
        assert result.total_objects_scanned == 4

        # Stats
        stats = fabric.get_stats(TENANT)
        assert stats.total_objects == 4
        assert stats.total_links == 3
        assert stats.objects_by_plane["commercial"] == 2
        assert stats.objects_by_plane["field"] == 1
        assert stats.objects_by_plane["governance"] == 1


class TestGraphSliceToReasoningFlow:
    """Fabric → graph slice → bounded reasoning."""

    def test_bounded_reasoning_from_graph(self):
        fabric = ControlFabricService()
        graph = ControlGraphService(fabric)
        reasoning = BoundedReasoningService(graph)

        # Build fabric
        contract = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="obligation",
                plane=ControlPlane.COMMERCIAL,
                domain="contract_margin",
                label="SPEN MSA — Rate Card A",
                confidence=0.97,
            ),
        )
        work = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="dispatch_precondition",
                plane=ControlPlane.FIELD,
                domain="utilities_field",
                label="Work Order WO-2024-100",
                confidence=0.91,
            ),
        )
        incident = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="incident_state",
                plane=ControlPlane.SERVICE,
                domain="telco_ops",
                label="INC-5555 — Cable fault",
                confidence=0.85,
            ),
        )

        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=contract.id,
                target_id=work.id,
                link_type=ControlLinkType.AUTHORIZES,
            ),
        )
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=work.id,
                target_id=incident.id,
                link_type=ControlLinkType.REFERENCES,
            ),
        )

        # Bounded reasoning
        result = reasoning.reason(
            TENANT,
            BoundedReasoningRequest(
                context=BoundedContextRequest(
                    root_object_ids=[contract.id],
                    scope=ReasoningScope.FULL_GRAPH,
                    max_depth=3,
                ),
                question="Is WO-2024-100 billable under SPEN MSA Rate Card A?",
            ),
        )
        assert result.objects_consulted == 3
        assert result.answer is not None
        assert len(result.context.planes_included) == 3


class TestValidationChainToActionFlow:
    """Validation chain → action engine release/block."""

    def test_action_released_through_chain(self):
        chain = ValidationChainService()
        engine = ActionEngineService(validation_chain=chain)

        action = engine.create_candidate(
            TENANT,
            CandidateActionCreate(
                pilot_case_id=CASE,
                action_type=ActionType.BILLING_ADJUSTMENT,
                label="Adjust margin for WO-2024-100",
                confidence=0.95,
            ),
        )

        released = engine.validate_and_release(
            action.id,
            context={
                "schema_valid": True,
                "evidence_completeness": 0.95,
                "boundary_valid": True,
                "failed_rules": [],
                "cross_plane_conflicts": 0,
                "policy_compliant": True,
                "confidence": 0.95,
                "confidence_threshold": 0.7,
            },
        )
        assert released.status == ActionStatus.RELEASED
        assert released.validation_chain_id is not None

        # Execute
        executed = engine.mark_executed(action.id)
        assert executed.status == ActionStatus.EXECUTED

    def test_action_blocked_by_chain(self):
        chain = ValidationChainService()
        engine = ActionEngineService(validation_chain=chain)

        action = engine.create_candidate(
            TENANT,
            CandidateActionCreate(
                pilot_case_id=CASE,
                action_type=ActionType.DISPATCH_ORDER,
                label="Dispatch crew",
                confidence=0.4,
            ),
        )

        blocked = engine.validate_and_release(
            action.id,
            context={
                "evidence_completeness": 0.2,
            },
        )
        assert blocked.status == ActionStatus.BLOCKED

    def test_summary_across_actions(self):
        chain = ValidationChainService()
        engine = ActionEngineService(validation_chain=chain)

        # Released action
        a1 = engine.create_candidate(
            TENANT,
            CandidateActionCreate(
                pilot_case_id=CASE,
                action_type=ActionType.BILLING_ADJUSTMENT,
                label="Billing 1",
            ),
        )
        engine.validate_and_release(a1.id, context={"evidence_completeness": 1.0})

        # Blocked action
        a2 = engine.create_candidate(
            TENANT,
            CandidateActionCreate(
                pilot_case_id=CASE,
                action_type=ActionType.CONTRACT_FLAG,
                label="Flag 1",
            ),
        )
        engine.validate_and_release(a2.id, context={"schema_valid": False})

        summary = engine.get_summary(TENANT)
        assert summary.total_candidates == 2
        assert summary.released == 1
        assert summary.blocked == 1


class TestFullControlArchitectureFlow:
    """End-to-end: fabric → graph → reconcile → reason → validate → action."""

    def test_full_flow(self):
        fabric = ControlFabricService()
        graph = ControlGraphService(fabric)
        recon = ReconciliationEngine(fabric)
        reasoning = BoundedReasoningService(graph)
        chain = ValidationChainService()
        action_engine = ActionEngineService(validation_chain=chain)

        # 1. Register control objects
        obligation = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="obligation",
                plane=ControlPlane.COMMERCIAL,
                domain="contract_margin",
                label="SPEN Clause 7.3 — Emergency rate",
                confidence=0.98,
            ),
        )
        evidence = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="billable_event",
                plane=ControlPlane.FIELD,
                domain="utilities_field",
                label="Emergency callout 2024-01-20",
                confidence=0.91,
            ),
        )
        policy = fabric.register_object(
            TENANT,
            FabricObjectCreate(
                control_type="escalation_rule",
                plane=ControlPlane.GOVERNANCE,
                domain="contract_margin",
                label="Emergency work requires 24h confirmation",
                confidence=1.0,
            ),
        )

        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=obligation.id,
                target_id=evidence.id,
                link_type=ControlLinkType.AUTHORIZES,
            ),
        )
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=policy.id,
                target_id=evidence.id,
                link_type=ControlLinkType.BLOCKS,
            ),
        )

        # 2. Reconciliation
        recon_result = recon.run_reconciliation(ReconciliationRunRequest(tenant_id=TENANT))
        assert recon_result.status == "completed"

        # 3. Bounded reasoning
        reason_result = reasoning.reason(
            TENANT,
            BoundedReasoningRequest(
                context=BoundedContextRequest(
                    pilot_case_id=CASE,
                    root_object_ids=[obligation.id],
                    scope=ReasoningScope.FULL_GRAPH,
                    max_depth=3,
                ),
                question="Can the emergency callout be billed at the emergency rate?",
            ),
        )
        assert reason_result.objects_consulted == 3

        # 4. Create and validate action
        action = action_engine.create_candidate(
            TENANT,
            CandidateActionCreate(
                pilot_case_id=CASE,
                action_type=ActionType.BILLING_ADJUSTMENT,
                label="Bill emergency callout at Rate Card E",
                confidence=0.93,
                source_object_ids=[obligation.id, evidence.id],
            ),
        )

        released = action_engine.validate_and_release(
            action.id,
            context={
                "schema_valid": True,
                "evidence_completeness": 0.91,
                "boundary_valid": True,
                "failed_rules": [],
                "cross_plane_conflicts": 0,
                "policy_compliant": True,
                "confidence": 0.93,
                "confidence_threshold": 0.7,
            },
        )
        assert released.status == ActionStatus.RELEASED

        # 5. Execute
        executed = action_engine.mark_executed(action.id)
        assert executed.status == ActionStatus.EXECUTED

        # 6. Verify summaries
        fabric_stats = fabric.get_stats(TENANT)
        assert fabric_stats.total_objects == 3
        assert fabric_stats.total_links == 2

        chain_summary = chain.get_summary(TENANT)
        assert chain_summary.total_runs == 1
        assert chain_summary.released == 1

        action_summary = action_engine.get_summary(TENANT)
        assert action_summary.total_candidates == 1
        assert action_summary.executed == 1
