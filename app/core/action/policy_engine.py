"""Wave 3 action policy engine — evidence-gated action release with validation chain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.action.domain_types import (
    W3ActionEvidenceManifest,
    W3ActionExecutionMode,
    W3ActionFailureCode,
    W3ActionId,
    W3ActionPolicy,
    W3ActionProposal,
    W3ActionRelease,
    W3ActionStatus,
    W3ActionType,
    new_action_id,
)
from app.core.audit import FabricAuditHook
from app.core.control_object import ControlObject
from app.core.graph.service import GraphService
from app.core.types import ControlObjectId, EvidenceRef
from app.core.validation.domain_types import (
    ValidationDecision,
    ValidationExecutionRequest,
    ValidationExecutionResult,
    ValidationReportHash,
    ValidationRunId,
)
from app.core.validation.executor import ValidationChainExecutor


class ActionPolicyError(Exception):
    """Raised when action policy is violated."""

    def __init__(self, message: str, failure_code: W3ActionFailureCode) -> None:
        super().__init__(message)
        self.failure_code = failure_code


class W3ActionPolicyEngine:
    """Evidence-gated action policy engine.

    Rules:
    - No action without passing validation chain
    - No action without evidence manifest
    - Every release is reproducibly hashable
    - Three modes: dry-run, approval-gated, deterministic-auto-release
    """

    def __init__(
        self,
        graph_service: GraphService,
        validation_executor: ValidationChainExecutor,
        policy: W3ActionPolicy | None = None,
        audit_hook: FabricAuditHook | None = None,
    ) -> None:
        self._graph = graph_service
        self._validator = validation_executor
        self._policy = policy or W3ActionPolicy()
        self._audit = audit_hook or FabricAuditHook()
        self._proposals: dict[W3ActionId, W3ActionProposal] = {}
        self._releases: dict[W3ActionId, W3ActionRelease] = {}

    @property
    def policy(self) -> W3ActionPolicy:
        return self._policy

    def propose_action(
        self,
        tenant_id: uuid.UUID,
        action_type: W3ActionType,
        target_object_ids: list[ControlObjectId],
        validation_result: ValidationExecutionResult,
        execution_mode: W3ActionExecutionMode = W3ActionExecutionMode.APPROVAL_GATED,
        parameters: dict[str, Any] | None = None,
        description: str = "",
    ) -> W3ActionProposal:
        """Propose an action based on a completed validation result."""
        if self._policy.require_validation_pass:
            if validation_result.decision not in self._policy.allowed_decisions_for_release:
                raise ActionPolicyError(
                    f"Validation decision '{validation_result.decision.value}' "
                    f"not in allowed decisions for release",
                    W3ActionFailureCode.VALIDATION_NOT_PASSED,
                )

        objects = self._resolve_objects(target_object_ids)
        all_evidence: list[EvidenceRef] = []
        for obj in objects:
            all_evidence.extend(obj.evidence)

        if self._policy.require_evidence and len(all_evidence) < self._policy.min_evidence_count:
            raise ActionPolicyError(
                f"Insufficient evidence: {len(all_evidence)} < {self._policy.min_evidence_count}",
                W3ActionFailureCode.EVIDENCE_MISSING,
            )

        if self._policy.require_report_hash and not validation_result.report.report_hash:
            raise ActionPolicyError(
                "Validation report has no hash — cannot ensure reproducibility",
                W3ActionFailureCode.HASH_MISMATCH,
            )

        action_id = new_action_id()
        manifest = W3ActionEvidenceManifest(
            action_id=action_id,
            evidence_refs=all_evidence,
            validation_run_id=validation_result.run.id,
            validation_decision=validation_result.decision,
            report_hash=validation_result.report.report_hash,
            target_object_ids=target_object_ids,
        )
        manifest.compute_hash()

        if execution_mode == W3ActionExecutionMode.DRY_RUN:
            status = W3ActionStatus.VALIDATED
        elif execution_mode == W3ActionExecutionMode.DETERMINISTIC_AUTO_RELEASE:
            status = W3ActionStatus.VALIDATED
        else:
            status = W3ActionStatus.PENDING_APPROVAL

        proposal = W3ActionProposal(
            id=action_id,
            tenant_id=tenant_id,
            action_type=action_type,
            execution_mode=execution_mode,
            status=status,
            target_object_ids=target_object_ids,
            validation_run_id=validation_result.run.id,
            validation_decision=validation_result.decision,
            report_hash=validation_result.report.report_hash,
            evidence_manifest=manifest,
            description=description,
            parameters=parameters or {},
        )
        proposal.compute_decision_hash()

        self._proposals[proposal.id] = proposal

        from app.core.audit import FabricAuditEvent, FabricAuditEventType

        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.ACTION_PROPOSED,
                tenant_id=tenant_id,
                detail=f"Action proposed: {action_type.value}",
                metadata={
                    "action_id": str(action_id),
                    "action_type": action_type.value,
                    "execution_mode": execution_mode.value,
                    "validation_decision": validation_result.decision.value,
                },
            )
        )

        return proposal

    def approve_action(
        self,
        action_id: W3ActionId,
        approver: str,
    ) -> W3ActionProposal:
        """Approve an action proposal (approval-gated mode only)."""
        proposal = self._proposals.get(action_id)
        if proposal is None:
            raise ActionPolicyError(
                f"Action {action_id} not found",
                W3ActionFailureCode.POLICY_BLOCKED,
            )
        if proposal.execution_mode != W3ActionExecutionMode.APPROVAL_GATED:
            raise ActionPolicyError(
                "Only approval-gated actions require approval",
                W3ActionFailureCode.POLICY_BLOCKED,
            )

        proposal.status = W3ActionStatus.APPROVED
        proposal.approved_by = approver

        from app.core.audit import FabricAuditEvent, FabricAuditEventType

        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.ACTION_APPROVED,
                tenant_id=proposal.tenant_id,
                detail=f"Action {action_id} approved by {approver}",
                metadata={
                    "action_id": str(action_id),
                    "approver": approver,
                },
            )
        )

        return proposal

    def reject_action(
        self,
        action_id: W3ActionId,
        reason: str = "",
    ) -> W3ActionProposal:
        """Reject an action proposal."""
        proposal = self._proposals.get(action_id)
        if proposal is None:
            raise ActionPolicyError(
                f"Action {action_id} not found",
                W3ActionFailureCode.POLICY_BLOCKED,
            )

        proposal.status = W3ActionStatus.REJECTED
        proposal.rejected_reason = reason

        from app.core.audit import FabricAuditEvent, FabricAuditEventType

        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.ACTION_REJECTED,
                tenant_id=proposal.tenant_id,
                detail=f"Action {action_id} rejected: {reason}",
                metadata={
                    "action_id": str(action_id),
                    "reason": reason,
                },
            )
        )

        return proposal

    def release_action(
        self,
        action_id: W3ActionId,
        actor: str = "system",
    ) -> W3ActionRelease:
        """Release an action — requires validation pass and evidence manifest."""
        proposal = self._proposals.get(action_id)
        if proposal is None:
            raise ActionPolicyError(
                f"Action {action_id} not found",
                W3ActionFailureCode.POLICY_BLOCKED,
            )

        if not proposal.is_releasable:
            raise ActionPolicyError(
                f"Action not releasable: status={proposal.status.value}, "
                f"mode={proposal.execution_mode.value}, "
                f"decision={proposal.validation_decision}",
                W3ActionFailureCode.TARGET_NOT_ELIGIBLE,
            )

        if proposal.evidence_manifest is None:
            raise ActionPolicyError(
                "Action has no evidence manifest",
                W3ActionFailureCode.EVIDENCE_MISSING,
            )

        proposal.status = W3ActionStatus.RELEASED
        proposal.released_at = datetime.now(UTC)

        release = W3ActionRelease(
            action_id=action_id,
            tenant_id=proposal.tenant_id,
            action_type=proposal.action_type,
            evidence_manifest=proposal.evidence_manifest,
            decision_hash=proposal.decision_hash,
            released_by=actor,
        )

        self._releases[action_id] = release

        from app.core.audit import FabricAuditEvent, FabricAuditEventType

        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.ACTION_RELEASED,
                tenant_id=proposal.tenant_id,
                detail=f"Action {action_id} released by {actor}",
                metadata={
                    "action_id": str(action_id),
                    "release_id": str(release.id),
                    "decision_hash": proposal.decision_hash,
                    "manifest_hash": proposal.evidence_manifest.manifest_hash,
                },
            )
        )

        return release

    def get_proposal(self, action_id: W3ActionId) -> W3ActionProposal | None:
        return self._proposals.get(action_id)

    def get_release(self, action_id: W3ActionId) -> W3ActionRelease | None:
        return self._releases.get(action_id)

    def list_proposals(
        self,
        tenant_id: uuid.UUID,
        status: W3ActionStatus | None = None,
    ) -> list[W3ActionProposal]:
        results = [p for p in self._proposals.values() if p.tenant_id == tenant_id]
        if status:
            results = [p for p in results if p.status == status]
        return results

    def _resolve_objects(self, object_ids: list[ControlObjectId]) -> list[ControlObject]:
        objects: list[ControlObject] = []
        for oid in object_ids:
            obj = self._graph.get_object(oid)
            if obj:
                objects.append(obj)
        return objects
