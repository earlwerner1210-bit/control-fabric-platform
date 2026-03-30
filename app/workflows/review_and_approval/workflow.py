"""Temporal workflow for review and approval of pilot cases."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ReviewAndApprovalInput:
    """Input for review and approval workflow."""

    pilot_case_id: str
    tenant_id: str
    reviewer_id: str
    workflow_output: dict[str, Any] = field(default_factory=dict)
    validation_result: dict[str, Any] = field(default_factory=dict)
    evidence_bundle_id: str | None = None
    baseline_expectation: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewAndApprovalOutput:
    """Output from review and approval workflow."""

    pilot_case_id: str
    review_outcome: str | None = None
    approval_type: str | None = None
    final_state: str = "under_review"
    override_reason: str | None = None
    escalation_route: str | None = None
    baseline_match_type: str | None = None
    reviewer_confidence: float | None = None
    timeline: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class ReviewAndApprovalActivities:
    """Activities for the review and approval workflow."""

    def __init__(self, audit_service: Any = None) -> None:
        self.audit_service = audit_service
        self._timeline: list[dict[str, Any]] = []

    def fetch_workflow_output(
        self, pilot_case_id: str, workflow_output: dict[str, Any]
    ) -> dict[str, Any]:
        """Fetch and validate workflow output for review."""
        self._record_timeline(
            "workflow_output_fetched",
            pilot_case_id,
            {"keys": list(workflow_output.keys())},
        )
        return workflow_output

    def fetch_evidence(self, pilot_case_id: str, evidence_bundle_id: str | None) -> dict[str, Any]:
        """Fetch evidence bundle for review."""
        self._record_timeline(
            "evidence_fetched",
            pilot_case_id,
            {"bundle_id": evidence_bundle_id},
        )
        return {"bundle_id": evidence_bundle_id, "fetched": True}

    def create_review_task(
        self, pilot_case_id: str, reviewer_id: str, workflow_output: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a review task for the reviewer."""
        review_id = str(uuid.uuid4())
        self._record_timeline(
            "review_task_created",
            pilot_case_id,
            {"review_id": review_id, "reviewer_id": reviewer_id},
        )
        self._record_audit(
            "review.task_created",
            pilot_case_id,
            None,
            reviewer_id,
            {"review_id": review_id},
        )
        return {"review_id": review_id, "reviewer_id": reviewer_id}

    def capture_review_outcome(
        self,
        pilot_case_id: str,
        reviewer_id: str,
        outcome: str,
        reasoning: str | None = None,
        confidence: float | None = None,
    ) -> dict[str, Any]:
        """Capture the reviewer's decision."""
        decision_id = str(uuid.uuid4())
        self._record_timeline(
            "review_outcome_captured",
            pilot_case_id,
            {
                "decision_id": decision_id,
                "outcome": outcome,
                "confidence": confidence,
            },
        )
        self._record_audit(
            "review.decision_captured",
            pilot_case_id,
            None,
            reviewer_id,
            {"outcome": outcome, "reasoning": reasoning, "confidence": confidence},
        )
        return {
            "decision_id": decision_id,
            "outcome": outcome,
            "reasoning": reasoning,
            "confidence": confidence,
        }

    def capture_approval(
        self,
        pilot_case_id: str,
        approver_id: str,
        approval_type: str,
        reasoning: str | None = None,
        override_reason: str | None = None,
        escalation_route: str | None = None,
        corrected_outcome: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Capture approval, override, or escalation."""
        approval_id = str(uuid.uuid4())
        self._record_timeline(
            f"{approval_type}_captured",
            pilot_case_id,
            {
                "approval_id": approval_id,
                "approval_type": approval_type,
                "override_reason": override_reason,
                "escalation_route": escalation_route,
            },
        )
        self._record_audit(
            f"review.{approval_type}",
            pilot_case_id,
            None,
            approver_id,
            {
                "approval_type": approval_type,
                "reasoning": reasoning,
                "override_reason": override_reason,
                "escalation_route": escalation_route,
                "corrected_outcome": corrected_outcome,
            },
        )
        return {
            "approval_id": approval_id,
            "approval_type": approval_type,
            "override_reason": override_reason,
            "escalation_route": escalation_route,
        }

    def compare_baseline(
        self,
        pilot_case_id: str,
        platform_outcome: str | None,
        reviewer_outcome: str | None,
        expected_outcome: str | None,
    ) -> dict[str, Any]:
        """Compare outcomes against baseline."""
        self._record_timeline(
            "baseline_compared",
            pilot_case_id,
            {
                "platform_outcome": platform_outcome,
                "reviewer_outcome": reviewer_outcome,
                "expected_outcome": expected_outcome,
            },
        )
        return {
            "platform_outcome": platform_outcome,
            "reviewer_outcome": reviewer_outcome,
            "expected_outcome": expected_outcome,
        }

    def persist_final_result(
        self,
        pilot_case_id: str,
        final_state: str,
        review_outcome: str | None,
        approval_type: str | None,
    ) -> dict[str, Any]:
        """Persist the final workflow result."""
        self._record_timeline(
            "final_result_persisted",
            pilot_case_id,
            {
                "final_state": final_state,
                "review_outcome": review_outcome,
                "approval_type": approval_type,
            },
        )
        self._record_audit(
            "review.completed",
            pilot_case_id,
            None,
            None,
            {
                "final_state": final_state,
                "review_outcome": review_outcome,
                "approval_type": approval_type,
            },
        )
        return {
            "final_state": final_state,
            "review_outcome": review_outcome,
            "approval_type": approval_type,
        }

    def get_timeline(self) -> list[dict[str, Any]]:
        return list(self._timeline)

    def _record_timeline(self, event_type: str, pilot_case_id: str, details: Any = None) -> None:
        self._timeline.append(
            {
                "event_type": event_type,
                "pilot_case_id": pilot_case_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "details": details,
            }
        )

    def _record_audit(
        self,
        event_type: str,
        pilot_case_id: str | None,
        tenant_id: str | None,
        actor_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self.audit_service is not None:
            try:
                self.audit_service.record(
                    event_type=event_type,
                    resource_id=pilot_case_id,
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    payload=payload or {},
                )
            except Exception:
                pass


class ReviewAndApprovalWorkflow:
    """Orchestrates the review and approval process.

    Steps:
    1. Fetch workflow output
    2. Fetch evidence
    3. Create review task
    4. Capture review outcome
    5. Based on outcome:
       - accept -> approve
       - reject -> override or close
       - escalate -> escalation
       - warn -> approve with notes
       - request_more_evidence -> return for more evidence
    6. Compare baseline
    7. Persist final result
    """

    def __init__(self, activities: ReviewAndApprovalActivities | None = None) -> None:
        self.activities = activities or ReviewAndApprovalActivities()

    def run(
        self,
        input_data: ReviewAndApprovalInput,
        review_outcome: str = "accept",
        review_reasoning: str | None = None,
        review_confidence: float | None = None,
        override_reason: str | None = None,
        escalation_route: str | None = None,
        corrected_outcome: dict[str, Any] | None = None,
    ) -> ReviewAndApprovalOutput:
        """Execute the review and approval workflow."""
        pilot_case_id = input_data.pilot_case_id

        # Step 1: Fetch workflow output
        self.activities.fetch_workflow_output(pilot_case_id, input_data.workflow_output)

        # Step 2: Fetch evidence
        self.activities.fetch_evidence(pilot_case_id, input_data.evidence_bundle_id)

        # Step 3: Create review task
        self.activities.create_review_task(
            pilot_case_id, input_data.reviewer_id, input_data.workflow_output
        )

        # Step 4: Capture review outcome
        self.activities.capture_review_outcome(
            pilot_case_id,
            input_data.reviewer_id,
            review_outcome,
            review_reasoning,
            review_confidence,
        )

        # Step 5: Determine approval path
        final_state: str
        approval_type: str | None = None

        if review_outcome in ("accept", "warn"):
            approval_type = "approval"
            final_state = "approved"
            self.activities.capture_approval(
                pilot_case_id,
                input_data.reviewer_id,
                "approval",
                reasoning=review_reasoning,
            )
        elif review_outcome == "reject":
            if override_reason:
                approval_type = "override"
                final_state = "overridden"
                self.activities.capture_approval(
                    pilot_case_id,
                    input_data.reviewer_id,
                    "override",
                    reasoning=review_reasoning,
                    override_reason=override_reason,
                    corrected_outcome=corrected_outcome,
                )
            else:
                final_state = "closed"
        elif review_outcome == "escalate":
            approval_type = "escalation"
            final_state = "escalated"
            self.activities.capture_approval(
                pilot_case_id,
                input_data.reviewer_id,
                "escalation",
                reasoning=review_reasoning,
                escalation_route=escalation_route,
            )
        elif review_outcome == "request_more_evidence":
            final_state = "evidence_ready"
        else:
            final_state = "under_review"

        # Step 6: Compare baseline
        baseline_match_type = None
        if input_data.baseline_expectation:
            expected = input_data.baseline_expectation.get("expected_outcome")
            platform = input_data.workflow_output.get("verdict")
            reviewer_final = corrected_outcome.get("verdict") if corrected_outcome else None
            comparison = self.activities.compare_baseline(
                pilot_case_id, platform, reviewer_final, expected
            )
            baseline_match_type = comparison.get("match_type")

        # Step 7: Persist final result
        self.activities.persist_final_result(
            pilot_case_id, final_state, review_outcome, approval_type
        )

        return ReviewAndApprovalOutput(
            pilot_case_id=pilot_case_id,
            review_outcome=review_outcome,
            approval_type=approval_type,
            final_state=final_state,
            override_reason=override_reason,
            escalation_route=escalation_route,
            baseline_match_type=baseline_match_type,
            reviewer_confidence=review_confidence,
            timeline=self.activities.get_timeline(),
        )
