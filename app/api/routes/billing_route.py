"""
Billing API — plan status, usage, invoices, portal.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth.middleware import CurrentUser, get_current_user
from app.core.billing.stripe_billing import PLAN_LIMITS, stripe_billing

router = APIRouter(prefix="/billing", tags=["billing"])


class CreateCustomerBody(BaseModel):
    email: str
    name: str
    plan: str = "starter"


class SetPilotBody(BaseModel):
    tenant_id: str


@router.get("/status")
def get_status(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Current plan, usage, and limits for the authenticated tenant."""
    return stripe_billing.get_subscription_status(current_user.tenant_id)


@router.get("/plans")
def list_plans() -> dict:
    """All available plans with limits and pricing."""
    return {
        "plans": [
            {
                "plan": plan,
                "limits": {k: v for k, v in limits.items() if k not in ("note",)},
                "note": limits.get("note", ""),
            }
            for plan, limits in PLAN_LIMITS.items()
            if plan != "pilot"
        ]
    }


@router.get("/usage")
def get_usage(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Current metered usage for the authenticated tenant."""
    from dataclasses import asdict

    from app.core.metering.meter import metering_engine

    usage = metering_engine.get_summary(current_user.tenant_id)
    return asdict(usage)


@router.get("/invoices")
def get_invoices(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Invoice history."""
    invoices = stripe_billing.get_invoices(current_user.tenant_id)
    return {"invoices": invoices}


@router.get("/portal")
def get_portal(
    return_url: str = "",
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Generate a Stripe billing portal URL for self-service plan management."""
    url = stripe_billing.get_billing_portal_url(current_user.tenant_id, return_url)
    if not url:
        return {
            "portal_url": None,
            "note": (
                "Billing portal requires Stripe configuration."
                " Contact support to manage your subscription."
            ),
        }
    return {"portal_url": url}


@router.post("/report/stripe")
def report_to_stripe_now(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Manually trigger a usage report to Stripe. Platform admin only."""
    if "platform_admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Platform admin required")
    record = stripe_billing.report_usage(current_user.tenant_id)
    return {
        "tenant_id": record.tenant_id,
        "period": record.period,
        "total_billable_units": record.total_billable_units,
        "stripe_reported": record.stripe_reported,
        "estimated_cost_gbp": record.estimated_cost_gbp,
    }


@router.post("/pilot")
def set_pilot_plan(
    body: SetPilotBody,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Set a tenant to pilot plan. Platform admin only."""
    if "platform_admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Platform admin required")
    customer = stripe_billing.set_pilot_plan(body.tenant_id)
    return {
        "tenant_id": customer.tenant_id,
        "plan": customer.plan,
        "status": customer.status,
        "note": "Pilot plan active. Commercial terms handled directly.",
    }


@router.get("/enforce/{action}")
def check_plan_limits(
    action: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Check if an action is within plan limits."""
    result = stripe_billing.check_plan_limits(current_user.tenant_id, action)
    return {
        "allowed": result.allowed,
        "reason": result.reason,
        "plan": result.plan,
        "upgrade_to": result.upgrade_to,
    }
