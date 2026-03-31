"""Approval workflow service — simple single and multi-step approvals."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.products.release_guard.domain.enums import ApprovalStatus
from app.products.release_guard.domain.models import ApprovalStep

logger = logging.getLogger(__name__)

_steps: dict[str, ApprovalStep] = {}  # step_id -> step
_by_release: dict[str, list[str]] = {}  # release_id -> [step_ids]


class ApprovalService:
    def request(
        self,
        release_id: str,
        approver_email: str,
        sla_hours: int = 24,
    ) -> ApprovalStep:
        step = ApprovalStep(
            release_id=release_id,
            approver_id=approver_email,
            approver_email=approver_email,
            sla_hours=sla_hours,
        )
        _steps[step.step_id] = step
        _by_release.setdefault(release_id, []).append(step.step_id)
        logger.info("Approval requested: %s -> %s", release_id[:8], approver_email)
        return step

    def approve(
        self,
        step_id: str,
        approved_by: str,
        note: str = "",
    ) -> ApprovalStep:
        step = self._get(step_id)
        step.status = ApprovalStatus.APPROVED
        step.decided_at = datetime.now(UTC).isoformat()
        step.decision_note = note
        # Check if all steps for this release are approved
        self._check_release_completion(step.release_id)
        return step

    def reject(
        self,
        step_id: str,
        rejected_by: str,
        note: str = "",
    ) -> ApprovalStep:
        step = self._get(step_id)
        step.status = ApprovalStatus.REJECTED
        step.decided_at = datetime.now(UTC).isoformat()
        step.decision_note = note
        # Block the release
        try:
            from app.products.release_guard.services.release_request_service import (
                release_request_service,
            )

            release_request_service.mark_blocked(
                step.release_id,
                f"Rejected by {rejected_by}: {note}",
                rejected_by,
            )
        except Exception:
            pass
        return step

    def get_steps_for_release(self, release_id: str) -> list[ApprovalStep]:
        step_ids = _by_release.get(release_id, [])
        return [_steps[sid] for sid in step_ids if sid in _steps]

    def get_pending_inbox(self, approver_email: str) -> list[dict]:
        """All pending approvals for an approver — the approvals inbox."""
        pending = [
            s
            for s in _steps.values()
            if s.approver_email == approver_email and s.status == ApprovalStatus.PENDING
        ]
        result = []
        for step in pending:
            try:
                from app.products.release_guard.services.release_request_service import (
                    release_request_service,
                )

                release = release_request_service.get(step.release_id)
                now = datetime.now(UTC)
                age_hours = (
                    now - datetime.fromisoformat(step.requested_at.replace("Z", "+00:00"))
                ).total_seconds() / 3600
                result.append(
                    {
                        "step_id": step.step_id,
                        "release_id": step.release_id,
                        "release_title": release.title,
                        "service_name": release.service_name,
                        "environment": release.environment,
                        "risk_level": release.risk_level.value,
                        "submitted_by": release.submitted_by,
                        "requested_at": step.requested_at,
                        "age_hours": round(age_hours, 1),
                        "sla_hours": step.sla_hours,
                        "sla_breached": age_hours > step.sla_hours,
                    }
                )
            except Exception:
                pass
        return sorted(result, key=lambda x: x.get("age_hours", 0), reverse=True)

    def _check_release_completion(self, release_id: str) -> None:
        steps = self.get_steps_for_release(release_id)
        all_approved = all(s.status == ApprovalStatus.APPROVED for s in steps)
        if all_approved and steps:
            try:
                from app.products.release_guard.services.release_request_service import (
                    release_request_service,
                )

                release_request_service.mark_approved(release_id, "approval_service")
            except Exception:
                pass

    def _get(self, step_id: str) -> ApprovalStep:
        s = _steps.get(step_id)
        if not s:
            raise ValueError(f"Approval step {step_id} not found")
        return s


approval_service = ApprovalService()
