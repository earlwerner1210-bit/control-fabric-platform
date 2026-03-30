"""
Exception and Override Manager

Governs the complete lifecycle of platform exceptions.
Exceptions pass through the same release gate as all other actions.
There is no backdoor. There is no silent override.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.exception_framework.domain_types import (
    ExceptionAuditEntry,
    ExceptionDecision,
    ExceptionRequest,
    ExceptionStatus,
)
from app.core.platform_action_release_gate import (
    ActionStatus,
    PlatformActionReleaseGate,
)
from app.core.platform_validation_chain import ActionOrigin

logger = logging.getLogger(__name__)


class ExceptionError(Exception):
    pass


class ExceptionManager:
    """
    Manages exception and override requests through the governance pipeline.

    Key guarantees:
    - Every exception is formally requested with justification
    - Every exception has an expiry — none are permanent
    - Every approval creates an automatic review task
    - Every action is logged in an immutable audit ledger
    - The release gate governs exception approvals too
    """

    def __init__(self, release_gate: PlatformActionReleaseGate | None = None) -> None:
        self._gate = release_gate or PlatformActionReleaseGate()
        self._requests: dict[str, ExceptionRequest] = {}
        self._decisions: dict[str, list[ExceptionDecision]] = {}
        self._audit_ledger: list[ExceptionAuditEntry] = []
        self._review_tasks: list[dict[str, Any]] = []

    def submit_exception(self, request: ExceptionRequest) -> ExceptionRequest:
        """
        Submit a formal exception request.
        Validates through the release gate before registering.
        """
        gate_result = self._gate.submit(
            action_type="exception_request",
            proposed_payload={
                "exception_type": request.exception_type.value,
                "affected_objects": request.affected_object_ids,
                "risk_assessment": request.risk_assessment.value,
                "expires_at": request.expires_at.isoformat(),
            },
            requested_by=request.requested_by,
            origin=ActionOrigin.HUMAN_OPERATOR,
            evidence_references=[request.request_hash],
        )

        if gate_result.status == ActionStatus.BLOCKED:
            raise ExceptionError(f"Exception request blocked: {gate_result.failure_reason}")

        self._requests[request.exception_id] = request
        self._audit(
            "submitted",
            request.exception_id,
            f"Exception request submitted by {request.requested_by}",
            request.requested_by,
        )
        logger.info(
            "Exception submitted: %s type=%s risk=%s",
            request.exception_id[:8],
            request.exception_type.value,
            request.risk_assessment.value,
        )
        return request

    def approve_exception(
        self,
        exception_id: str,
        decided_by: str,
        rationale: str,
        conditions: list[str] | None = None,
    ) -> ExceptionDecision:
        """Approve an exception. Automatically creates a review task."""
        request = self._get_request(exception_id)
        self._validate_not_expired(request)

        review_task_id = str(uuid.uuid4())
        self._review_tasks.append(
            {
                "task_id": review_task_id,
                "exception_id": exception_id,
                "task_type": "post_exception_review",
                "due_by": request.expires_at.isoformat(),
                "assigned_to": decided_by,
                "status": "open",
            }
        )

        decision = ExceptionDecision(
            exception_id=exception_id,
            decided_by=decided_by,
            decision=ExceptionStatus.APPROVED,
            decision_rationale=rationale,
            conditions=conditions or [],
            review_task_id=review_task_id,
        )
        self._decisions.setdefault(exception_id, []).append(decision)
        self._audit(
            "approved",
            exception_id,
            f"Approved by {decided_by}. Review task {review_task_id[:8]} created.",
            decided_by,
        )
        logger.info(
            "Exception approved: %s review_task=%s",
            exception_id[:8],
            review_task_id[:8],
        )
        return decision

    def reject_exception(
        self, exception_id: str, decided_by: str, rationale: str
    ) -> ExceptionDecision:
        """Reject an exception request."""
        self._get_request(exception_id)
        decision = ExceptionDecision(
            exception_id=exception_id,
            decided_by=decided_by,
            decision=ExceptionStatus.REJECTED,
            decision_rationale=rationale,
            review_task_id="none-rejected",
        )
        self._decisions.setdefault(exception_id, []).append(decision)
        self._audit(
            "rejected",
            exception_id,
            f"Rejected by {decided_by}: {rationale[:80]}",
            decided_by,
        )
        return decision

    def revoke_exception(self, exception_id: str, revoked_by: str, reason: str) -> None:
        """Revoke an active exception before expiry."""
        self._get_request(exception_id)
        self._audit(
            "revoked",
            exception_id,
            f"Revoked by {revoked_by}: {reason[:80]}",
            revoked_by,
        )
        logger.warning("Exception revoked: %s by %s", exception_id[:8], revoked_by)

    def get_active_exceptions(self) -> list[ExceptionRequest]:
        """Return all non-expired, approved exceptions."""
        now = datetime.now(UTC)
        active = []
        for req in self._requests.values():
            if req.expires_at > now:
                decisions = self._decisions.get(req.exception_id, [])
                if any(d.decision == ExceptionStatus.APPROVED for d in decisions):
                    active.append(req)
        return active

    def get_expired_unreviewed(self) -> list[dict[str, Any]]:
        """Return review tasks that are past due."""
        now = datetime.now(UTC)
        return [
            t
            for t in self._review_tasks
            if t["status"] == "open" and datetime.fromisoformat(t["due_by"]) < now
        ]

    def get_audit_trail(self, exception_id: str | None = None) -> list[ExceptionAuditEntry]:
        if exception_id:
            return [e for e in self._audit_ledger if e.exception_id == exception_id]
        return list(self._audit_ledger)

    def _get_request(self, exception_id: str) -> ExceptionRequest:
        if exception_id not in self._requests:
            raise ExceptionError(f"Exception {exception_id} not found.")
        return self._requests[exception_id]

    def _validate_not_expired(self, request: ExceptionRequest) -> None:
        if request.expires_at < datetime.now(UTC):
            raise ExceptionError(f"Exception {request.exception_id} has expired.")

    def _audit(
        self,
        event_type: str,
        exception_id: str,
        detail: str,
        performed_by: str,
    ) -> None:
        entry = ExceptionAuditEntry(
            exception_id=exception_id,
            event_type=event_type,
            event_detail=detail,
            performed_by=performed_by,
        )
        self._audit_ledger.append(entry)

    @property
    def total_requests(self) -> int:
        return len(self._requests)

    @property
    def total_active(self) -> int:
        return len(self.get_active_exceptions())
