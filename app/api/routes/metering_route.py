"""
Usage metering API — tenant usage stats and Stripe reporting.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth.middleware import CurrentUser, get_current_user
from app.core.metering.meter import metering_engine

router = APIRouter(prefix="/metering", tags=["metering"])


@router.get("/usage/{tenant_id}")
def get_tenant_usage(
    tenant_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if current_user.tenant_id != tenant_id and "platform_admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Access denied")
    usage = metering_engine.get_usage(tenant_id)
    return {"tenant_id": tenant_id, "usage": usage, "total_events": sum(usage.values())}


@router.get("/summary/{tenant_id}")
def get_billing_summary(
    tenant_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if current_user.tenant_id != tenant_id and "platform_admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Access denied")
    return asdict(metering_engine.get_summary(tenant_id))


@router.post("/report/{tenant_id}/stripe")
def report_to_stripe(
    tenant_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if "platform_admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Platform admin required")
    return metering_engine.report_to_stripe(tenant_id)


@router.get("/tenants")
def list_tenants(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if "platform_admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Platform admin required")
    tenants = metering_engine.get_all_tenants()
    summaries = [
        {
            "tenant_id": tid,
            "total_events": metering_engine.get_summary(tid).total_events,
            "estimated_cost_gbp": metering_engine.get_summary(tid).estimated_cost_gbp,
        }
        for tid in tenants
    ]
    return {
        "tenant_count": len(summaries),
        "tenants": sorted(summaries, key=lambda x: x["total_events"], reverse=True),
    }


@router.get("/overview")
def get_overview() -> dict:
    """Platform-wide totals — no auth required."""
    totals: dict[str, int] = {}
    for tid in metering_engine.get_all_tenants():
        for et, count in metering_engine.get_usage(tid).items():
            totals[et] = totals.get(et, 0) + count
    return {
        "total_tenants": len(metering_engine.get_all_tenants()),
        "total_events": sum(totals.values()),
        "event_breakdown": totals,
    }
