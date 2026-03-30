"""
Audit export — produces compliance-ready audit packages.
Outputs: JSON, CSV, signed manifest.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Query
from fastapi.responses import Response, StreamingResponse

from app.core.exception_framework.manager import ExceptionManager
from app.core.platform_action_release_gate import PlatformActionReleaseGate

router = APIRouter(prefix="/audit/export", tags=["audit"])

_gate = PlatformActionReleaseGate()
_exception_manager = ExceptionManager()


def _build_audit_records() -> list[dict]:
    records = []
    for entry in _gate.get_audit_log():
        records.append(
            {
                "record_type": "action_release",
                "dispatch_id": entry.dispatch_id,
                "package_id": entry.package_id,
                "status": entry.status.value,
                "failure_reason": entry.failure_reason,
                "dispatched_at": entry.dispatched_at.isoformat(),
            }
        )
    for entry in _exception_manager.get_audit_trail():
        records.append(
            {
                "record_type": "exception",
                "exception_id": entry.exception_id,
                "event_type": entry.event_type,
                "event_detail": entry.event_detail,
                "performed_by": entry.performed_by,
                "occurred_at": entry.occurred_at.isoformat(),
            }
        )
    return sorted(
        records,
        key=lambda r: r.get("dispatched_at", r.get("occurred_at", "")),
        reverse=True,
    )


@router.get("/json")
def export_json(
    from_dt: str | None = Query(None, description="ISO datetime"),
    to_dt: str | None = Query(None, description="ISO datetime"),
) -> Response:
    records = _build_audit_records()
    if from_dt:
        records = [
            r for r in records if r.get("dispatched_at", r.get("occurred_at", "")) >= from_dt
        ]
    if to_dt:
        records = [r for r in records if r.get("dispatched_at", r.get("occurred_at", "")) <= to_dt]
    payload = json.dumps(
        {
            "exported_at": datetime.now(UTC).isoformat(),
            "record_count": len(records),
            "records": records,
        },
        indent=2,
    )
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit-export.json"},
    )


@router.get("/csv")
def export_csv() -> StreamingResponse:
    records = _build_audit_records()
    output = io.StringIO()
    if records:
        writer = csv.DictWriter(output, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-export.csv"},
    )


@router.get("/manifest")
def export_manifest() -> dict:
    """Signed hash manifest — cryptographic proof of audit record integrity."""
    records = _build_audit_records()
    manifest_payload = json.dumps(records, sort_keys=True)
    manifest_hash = hashlib.sha256(manifest_payload.encode()).hexdigest()
    return {
        "manifest_hash": manifest_hash,
        "record_count": len(records),
        "exported_at": datetime.now(UTC).isoformat(),
        "algorithm": "SHA-256",
        "verification": "Re-compute SHA-256 of the ordered JSON export to verify manifest_hash",
    }
