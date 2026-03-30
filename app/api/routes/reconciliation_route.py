"""
Control Fabric Platform — Reconciliation API Routes

Patent Claim (Theme 2): Cross-plane reconciliation engine exposed via REST.
All detected cases are formally committed — none can be suppressed.

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.core.graph.store import ControlGraphStore
from app.core.reconciliation.cross_plane_engine import (
    CrossPlaneReconciliationEngine,
    ReconciliationCaseSeverity,
    ReconciliationCaseType,
    build_core_reconciliation_rules,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])

# Platform-shared graph instance
# In production this is injected via dependency injection
_graph = ControlGraphStore()
_engine = CrossPlaneReconciliationEngine(graph=_graph)


@router.post("/run", summary="Run full cross-plane reconciliation")
def run_reconciliation() -> dict[str, Any]:
    """
    Patent Claim (Theme 2): Detects semantic gaps, conflicts, and orphans.
    Cases cannot be suppressed or bypassed.
    """
    cases = _engine.run_full_reconciliation()

    return {
        "total_cases": _engine.total_cases,
        "open_cases": _engine.open_case_count,
        "new_cases_this_run": len(cases),
        "by_severity": {
            "critical": len(_engine.get_cases_by_severity(ReconciliationCaseSeverity.CRITICAL)),
            "high": len(_engine.get_cases_by_severity(ReconciliationCaseSeverity.HIGH)),
            "medium": len(_engine.get_cases_by_severity(ReconciliationCaseSeverity.MEDIUM)),
            "low": len(_engine.get_cases_by_severity(ReconciliationCaseSeverity.LOW)),
        },
        "by_type": {
            "gap": len([c for c in cases if c.case_type == ReconciliationCaseType.GAP]),
            "conflict": len([c for c in cases if c.case_type == ReconciliationCaseType.CONFLICT]),
            "orphan": len([c for c in cases if c.case_type == ReconciliationCaseType.ORPHAN]),
        },
        "cases": [
            {
                "case_id": c.case_id,
                "case_type": c.case_type.value,
                "severity": c.severity.value,
                "status": c.status.value,
                "title": c.title,
                "affected_objects": c.affected_object_ids,
                "affected_planes": c.affected_planes,
                "violated_rule_id": c.violated_rule_id,
                "remediation_suggestions": c.remediation_suggestions,
                "detected_at": c.detected_at.isoformat(),
            }
            for c in cases
        ],
    }


@router.get("/cases", summary="Get all open reconciliation cases")
def get_open_cases() -> dict[str, Any]:
    cases = _engine.get_open_cases()
    return {
        "open_case_count": len(cases),
        "cases": [
            {
                "case_id": c.case_id,
                "case_type": c.case_type.value,
                "severity": c.severity.value,
                "title": c.title,
                "affected_planes": c.affected_planes,
                "detected_at": c.detected_at.isoformat(),
            }
            for c in cases
        ],
    }


@router.get("/cases/{case_id}", summary="Get a specific reconciliation case")
def get_case(case_id: str) -> dict[str, Any]:
    all_cases = {c.case_id: c for c in _engine.get_open_cases()}
    case = all_cases.get(case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found or already resolved.",
        )
    return {
        "case_id": case.case_id,
        "case_type": case.case_type.value,
        "severity": case.severity.value,
        "status": case.status.value,
        "title": case.title,
        "description": case.description,
        "affected_objects": case.affected_object_ids,
        "affected_planes": case.affected_planes,
        "violated_rule_id": case.violated_rule_id,
        "missing_relationship_type": (
            case.missing_relationship_type.value if case.missing_relationship_type else None
        ),
        "remediation_suggestions": case.remediation_suggestions,
        "severity_score": case.severity_score,
        "detected_at": case.detected_at.isoformat(),
        "case_hash": case.case_hash,
    }


@router.post("/cases/{case_id}/resolve", summary="Resolve a case through the release gate")
def resolve_case(case_id: str, resolved_by: str, resolution_note: str) -> dict[str, Any]:
    """
    Patent Claim (Theme 3+4): Case resolution is a governed output.
    Passes through the platform-wide release gate before committing.
    """
    from app.core.platform_action_release_gate import PlatformActionReleaseGate

    gate = PlatformActionReleaseGate()
    try:
        resolved = _engine.mark_case_resolved(
            case_id=case_id,
            resolved_by=resolved_by,
            resolution_note=resolution_note,
            release_gate=gate,
        )
        return {
            "case_id": resolved.case_id,
            "status": resolved.status.value,
            "resolved_at": (resolved.resolved_at.isoformat() if resolved.resolved_at else None),
            "gate_submissions": gate.total_submitted,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/rules", summary="List all active reconciliation rules")
def get_rules() -> dict[str, Any]:
    rules = build_core_reconciliation_rules()
    return {
        "rule_count": len(rules),
        "rules": [
            {
                "rule_id": r.rule_id,
                "domain_pack": r.domain_pack,
                "rule_name": r.rule_name,
                "description": r.description,
                "source_plane": r.source_plane,
                "target_plane": r.target_plane,
                "required_relationship": r.required_relationship.value,
                "severity": r.severity.value,
                "enabled": r.enabled,
            }
            for r in rules
        ],
    }
