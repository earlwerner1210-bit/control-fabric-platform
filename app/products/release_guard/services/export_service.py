"""
Audit Export Service

Generates audit exports for compliance reporting.

Formats:
  - CSV: machine-readable, importable into Excel/GRC tools
  - Summary JSON: structured for API consumption

Export types:
  - releases: all release decisions with evidence
  - approvals: approval decisions with timestamps
  - exceptions: all exception requests and outcomes

Each export produces:
  - a unique export_id
  - a content hash for tamper detection
  - an immutable record of what was exported and when
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class ExportJob:
    export_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str = ""
    export_type: str = "releases"  # releases / approvals / exceptions
    format: str = "csv"  # csv / json
    status: str = "complete"
    requested_by: str = ""
    requested_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    record_count: int = 0
    content_hash: str = ""
    date_from: str | None = None
    date_to: str | None = None


_jobs: dict[str, ExportJob] = {}
_content: dict[str, str] = {}  # export_id → CSV or JSON string


class ExportService:
    """
    Generates compliance audit exports.
    All exports are immutable once created.
    """

    def export_releases(
        self,
        workspace_id: str,
        requested_by: str,
        format: str = "csv",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> ExportJob:
        from app.products.release_guard.services.release_request_service import (
            release_request_service,
        )

        releases = release_request_service.list_for_workspace(workspace_id, limit=10000)

        if date_from:
            releases = [r for r in releases if r.created_at >= date_from]
        if date_to:
            releases = [r for r in releases if r.created_at <= date_to]

        rows = []
        for r in releases:
            rows.append(
                {
                    "release_id": r.release_id,
                    "title": r.title,
                    "service_name": r.service_name,
                    "environment": r.environment,
                    "risk_level": r.risk_level.value,
                    "status": r.status.value,
                    "submitted_by": r.submitted_by,
                    "created_at": r.created_at,
                    "decided_at": r.decided_at or "",
                    "blocked_reason": r.blocked_reason or "",
                    "evidence_count": len(r.evidence_items),
                    "evidence_types": "|".join(e.evidence_type.value for e in r.evidence_items),
                    "package_id": r.package_id or "",
                }
            )

        content = self._render(rows, format)
        return self._save_job(
            workspace_id,
            "releases",
            format,
            requested_by,
            rows,
            content,
            date_from,
            date_to,
        )

    def export_approvals(
        self,
        workspace_id: str,
        requested_by: str,
        format: str = "csv",
    ) -> ExportJob:
        from app.products.release_guard.services.approval_service import (
            _steps as approval_steps,
        )
        from app.products.release_guard.services.release_request_service import (
            release_request_service,
        )

        rows = []
        for step in approval_steps.values():
            try:
                release = release_request_service.get(step.release_id)
                if release.workspace_id != workspace_id:
                    continue
            except Exception:
                continue

            rows.append(
                {
                    "step_id": step.step_id,
                    "release_id": step.release_id,
                    "release_title": "",
                    "approver_email": step.approver_email,
                    "status": step.status.value,
                    "requested_at": step.requested_at,
                    "decided_at": step.decided_at or "",
                    "decision_note": step.decision_note,
                    "sla_hours": step.sla_hours,
                }
            )

        content = self._render(rows, format)
        return self._save_job(workspace_id, "approvals", format, requested_by, rows, content)

    def export_exceptions(
        self,
        workspace_id: str,
        requested_by: str,
        format: str = "csv",
    ) -> ExportJob:
        from app.products.release_guard.services.exception_service import exception_service

        exceptions = exception_service.list_for_workspace(workspace_id)

        rows = [
            {
                "exception_id": e.exception_id,
                "release_id": e.release_id,
                "raised_by": e.raised_by,
                "reason": e.reason,
                "business_justification": e.business_justification,
                "urgency": e.urgency,
                "status": e.status,
                "approver_email": e.approver_email,
                "decision_note": e.decision_note,
                "raised_at": e.raised_at,
                "decided_at": e.decided_at or "",
                "audit_hash": e.audit_hash,
            }
            for e in exceptions
        ]

        content = self._render(rows, format)
        return self._save_job(workspace_id, "exceptions", format, requested_by, rows, content)

    def get_job(self, export_id: str) -> ExportJob:
        job = _jobs.get(export_id)
        if not job:
            raise ValueError(f"Export {export_id} not found")
        return job

    def get_content(self, export_id: str) -> str:
        content = _content.get(export_id)
        if content is None:
            raise ValueError(f"Export content for {export_id} not found")
        return content

    def list_jobs(self, workspace_id: str) -> list[ExportJob]:
        return [j for j in _jobs.values() if j.workspace_id == workspace_id]

    def _render(self, rows: list[dict], format: str) -> str:
        if format == "json":
            return json.dumps(rows, indent=2)
        if not rows:
            return ""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    def _save_job(
        self,
        workspace_id: str,
        export_type: str,
        format: str,
        requested_by: str,
        rows: list[dict],
        content: str,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> ExportJob:
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        job = ExportJob(
            workspace_id=workspace_id,
            export_type=export_type,
            format=format,
            requested_by=requested_by,
            record_count=len(rows),
            content_hash=content_hash,
            date_from=date_from,
            date_to=date_to,
        )
        _jobs[job.export_id] = job
        _content[job.export_id] = content
        logger.info(
            "Export created: %s type=%s format=%s records=%d hash=%s",
            job.export_id[:8],
            export_type,
            format,
            len(rows),
            content_hash[:8],
        )
        return job


export_service = ExportService()
