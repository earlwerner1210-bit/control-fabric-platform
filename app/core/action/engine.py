"""Action engine — evidence-gated action release with mandatory validation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.action.manifest import build_manifest
from app.core.action.types import (
    ActionManifest,
    ActionMode,
    ActionProposal,
    ActionStatus,
    ActionType,
)
from app.core.control_object import ControlObject
from app.core.errors import (
    ActionWithoutEvidenceError,
    ActionWithoutValidationError,
)
from app.core.graph.service import GraphService
from app.core.registry import FabricRegistry
from app.core.types import (
    ActionEligibility,
    AuditContext,
    ConfidenceScore,
    ControlObjectId,
    ControlState,
)
from app.core.validation.chain import ValidationChain
from app.core.validation.types import ChainOutcome, ValidationChainResult


class ActionEngine:
    """Evidence-gated action engine.

    Rules:
    - No action without passing the validation chain
    - No action without evidence references
    - Every action produces a reproducible manifest with a decision hash
    - Three modes: dry_run, approval_gated, auto_release
    """

    def __init__(
        self,
        graph_service: GraphService,
        validation_chain: ValidationChain,
        registry: FabricRegistry | None = None,
    ) -> None:
        self._graph = graph_service
        self._validation = validation_chain
        self._registry = registry or FabricRegistry()
        self._proposals: dict[uuid.UUID, ActionProposal] = {}

    def propose_action(
        self,
        tenant_id: uuid.UUID,
        action_type: ActionType,
        target_object_ids: list[ControlObjectId],
        mode: ActionMode = ActionMode.APPROVAL_GATED,
        parameters: dict[str, Any] | None = None,
        description: str = "",
        context: dict[str, Any] | None = None,
    ) -> ActionProposal:
        """Propose an action: validates, checks evidence, builds manifest."""
        # Gather target objects
        objects: list[ControlObject] = []
        for oid in target_object_ids:
            obj = self._graph.get_object(oid)
            if obj:
                objects.append(obj)

        if not objects:
            raise ActionWithoutEvidenceError("No valid target objects found for action")

        # Check evidence gate
        total_evidence = sum(len(o.evidence) for o in objects)
        if total_evidence == 0:
            raise ActionWithoutEvidenceError(
                "Action requires at least one evidence reference across target objects"
            )

        # Run validation chain
        validation_result = self._validation.validate(
            tenant_id=tenant_id,
            objects=objects,
            action_type=action_type.value,
            context=context,
        )

        if not validation_result.is_actionable:
            raise ActionWithoutValidationError(
                f"Validation chain failed: {validation_result.failed_count} failures. "
                f"Action cannot proceed without passing validation."
            )

        # Build manifest
        manifest = build_manifest(
            tenant_id=tenant_id,
            action_type=action_type,
            objects=objects,
            parameters=parameters,
            validation_result_id=validation_result.id,
        )

        # Determine initial status based on mode
        if mode == ActionMode.DRY_RUN:
            status = ActionStatus.DRY_RUN_COMPLETE
            eligibility = ActionEligibility.INELIGIBLE
        elif mode == ActionMode.AUTO_RELEASE:
            status = ActionStatus.VALIDATED
            eligibility = ActionEligibility.ELIGIBLE
        else:
            status = ActionStatus.PENDING_APPROVAL
            eligibility = ActionEligibility.PENDING_APPROVAL

        proposal = ActionProposal(
            tenant_id=tenant_id,
            action_type=action_type,
            mode=mode,
            status=status,
            manifest=manifest,
            validation_result=validation_result,
            eligibility=eligibility,
            description=description,
            confidence=ConfidenceScore(min(float(o.confidence) for o in objects)),
            created_at=datetime.now(UTC),
        )

        self._proposals[proposal.id] = proposal
        return proposal

    def approve_action(
        self,
        proposal_id: uuid.UUID,
        approver: str,
    ) -> ActionProposal:
        """Approve an action proposal (for approval-gated mode)."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ActionWithoutValidationError(f"Proposal {proposal_id} not found")
        if proposal.mode != ActionMode.APPROVAL_GATED:
            raise ActionWithoutValidationError("Only approval-gated actions require approval")

        proposal.status = ActionStatus.APPROVED
        proposal.eligibility = ActionEligibility.ELIGIBLE
        proposal.approved_by = approver
        return proposal

    def reject_action(
        self,
        proposal_id: uuid.UUID,
        reason: str = "",
    ) -> ActionProposal:
        """Reject an action proposal."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ActionWithoutValidationError(f"Proposal {proposal_id} not found")
        proposal.status = ActionStatus.REJECTED
        proposal.eligibility = ActionEligibility.INELIGIBLE
        if reason:
            proposal.metadata["rejection_reason"] = reason
        return proposal

    def release_action(
        self,
        proposal_id: uuid.UUID,
        actor: str = "system",
    ) -> ActionProposal:
        """Release an approved/auto-release action."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ActionWithoutValidationError(f"Proposal {proposal_id} not found")
        if not proposal.is_releasable:
            raise ActionWithoutValidationError(
                f"Action is not releasable: status={proposal.status.value}, "
                f"eligibility={proposal.eligibility.value}"
            )

        proposal.status = ActionStatus.RELEASED
        proposal.released_at = datetime.now(UTC)

        # Mark target objects as actioned
        now = datetime.now(UTC)
        for oid in proposal.manifest.target_object_ids:
            obj = self._graph.get_object(oid)
            if obj and obj.state == ControlState.RECONCILED:
                obj.mark_actioned(
                    AuditContext(
                        actor=actor,
                        action=f"actioned_via_{proposal.action_type.value}",
                        timestamp=now,
                    )
                )
                self._graph.repository.store_object(obj)

        return proposal

    def get_proposal(self, proposal_id: uuid.UUID) -> ActionProposal | None:
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        tenant_id: uuid.UUID,
        status: ActionStatus | None = None,
    ) -> list[ActionProposal]:
        results = [p for p in self._proposals.values() if p.tenant_id == tenant_id]
        if status:
            results = [p for p in results if p.status == status]
        return results
