"""Governed Action Release Workflow — Temporal-style orchestration for evidence-gated action release."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class GovernedActionReleaseInput:
    pilot_case_id: str
    tenant_id: str
    action_type: str
    action_label: str
    action_payload: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    source_object_ids: list[str] = field(default_factory=list)
    confidence: float = 1.0
    requires_approval: bool = False
    validation_context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GovernedActionReleaseOutput:
    action_id: str
    status: str
    validation_outcome: str | None = None
    validation_chain_id: str | None = None
    blocking_stage: str | None = None
    blocking_message: str | None = None
    released_at: str | None = None
    error: str | None = None


class GovernedActionReleaseActivities:
    """Activity implementations for the governed action release workflow."""

    def create_candidate_action(
        self,
        pilot_case_id: str,
        tenant_id: str,
        action_type: str,
        action_label: str,
        payload: dict[str, Any],
        evidence_refs: list[str],
        source_object_ids: list[str],
        confidence: float,
        requires_approval: bool,
    ) -> dict[str, Any]:
        return {
            "action_id": str(uuid.uuid4()),
            "status": "candidate",
            "pilot_case_id": pilot_case_id,
            "action_type": action_type,
            "label": action_label,
        }

    def gather_evidence(
        self,
        pilot_case_id: str,
        evidence_refs: list[str],
    ) -> dict[str, Any]:
        return {
            "evidence_count": len(evidence_refs),
            "completeness_score": 1.0 if evidence_refs else 0.0,
        }

    def build_validation_context(
        self,
        action: dict[str, Any],
        evidence: dict[str, Any],
        user_context: dict[str, Any],
    ) -> dict[str, Any]:
        ctx = dict(user_context)
        ctx["evidence_completeness"] = evidence.get("completeness_score", 0.0)
        ctx["confidence"] = action.get("confidence", 1.0)
        return ctx

    def run_validation_chain(
        self,
        pilot_case_id: str,
        tenant_id: str,
        action_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "chain_id": str(uuid.uuid4()),
            "outcome": "released",
            "blocking_stage": None,
            "blocking_message": None,
        }

    def release_action(
        self,
        action_id: str,
        chain_id: str,
    ) -> dict[str, Any]:
        return {
            "action_id": action_id,
            "status": "released",
            "released_at": datetime.now(UTC).isoformat(),
        }

    def block_action(
        self,
        action_id: str,
        chain_id: str,
        blocking_stage: str | None,
        blocking_message: str | None,
    ) -> dict[str, Any]:
        return {
            "action_id": action_id,
            "status": "blocked",
            "blocking_stage": blocking_stage,
            "blocking_message": blocking_message,
        }

    def escalate_action(
        self,
        action_id: str,
        chain_id: str,
        reason: str | None,
    ) -> dict[str, Any]:
        return {
            "action_id": action_id,
            "status": "escalated",
        }

    def record_audit_event(
        self,
        pilot_case_id: str,
        action_id: str,
        event_type: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "recorded": True,
        }


class GovernedActionReleaseWorkflow:
    """Orchestrates evidence-gated action release through validation chain."""

    def __init__(self, activities: GovernedActionReleaseActivities) -> None:
        self._activities = activities

    def run(self, input: GovernedActionReleaseInput) -> GovernedActionReleaseOutput:
        try:
            # Step 1: Create candidate action
            action = self._activities.create_candidate_action(
                pilot_case_id=input.pilot_case_id,
                tenant_id=input.tenant_id,
                action_type=input.action_type,
                action_label=input.action_label,
                payload=input.action_payload,
                evidence_refs=input.evidence_refs,
                source_object_ids=input.source_object_ids,
                confidence=input.confidence,
                requires_approval=input.requires_approval,
            )
            action_id = action["action_id"]

            # Step 2: Gather evidence
            evidence = self._activities.gather_evidence(
                pilot_case_id=input.pilot_case_id,
                evidence_refs=input.evidence_refs,
            )

            # Step 3: Build validation context
            context = self._activities.build_validation_context(
                action=action,
                evidence=evidence,
                user_context=input.validation_context,
            )

            # Step 4: Run validation chain
            chain_result = self._activities.run_validation_chain(
                pilot_case_id=input.pilot_case_id,
                tenant_id=input.tenant_id,
                action_id=action_id,
                context=context,
            )
            chain_id = chain_result["chain_id"]
            outcome = chain_result["outcome"]

            # Step 5: Release, block, or escalate based on outcome
            if outcome in ("released", "warn_released"):
                release = self._activities.release_action(action_id, chain_id)
                self._activities.record_audit_event(
                    pilot_case_id=input.pilot_case_id,
                    action_id=action_id,
                    event_type="action_released",
                    details={"chain_id": chain_id, "outcome": outcome},
                )
                return GovernedActionReleaseOutput(
                    action_id=action_id,
                    status="released",
                    validation_outcome=outcome,
                    validation_chain_id=chain_id,
                    released_at=release.get("released_at"),
                )

            if outcome == "blocked":
                self._activities.block_action(
                    action_id=action_id,
                    chain_id=chain_id,
                    blocking_stage=chain_result.get("blocking_stage"),
                    blocking_message=chain_result.get("blocking_message"),
                )
                self._activities.record_audit_event(
                    pilot_case_id=input.pilot_case_id,
                    action_id=action_id,
                    event_type="action_blocked",
                    details={
                        "chain_id": chain_id,
                        "blocking_stage": chain_result.get("blocking_stage"),
                    },
                )
                return GovernedActionReleaseOutput(
                    action_id=action_id,
                    status="blocked",
                    validation_outcome=outcome,
                    validation_chain_id=chain_id,
                    blocking_stage=chain_result.get("blocking_stage"),
                    blocking_message=chain_result.get("blocking_message"),
                )

            # Escalated
            self._activities.escalate_action(
                action_id=action_id,
                chain_id=chain_id,
                reason=chain_result.get("blocking_message"),
            )
            self._activities.record_audit_event(
                pilot_case_id=input.pilot_case_id,
                action_id=action_id,
                event_type="action_escalated",
                details={"chain_id": chain_id},
            )
            return GovernedActionReleaseOutput(
                action_id=action_id,
                status="escalated",
                validation_outcome=outcome,
                validation_chain_id=chain_id,
            )

        except Exception as e:
            return GovernedActionReleaseOutput(
                action_id="",
                status="failed",
                error=str(e),
            )
