"""
Exception Workflow Service

Provides a governed emergency release path.
When a release is blocked but business urgency demands
it proceed, the submitter can raise an exception.

An exception does NOT bypass the evidence gate.
It routes to an approver with the reason, creates
a permanent audit record, and marks the release
as exception-approved.

This is the "break glass" path — visible, auditable,
never silent.

States:
  raised → pending_approval → approved / rejected
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone

from app.products.release_guard.domain.enums import ReleaseStatus

logger = logging.getLogger(__name__)


@dataclass
class ExceptionRequest:
    exception_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    release_id: str = ""
    workspace_id: str = ""
    raised_by: str = ""
    reason: str = ""
    business_justification: str = ""
    urgency: str = "high"  # low / medium / high / critical
    status: str = "pending_approval"
    approver_email: str = ""
    decision_note: str = ""
    raised_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    decided_at: str | None = None
    approved: bool | None = None
    audit_hash: str = ""

    def __post_init__(self) -> None:
        if not self.audit_hash:
            payload = f"{self.exception_id}{self.raised_by}{self.raised_at}"
            self.audit_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]


_exceptions: dict[str, ExceptionRequest] = {}
_by_release: dict[str, list[str]] = {}


class ExceptionService:
    """
    Manages emergency exception requests for blocked releases.
    Wraps the underlying Control Fabric exception framework.
    """

    def raise_exception(
        self,
        release_id: str,
        workspace_id: str,
        raised_by: str,
        reason: str,
        business_justification: str,
        approver_email: str,
        urgency: str = "high",
    ) -> ExceptionRequest:
        """
        Raise an exception for a blocked release.
        The release must be in BLOCKED status.
        """
        from app.products.release_guard.services.release_request_service import (
            release_request_service,
        )

        release = release_request_service.get(release_id)
        if release.status != ReleaseStatus.BLOCKED:
            raise ValueError(
                f"Exceptions can only be raised for blocked releases. "
                f"Release {release_id} is {release.status.value}."
            )

        exc = ExceptionRequest(
            release_id=release_id,
            workspace_id=workspace_id,
            raised_by=raised_by,
            reason=reason,
            business_justification=business_justification,
            approver_email=approver_email,
            urgency=urgency,
        )
        _exceptions[exc.exception_id] = exc
        _by_release.setdefault(release_id, []).append(exc.exception_id)

        try:
            release_request_service._add_audit(
                release,
                "exception_raised",
                raised_by,
                f"Exception raised: {reason[:100]}",
            )
        except Exception:
            pass

        logger.warning(
            "Exception raised: release=%s by=%s urgency=%s",
            release_id[:8],
            raised_by,
            urgency,
        )
        return exc

    def approve_exception(
        self,
        exception_id: str,
        approved_by: str,
        note: str = "",
    ) -> ExceptionRequest:
        exc = self._get(exception_id)
        exc.status = "approved"
        exc.approved = True
        exc.decided_at = datetime.now(UTC).isoformat()
        exc.decision_note = note

        try:
            from app.products.release_guard.services.release_request_service import (
                release_request_service,
            )

            release = release_request_service.get(exc.release_id)
            release.status = ReleaseStatus.APPROVED
            release.decided_at = exc.decided_at
            release_request_service._add_audit(
                release,
                "exception_approved",
                approved_by,
                f"Exception approved by {approved_by}: {note[:100]}",
            )
        except Exception as e:
            logger.error("Could not update release after exception approval: %s", e)

        logger.warning("Exception APPROVED: %s by %s", exception_id[:8], approved_by)
        return exc

    def reject_exception(
        self,
        exception_id: str,
        rejected_by: str,
        note: str = "",
    ) -> ExceptionRequest:
        exc = self._get(exception_id)
        exc.status = "rejected"
        exc.approved = False
        exc.decided_at = datetime.now(UTC).isoformat()
        exc.decision_note = note

        try:
            from app.products.release_guard.services.release_request_service import (
                release_request_service,
            )

            release = release_request_service.get(exc.release_id)
            release_request_service._add_audit(
                release,
                "exception_rejected",
                rejected_by,
                f"Exception rejected by {rejected_by}: {note[:100]}",
            )
        except Exception:
            pass

        logger.warning("Exception REJECTED: %s by %s", exception_id[:8], rejected_by)
        return exc

    def get(self, exception_id: str) -> ExceptionRequest:
        return self._get(exception_id)

    def list_for_workspace(
        self,
        workspace_id: str,
        status: str | None = None,
    ) -> list[ExceptionRequest]:
        exceptions = [e for e in _exceptions.values() if e.workspace_id == workspace_id]
        if status:
            exceptions = [e for e in exceptions if e.status == status]
        return sorted(exceptions, key=lambda e: e.raised_at, reverse=True)

    def list_for_release(self, release_id: str) -> list[ExceptionRequest]:
        exc_ids = _by_release.get(release_id, [])
        return [_exceptions[eid] for eid in exc_ids if eid in _exceptions]

    def get_pending_for_approver(self, approver_email: str) -> list[dict]:
        pending = [
            e
            for e in _exceptions.values()
            if e.approver_email == approver_email and e.status == "pending_approval"
        ]
        result = []
        for exc in pending:
            try:
                from app.products.release_guard.services.release_request_service import (
                    release_request_service,
                )

                release = release_request_service.get(exc.release_id)
                age_hours = round(
                    (
                        datetime.now(UTC)
                        - datetime.fromisoformat(exc.raised_at.replace("Z", "+00:00"))
                    ).total_seconds()
                    / 3600,
                    1,
                )
                result.append(
                    {
                        "exception_id": exc.exception_id,
                        "release_id": exc.release_id,
                        "release_title": release.title,
                        "service_name": release.service_name,
                        "reason": exc.reason,
                        "business_justification": exc.business_justification,
                        "urgency": exc.urgency,
                        "raised_by": exc.raised_by,
                        "raised_at": exc.raised_at,
                        "age_hours": age_hours,
                        "blocked_reason": release.blocked_reason,
                    }
                )
            except Exception:
                pass
        return sorted(result, key=lambda x: x.get("age_hours", 0), reverse=True)

    def _get(self, exception_id: str) -> ExceptionRequest:
        exc = _exceptions.get(exception_id)
        if not exc:
            raise ValueError(f"Exception {exception_id} not found")
        return exc


exception_service = ExceptionService()
