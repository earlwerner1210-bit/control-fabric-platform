"""Customer-facing reports API."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

router = APIRouter(prefix="/reports", tags=["reports"])

AVAILABLE_REPORTS = [
    {
        "report_id": "governance-posture",
        "title": "Governance Posture",
        "description": "Overall governance coverage and gap analysis.",
    },
    {
        "report_id": "release-gate-activity",
        "title": "Release Gate Activity",
        "description": "All release gate submissions, outcomes, and evidence.",
    },
    {
        "report_id": "evidence-completeness",
        "title": "Evidence Completeness",
        "description": "Evidence coverage by release type and environment.",
    },
    {
        "report_id": "exception-history",
        "title": "Exception History",
        "description": "All exception requests, approvals, and expirations.",
    },
    {
        "report_id": "reconciliation-trend",
        "title": "Reconciliation Trend",
        "description": "Case volume and resolution over time.",
    },
    {
        "report_id": "policy-compliance",
        "title": "Policy Compliance",
        "description": "Policy violations, blocks, and compliance rate.",
    },
]


def _window_to_days(window: str) -> int:
    mapping = {"7d": 7, "30d": 30, "90d": 90}
    return mapping.get(window, 30)


def _generate_governance_posture(days: int) -> dict:
    return {
        "coverage_pct": 87.5,
        "total_objects": 142,
        "governed_objects": 124,
        "ungoverned_objects": 18,
        "critical_gaps": 3,
        "trend": "improving" if days > 7 else "stable",
    }


def _generate_release_gate_activity(days: int) -> dict:
    return {
        "total_submissions": days * 4,
        "released": days * 3,
        "blocked": days,
        "pass_rate_pct": 75.0,
        "top_blocking_gate": "evidence_sufficiency",
        "top_blocking_count": max(1, days // 3),
    }


def _generate_evidence_completeness(days: int) -> dict:
    return {
        "overall_completeness_pct": 82.0,
        "by_type": {
            "ci_result": 95.0,
            "security_scan": 78.0,
            "load_test": 65.0,
            "change_request": 88.0,
        },
        "missing_evidence_count": max(1, days // 5),
    }


def _generate_exception_history(days: int) -> dict:
    return {
        "total_exceptions": max(1, days // 10),
        "approved": max(1, days // 12),
        "denied": max(0, days // 30),
        "expired": max(0, days // 15),
        "active": 1,
        "avg_duration_hours": 3.5,
    }


def _generate_reconciliation_trend(days: int) -> dict:
    return {
        "total_cases_detected": days * 2,
        "resolved": int(days * 1.6),
        "open": int(days * 0.4),
        "mean_time_to_resolve_hours": 18.5,
        "by_severity": {
            "critical": max(1, days // 10),
            "high": max(1, days // 5),
            "medium": days // 2,
            "low": days,
        },
    }


def _generate_policy_compliance(days: int) -> dict:
    return {
        "total_evaluations": days * 6,
        "compliant": int(days * 5.4),
        "violations": int(days * 0.6),
        "compliance_rate_pct": 90.0,
        "most_violated_policy": "Production Release Policy",
    }


REPORT_GENERATORS = {
    "governance-posture": _generate_governance_posture,
    "release-gate-activity": _generate_release_gate_activity,
    "evidence-completeness": _generate_evidence_completeness,
    "exception-history": _generate_exception_history,
    "reconciliation-trend": _generate_reconciliation_trend,
    "policy-compliance": _generate_policy_compliance,
}


@router.get("/summary")
def get_report_summary() -> dict:
    """List all available reports."""
    return {"available_reports": AVAILABLE_REPORTS}


@router.get("/{report_id}")
def get_report(report_id: str, window: str = "30d") -> dict:
    """Generate a report by ID for the given time window."""
    generator = REPORT_GENERATORS.get(report_id)
    if not generator:
        return {"error": f"Report '{report_id}' not found"}

    meta = next((r for r in AVAILABLE_REPORTS if r["report_id"] == report_id), None)
    days = _window_to_days(window)
    return {
        "report_id": report_id,
        "title": meta["title"] if meta else report_id,
        "window": window,
        "generated_at": datetime.now(UTC).isoformat(),
        "data": generator(days),
    }
