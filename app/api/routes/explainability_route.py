"""Explainability routes — human-readable explanations for platform decisions."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.explainability.engine import explainability_engine
from app.core.platform_action_release_gate import PlatformActionReleaseGate

router = APIRouter(prefix="/explain", tags=["explainability"])
_gate = PlatformActionReleaseGate()


@router.get("/block/{dispatch_id}")
def explain_block(dispatch_id: str) -> dict:
    """Why was this action blocked? Returns remediation steps."""
    log = _gate.get_audit_log()
    result = next((r for r in log if r.dispatch_id == dispatch_id), None)
    if not result:
        raise HTTPException(status_code=404, detail=f"No dispatch record found for {dispatch_id}")
    if result.status.value != "blocked":
        raise HTTPException(
            status_code=400,
            detail=f"Action {dispatch_id} was not blocked (status: {result.status.value})",
        )
    explanation = explainability_engine.explain_block(
        {
            "dispatch_id": result.dispatch_id,
            "failure_reason": result.failure_reason or "",
            "dispatched_at": result.dispatched_at.isoformat(),
        }
    )
    return {
        "dispatch_id": dispatch_id,
        "outcome": "blocked",
        "human_summary": explanation.human_summary,
        "blocking_gate": explanation.blocking_gate,
        "blocking_reason": explanation.blocking_reason,
        "gates": [
            {"gate": g.gate_name, "outcome": g.outcome, "detail": g.detail}
            for g in explanation.gates
        ],
        "missing_evidence": explanation.missing_evidence,
        "remediation_steps": explanation.remediation_steps,
    }


@router.get("/release/{package_id}")
def explain_release(package_id: str) -> dict:
    """Why was this action released? Returns evidence used and package hash."""
    package = _gate.get_package(package_id)
    if not package:
        raise HTTPException(
            status_code=404,
            detail=f"No evidence package found for {package_id}",
        )
    explanation = explainability_engine.explain_release(
        {
            "package_id": package.package_id,
            "action_type": package.action_type,
            "origin": package.origin.value,
            "requested_by": package.requested_by,
            "evidence_chain": package.evidence_chain,
            "package_hash": package.package_hash,
            "compiled_at": package.compiled_at.isoformat(),
        }
    )
    return {
        "package_id": package_id,
        "outcome": "released",
        "human_summary": explanation.human_summary,
        "gates_passed": explanation.gates_passed,
        "evidence_used": explanation.evidence_used,
        "package_hash": explanation.package_hash,
        "compiled_at": explanation.compiled_at,
    }


@router.get("/case/{case_id}")
def explain_case(case_id: str) -> dict:
    """Why does this reconciliation case exist?"""
    from app.core.graph.store import ControlGraphStore
    from app.core.reconciliation.cross_plane_engine import CrossPlaneReconciliationEngine

    graph = ControlGraphStore()
    engine = CrossPlaneReconciliationEngine(graph=graph)
    cases = {c.case_id: c for c in engine.get_open_cases()}
    case = cases.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return explainability_engine.explain_case(
        {
            "case_id": case.case_id,
            "case_type": case.case_type.value,
            "severity": case.severity.value,
            "affected_planes": case.affected_planes,
            "violated_rule_id": case.violated_rule_id,
            "remediation_suggestions": case.remediation_suggestions,
        }
    )
