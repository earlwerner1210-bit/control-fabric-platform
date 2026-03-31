"""
Release Request Service

The core product service. Creates, validates, and manages release requests.
Orchestrates the underlying Control Fabric validation chain and release gate
but exposes a simple product API to SMB users.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.products.release_guard.domain.enums import (
    EvidenceType,
    PolicyProfileName,
    ReleaseRisk,
    ReleaseStatus,
)
from app.products.release_guard.domain.models import (
    EvidenceItem,
    ReleaseRequest,
)
from app.products.release_guard.policies.profiles import (
    approvers_required,
    get_required_evidence,
    needs_approval,
)

logger = logging.getLogger(__name__)

_releases: dict[str, ReleaseRequest] = {}


class ReleaseRequestService:
    """
    Creates and manages release requests.

    The complexity of the underlying Control Fabric platform
    (validation chain, evidence gate, graph reconciliation) is
    hidden behind simple product operations:
      create -> add evidence -> submit -> get status
    """

    def create(
        self,
        workspace_id: str,
        tenant_id: str,
        title: str,
        service_name: str,
        environment: str,
        risk_level: ReleaseRisk,
        submitted_by: str,
        description: str = "",
    ) -> ReleaseRequest:
        release = ReleaseRequest(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            title=title,
            service_name=service_name,
            environment=environment,
            risk_level=risk_level,
            submitted_by=submitted_by,
            description=description,
        )
        _releases[release.release_id] = release
        self._add_audit(release, "created", submitted_by, f"Release request created: {title}")
        logger.info("Release request created: %s", release.release_id[:8])
        return release

    def add_evidence(
        self,
        release_id: str,
        evidence_type: EvidenceType,
        title: str,
        reference: str,
        url: str,
        added_by: str,
    ) -> EvidenceItem:
        release = self._get(release_id)
        if release.status not in (ReleaseStatus.DRAFT, ReleaseStatus.BLOCKED):
            raise ValueError(f"Cannot add evidence to release in status {release.status}")
        item = EvidenceItem(
            release_id=release_id,
            evidence_type=evidence_type,
            title=title,
            reference=reference,
            url=url,
            added_by=added_by,
            verified=True,
        )
        release.evidence_items.append(item)
        self._add_audit(
            release,
            "evidence_added",
            added_by,
            f"Evidence added: {evidence_type.value} — {title}",
        )
        return item

    def remove_evidence(self, release_id: str, evidence_id: str) -> None:
        release = self._get(release_id)
        release.evidence_items = [e for e in release.evidence_items if e.evidence_id != evidence_id]

    def check_evidence_completeness(
        self,
        release_id: str,
        profile_name: PolicyProfileName,
    ) -> dict:
        """
        Check what evidence is required vs what is attached.
        Returns a simple checklist — not the raw platform model.
        """
        release = self._get(release_id)
        required = get_required_evidence(profile_name)
        attached_types = {e.evidence_type.value for e in release.evidence_items}
        checks = []
        for req in required:
            checks.append(
                {
                    "check": req.replace("_", " ").title(),
                    "required": True,
                    "complete": req in attached_types,
                    "evidence_type": req,
                }
            )
        complete_count = sum(1 for c in checks if c["complete"])
        return {
            "release_id": release_id,
            "complete": complete_count == len(checks),
            "complete_count": complete_count,
            "total_required": len(checks),
            "checks": checks,
            "missing": [c["evidence_type"] for c in checks if not c["complete"]],
        }

    def submit(
        self,
        release_id: str,
        profile_name: PolicyProfileName,
    ) -> ReleaseRequest:
        """
        Submit a release request for validation.
        Orchestrates the underlying Control Fabric release gate.
        """
        release = self._get(release_id)
        if release.status not in (ReleaseStatus.DRAFT, ReleaseStatus.BLOCKED):
            raise ValueError(
                f"Release {release_id} cannot be submitted from status {release.status}"
            )

        now = datetime.now(UTC).isoformat()
        release.submitted_at = now
        release.status = ReleaseStatus.PENDING
        release.blocked_reason = None
        release.blocked_checks = []
        release.missing_evidence = []

        # Check evidence completeness
        completeness = self.check_evidence_completeness(release_id, profile_name)
        if not completeness["complete"]:
            release.status = ReleaseStatus.BLOCKED
            release.missing_evidence = completeness["missing"]
            release.blocked_reason = "Missing required evidence: " + ", ".join(
                m.replace("_", " ") for m in completeness["missing"]
            )
            release.blocked_checks = completeness["missing"]
            release.decided_at = now
            self._add_audit(
                release, "blocked", release.submitted_by, f"Blocked: {release.blocked_reason}"
            )
            logger.info("Release blocked: %s — %s", release_id[:8], release.blocked_reason)
            return release

        # Submit to underlying Control Fabric release gate
        try:
            from app.core.platform_action_release_gate import PlatformActionReleaseGate
            from app.core.platform_validation_chain import ActionOrigin

            gate = PlatformActionReleaseGate()
            evidence_refs = [
                f"{e.evidence_type.value}:{e.reference}" for e in release.evidence_items
            ]
            result = gate.submit(
                action_type="production_release",
                proposed_payload={
                    "service": release.service_name,
                    "environment": release.environment,
                    "release_id": release.release_id,
                    "title": release.title,
                    "risk_level": release.risk_level.value,
                },
                requested_by=release.submitted_by,
                origin=ActionOrigin.HUMAN_OPERATOR,
                evidence_references=evidence_refs,
            )
            if result.status.value == "compiled":
                release.package_id = result.package_id
                # Check if approval is needed
                if needs_approval(profile_name, release.risk_level):
                    release.status = ReleaseStatus.PENDING
                    self._add_audit(
                        release,
                        "awaiting_approval",
                        release.submitted_by,
                        "Evidence complete — awaiting approver decision",
                    )
                else:
                    release.status = ReleaseStatus.APPROVED
                    release.decided_at = now
                    self._add_audit(
                        release,
                        "approved",
                        "system",
                        "Auto-approved: evidence complete, no approval required by policy",
                    )
            else:
                release.status = ReleaseStatus.BLOCKED
                release.blocked_reason = result.failure_reason or "Validation failed"
                release.decided_at = now
                self._add_audit(release, "blocked", "system", release.blocked_reason)
        except Exception as e:
            logger.warning("Release gate unavailable — using offline validation: %s", e)
            # Offline mode: evidence check passed, approval determines status
            if needs_approval(profile_name, release.risk_level):
                release.status = ReleaseStatus.PENDING
            else:
                release.status = ReleaseStatus.APPROVED
                release.decided_at = now

        return release

    def mark_approved(self, release_id: str, approved_by: str) -> ReleaseRequest:
        release = self._get(release_id)
        release.status = ReleaseStatus.APPROVED
        release.decided_at = datetime.now(UTC).isoformat()
        self._add_audit(release, "approved", approved_by, "Release approved")
        return release

    def mark_blocked(self, release_id: str, reason: str, blocked_by: str) -> ReleaseRequest:
        release = self._get(release_id)
        release.status = ReleaseStatus.BLOCKED
        release.blocked_reason = reason
        release.decided_at = datetime.now(UTC).isoformat()
        self._add_audit(release, "blocked", blocked_by, f"Blocked: {reason}")
        return release

    def cancel(self, release_id: str, cancelled_by: str) -> ReleaseRequest:
        release = self._get(release_id)
        release.status = ReleaseStatus.CANCELLED
        self._add_audit(release, "cancelled", cancelled_by, "Release cancelled")
        return release

    def get(self, release_id: str) -> ReleaseRequest:
        return self._get(release_id)

    def list_for_workspace(
        self,
        workspace_id: str,
        status: ReleaseStatus | None = None,
        limit: int = 50,
    ) -> list[ReleaseRequest]:
        releases = [r for r in _releases.values() if r.workspace_id == workspace_id]
        if status:
            releases = [r for r in releases if r.status == status]
        return sorted(releases, key=lambda r: r.created_at, reverse=True)[:limit]

    def get_explain(self, release_id: str) -> dict:
        """
        Plain-language explanation of why a release was blocked or approved.
        Wraps the underlying explainability engine.
        """
        release = self._get(release_id)
        if release.status == ReleaseStatus.BLOCKED:
            return {
                "outcome": "blocked",
                "title": "Release blocked",
                "reason": release.blocked_reason or "Validation failed",
                "missing_evidence": [m.replace("_", " ").title() for m in release.missing_evidence],
                "what_to_do": [
                    f"Add {m.replace('_', ' ')} to continue" for m in release.missing_evidence
                ],
            }
        elif release.status == ReleaseStatus.APPROVED:
            return {
                "outcome": "approved",
                "title": "Release approved",
                "reason": "All required evidence was provided and all checks passed.",
                "evidence_provided": [
                    f"{e.evidence_type.value.replace('_', ' ').title()}: {e.title}"
                    for e in release.evidence_items
                ],
                "package_id": release.package_id,
            }
        return {
            "outcome": release.status.value,
            "title": f"Release is {release.status.value}",
            "reason": "No additional information available.",
        }

    def _get(self, release_id: str) -> ReleaseRequest:
        r = _releases.get(release_id)
        if not r:
            raise ValueError(f"Release {release_id} not found")
        return r

    @staticmethod
    def _add_audit(release: ReleaseRequest, event: str, by: str, detail: str) -> None:
        release.audit_trail.append(
            {
                "event": event,
                "by": by,
                "detail": detail,
                "at": datetime.now(UTC).isoformat(),
            }
        )


release_request_service = ReleaseRequestService()
