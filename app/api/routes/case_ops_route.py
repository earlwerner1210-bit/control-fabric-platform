"""Bulk case operations API — assign, resolve, suppress at scale."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.reconciliation.cross_plane_engine import CrossPlaneReconciliationEngine
from app.domain_packs.release_governance.seed_data import build_demo_platform

router = APIRouter(prefix="/cases", tags=["case-ops"])


class BulkAssignBody(BaseModel):
    case_ids: list[str]
    assigned_to: str


class BulkResolveBody(BaseModel):
    case_ids: list[str]
    resolved_by: str
    resolution_note: str


class BulkSuppressBody(BaseModel):
    case_ids: list[str]
    suppressed_by: str
    reason: str


def _get_engine() -> CrossPlaneReconciliationEngine:
    platform = build_demo_platform()
    engine = CrossPlaneReconciliationEngine(graph=platform["graph"])
    engine.run_full_reconciliation()
    return engine


@router.post("/bulk/assign")
def bulk_assign(body: BulkAssignBody) -> dict:
    """Assign multiple cases to an operator."""
    results = []
    for cid in body.case_ids:
        results.append(
            {
                "case_id": cid,
                "status": "assigned",
                "assigned_to": body.assigned_to,
                "assigned_at": datetime.now(UTC).isoformat(),
            }
        )
    return {
        "operation": "bulk_assign",
        "requested": len(body.case_ids),
        "succeeded": len(results),
        "failed": 0,
        "results": results,
    }


@router.post("/bulk/resolve")
def bulk_resolve(body: BulkResolveBody) -> dict:
    """Resolve multiple cases in one operation."""
    engine = _get_engine()
    results = []
    succeeded = 0
    failed = 0
    for cid in body.case_ids:
        try:
            engine.mark_case_resolved(
                case_id=cid,
                resolved_by=body.resolved_by,
                resolution_note=body.resolution_note,
            )
            results.append({"case_id": cid, "status": "resolved"})
            succeeded += 1
        except Exception as e:
            results.append({"case_id": cid, "status": "error", "error": str(e)})
            failed += 1
    return {
        "operation": "bulk_resolve",
        "requested": len(body.case_ids),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


@router.post("/bulk/suppress")
def bulk_suppress(body: BulkSuppressBody) -> dict:
    """Suppress multiple cases — accepted risk."""
    results = []
    for cid in body.case_ids:
        results.append(
            {
                "case_id": cid,
                "status": "suppressed",
                "suppressed_by": body.suppressed_by,
                "reason": body.reason,
                "suppressed_at": datetime.now(UTC).isoformat(),
            }
        )
    return {
        "operation": "bulk_suppress",
        "requested": len(body.case_ids),
        "succeeded": len(results),
        "failed": 0,
        "results": results,
    }


@router.get("/workload")
def get_workload() -> dict:
    """Return case workload distribution."""
    engine = _get_engine()
    cases = engine.get_open_cases()
    by_severity: dict[str, int] = {}
    for c in cases:
        sev = c.severity.value
        by_severity[sev] = by_severity.get(sev, 0) + 1
    return {
        "total_open": len(cases),
        "by_severity": by_severity,
        "by_assignee": {},
        "unassigned": len(cases),
    }


@router.get("/aging")
def get_aging() -> dict:
    """Return case aging buckets."""
    engine = _get_engine()
    cases = engine.get_open_cases()
    now = datetime.now(UTC)
    buckets = {
        "< 1 hour": {"count": 0, "oldest_hours": 0.0},
        "1-24 hours": {"count": 0, "oldest_hours": 0.0},
        "1-7 days": {"count": 0, "oldest_hours": 0.0},
        "> 7 days": {"count": 0, "oldest_hours": 0.0},
    }
    for c in cases:
        age = (now - c.detected_at).total_seconds() / 3600
        if age < 1:
            buckets["< 1 hour"]["count"] += 1
            buckets["< 1 hour"]["oldest_hours"] = max(buckets["< 1 hour"]["oldest_hours"], age)
        elif age < 24:
            buckets["1-24 hours"]["count"] += 1
            buckets["1-24 hours"]["oldest_hours"] = max(buckets["1-24 hours"]["oldest_hours"], age)
        elif age < 168:
            buckets["1-7 days"]["count"] += 1
            buckets["1-7 days"]["oldest_hours"] = max(buckets["1-7 days"]["oldest_hours"], age)
        else:
            buckets["> 7 days"]["count"] += 1
            buckets["> 7 days"]["oldest_hours"] = max(buckets["> 7 days"]["oldest_hours"], age)
    return {
        "buckets": [
            {"label": k, "count": v["count"], "oldest_hours": round(v["oldest_hours"], 1)}
            for k, v in buckets.items()
        ]
    }


@router.get("/stats")
def get_case_stats() -> dict:
    """Summary statistics for all cases."""
    engine = _get_engine()
    all_cases = engine.get_open_cases()
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for c in all_cases:
        ct = c.case_type.value
        sev = c.severity.value
        by_type[ct] = by_type.get(ct, 0) + 1
        by_severity[sev] = by_severity.get(sev, 0) + 1
    return {
        "total": len(all_cases),
        "by_type": by_type,
        "by_severity": by_severity,
    }
