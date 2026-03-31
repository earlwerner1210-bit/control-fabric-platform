"""
Customer health scoring API.
GET /health-scores/{tenant_id}   — score for one tenant
GET /health-scores/all           — all tenants (CSM view)
GET /health-scores/at-risk       — only at-risk tenants
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth.middleware import CurrentUser, get_current_user
from app.core.health_scoring.scorer import health_scorer

router = APIRouter(prefix="/health-scores", tags=["health-scores"])


@router.get("/all")
def get_all_scores(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if "platform_admin" not in current_user.roles and "auditor" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Platform admin or auditor required")
    scores = health_scorer.score_all_tenants()
    return {
        "total_tenants": len(scores),
        "healthy": sum(1 for s in scores if s.risk_level == "healthy"),
        "at_risk": sum(1 for s in scores if s.risk_level == "at_risk"),
        "churn_risk": sum(1 for s in scores if s.risk_level == "churn_risk"),
        "scores": [asdict(s) for s in sorted(scores, key=lambda x: x.overall_score)],
    }


@router.get("/at-risk")
def get_at_risk(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if "platform_admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Platform admin required")
    at_risk = health_scorer.get_at_risk_tenants()
    return {"count": len(at_risk), "tenants": [asdict(s) for s in at_risk]}


@router.get("/{tenant_id}")
def get_tenant_score(
    tenant_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if current_user.tenant_id != tenant_id and "platform_admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Access denied")
    score = health_scorer.score_tenant(tenant_id)
    return asdict(score)
