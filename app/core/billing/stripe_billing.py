"""
Stripe Billing — End-to-End Integration

Handles the full commercial lifecycle:
  1. Customer creation   — new tenant -> Stripe customer
  2. Subscription management — plan selection -> Stripe subscription
  3. Usage reporting     — gate submissions -> Stripe usage records
  4. Invoice retrieval   — current + past invoices
  5. Plan enforcement    — block over-quota actions
  6. Billing portal      — customer self-service

Stripe products and price IDs must be configured in environment:
  STRIPE_STARTER_PRICE_ID    — GBP 2,750/month recurring
  STRIPE_GROWTH_PRICE_ID     — GBP 9,000/month recurring
  STRIPE_ENTERPRISE_PRICE_ID — GBP 42,500/month recurring
  STRIPE_USAGE_PRICE_ID      — per-submission metered price

Plan limits (enforced by platform):
  starter:    100 gate submissions/day, 5 users, 1 environment
  growth:     1,000 gate submissions/day, 25 users, 3 environments
  enterprise: unlimited submissions, unlimited users, unlimited environments
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone

logger = logging.getLogger(__name__)

PLAN_LIMITS = {
    "starter": {
        "gate_submissions_per_day": 100,
        "max_users": 5,
        "max_environments": 1,
        "connectors_allowed": ["github", "jira"],
        "domain_packs_included": 1,
        "support": "email",
        "monthly_price_gbp": 2750,
    },
    "growth": {
        "gate_submissions_per_day": 1000,
        "max_users": 25,
        "max_environments": 3,
        "connectors_allowed": ["github", "jira", "servicenow", "azure_devops"],
        "domain_packs_included": 3,
        "support": "priority_email",
        "monthly_price_gbp": 9000,
    },
    "enterprise": {
        "gate_submissions_per_day": -1,  # unlimited
        "max_users": -1,
        "max_environments": -1,
        "connectors_allowed": [
            "github",
            "jira",
            "servicenow",
            "azure_devops",
            "custom",
        ],
        "domain_packs_included": -1,
        "support": "dedicated_csm",
        "monthly_price_gbp": 42500,
    },
    "pilot": {
        "gate_submissions_per_day": 500,
        "max_users": 10,
        "max_environments": 2,
        "connectors_allowed": ["github", "jira", "servicenow", "azure_devops"],
        "domain_packs_included": 8,
        "support": "dedicated_csm",
        "monthly_price_gbp": 0,  # Pilot is complimentary
        "note": "Pilot plan — commercial terms agreed separately",
    },
}

STRIPE_PRICE_IDS = {
    "starter": os.getenv("STRIPE_STARTER_PRICE_ID", ""),
    "growth": os.getenv("STRIPE_GROWTH_PRICE_ID", ""),
    "enterprise": os.getenv("STRIPE_ENTERPRISE_PRICE_ID", ""),
    "usage": os.getenv("STRIPE_USAGE_PRICE_ID", ""),
}


@dataclass
class BillingCustomer:
    tenant_id: str
    stripe_customer_id: str = ""
    stripe_subscription_id: str = ""
    stripe_subscription_item_id: str = ""
    plan: str = "starter"
    status: str = "active"
    trial_end: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class UsageRecord:
    tenant_id: str
    period: str
    gate_submissions: int = 0
    reconciliation_runs: int = 0
    slm_enrichments: int = 0
    total_billable_units: int = 0
    estimated_cost_gbp: float = 0.0
    stripe_reported: bool = False
    reported_at: str | None = None


@dataclass
class PlanEnforcementResult:
    allowed: bool
    reason: str
    plan: str
    limit: int
    current_usage: int
    upgrade_to: str | None = None


# In-memory store — in production use DB
_customers: dict[str, BillingCustomer] = {}


class StripeBillingService:
    """
    Manages Stripe billing for all platform tenants.
    Handles customer creation, subscription management,
    usage metering, and plan enforcement.
    """

    def __init__(self) -> None:
        self._stripe_configured = bool(os.getenv("STRIPE_SECRET_KEY"))
        if self._stripe_configured:
            import stripe

            stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

    # -- Customer management -------------------------------------------------

    def get_or_create_customer(
        self,
        tenant_id: str,
        email: str,
        name: str,
        plan: str = "starter",
    ) -> BillingCustomer:
        """Get existing customer or create new one in Stripe."""
        if tenant_id in _customers:
            return _customers[tenant_id]

        customer = BillingCustomer(tenant_id=tenant_id, plan=plan)

        if self._stripe_configured:
            try:
                import stripe

                existing = stripe.Customer.list(email=email, limit=1)
                if existing.data:
                    stripe_customer = existing.data[0]
                else:
                    stripe_customer = stripe.Customer.create(
                        email=email,
                        name=name,
                        metadata={
                            "tenant_id": tenant_id,
                            "plan": plan,
                            "platform": "control_fabric",
                        },
                    )
                customer.stripe_customer_id = stripe_customer.id
                logger.info(
                    "Stripe customer: tenant=%s customer=%s",
                    tenant_id,
                    stripe_customer.id,
                )
            except Exception as e:
                logger.error("Stripe customer creation failed: %s", e)

        _customers[tenant_id] = customer
        return customer

    def create_subscription(
        self,
        tenant_id: str,
        plan: str,
        trial_days: int = 0,
    ) -> BillingCustomer:
        """Create a Stripe subscription for a tenant."""
        customer = _customers.get(tenant_id)
        if not customer:
            raise ValueError(
                f"Customer not found for tenant {tenant_id}. Call get_or_create_customer first."
            )

        price_id = STRIPE_PRICE_IDS.get(plan)

        if self._stripe_configured and price_id and customer.stripe_customer_id:
            try:
                import stripe

                params: dict = {
                    "customer": customer.stripe_customer_id,
                    "items": [{"price": price_id}],
                    "metadata": {"tenant_id": tenant_id},
                }
                if trial_days > 0:
                    params["trial_period_days"] = trial_days
                sub = stripe.Subscription.create(**params)
                customer.stripe_subscription_id = sub.id
                customer.plan = plan
                customer.status = sub.status
                if sub.items.data:
                    customer.stripe_subscription_item_id = sub.items.data[0].id
                logger.info(
                    "Stripe subscription: tenant=%s plan=%s sub=%s",
                    tenant_id,
                    plan,
                    sub.id,
                )
            except Exception as e:
                logger.error("Stripe subscription creation failed: %s", e)
        else:
            customer.plan = plan
            customer.status = "active"

        _customers[tenant_id] = customer
        return customer

    # -- Usage reporting -----------------------------------------------------

    def report_usage(self, tenant_id: str) -> UsageRecord:
        """
        Pull current usage from metering engine and push to Stripe.
        Called hourly by Celery task.
        """
        from app.core.metering.meter import metering_engine

        usage = metering_engine.get_usage(tenant_id)

        gate_subs = usage.get("gate_submission", 0)
        recon_runs = usage.get("reconciliation_run", 0)
        slm_enrichments = usage.get("slm_enrichment", 0)
        total_billable = gate_subs + recon_runs + slm_enrichments

        record = UsageRecord(
            tenant_id=tenant_id,
            period=datetime.now(UTC).strftime("%Y-%m"),
            gate_submissions=gate_subs,
            reconciliation_runs=recon_runs,
            slm_enrichments=slm_enrichments,
            total_billable_units=total_billable,
            estimated_cost_gbp=self._estimate_cost(tenant_id, total_billable),
        )

        if not self._stripe_configured:
            record.stripe_reported = False
            return record

        customer = _customers.get(tenant_id)
        if not customer or not customer.stripe_subscription_item_id:
            logger.debug("No Stripe subscription item for tenant %s — skipping", tenant_id)
            return record

        try:
            import stripe

            stripe.SubscriptionItem.create_usage_record(
                customer.stripe_subscription_item_id,
                quantity=total_billable,
                timestamp=int(time.time()),
                action="set",
            )
            record.stripe_reported = True
            record.reported_at = datetime.now(UTC).isoformat()
            logger.info(
                "Usage reported to Stripe: tenant=%s units=%d",
                tenant_id,
                total_billable,
            )
        except Exception as e:
            logger.error("Stripe usage reporting failed for %s: %s", tenant_id, e)

        return record

    def report_all_tenants(self) -> list[UsageRecord]:
        """Report usage for all known tenants — called by Celery beat."""
        from app.core.metering.meter import metering_engine

        tenants = metering_engine.get_all_tenants()
        results = []
        for tenant_id in tenants:
            try:
                results.append(self.report_usage(tenant_id))
            except Exception as e:
                logger.error("Usage report failed for %s: %s", tenant_id, e)
        return results

    # -- Plan enforcement ----------------------------------------------------

    def check_plan_limits(
        self,
        tenant_id: str,
        action: str = "gate_submission",
    ) -> PlanEnforcementResult:
        """
        Check whether a tenant is within their plan limits.
        Called before gate submissions to enforce quotas.
        """
        customer = _customers.get(tenant_id)
        plan = customer.plan if customer else "starter"
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])

        if action == "gate_submission":
            limit = limits["gate_submissions_per_day"]
            if limit == -1:
                return PlanEnforcementResult(
                    allowed=True,
                    reason="unlimited",
                    plan=plan,
                    limit=-1,
                    current_usage=0,
                )
            try:
                from app.core.metering.meter import metering_engine

                usage = metering_engine.get_usage(tenant_id)
                current = usage.get("gate_submission", 0)
                if current >= limit:
                    upgrade_to = {
                        "starter": "growth",
                        "growth": "enterprise",
                    }.get(plan)
                    return PlanEnforcementResult(
                        allowed=False,
                        reason=(f"Daily limit of {limit} gate submissions reached on {plan} plan"),
                        plan=plan,
                        limit=limit,
                        current_usage=current,
                        upgrade_to=upgrade_to,
                    )
                return PlanEnforcementResult(
                    allowed=True,
                    reason=f"{current}/{limit} submissions today",
                    plan=plan,
                    limit=limit,
                    current_usage=current,
                )
            except Exception:
                return PlanEnforcementResult(
                    allowed=True,
                    reason="metering unavailable — allowing",
                    plan=plan,
                    limit=limit,
                    current_usage=0,
                )

        return PlanEnforcementResult(
            allowed=True,
            reason="action not quota-tracked",
            plan=plan,
            limit=-1,
            current_usage=0,
        )

    # -- Customer portal -----------------------------------------------------

    def get_billing_portal_url(
        self,
        tenant_id: str,
        return_url: str = "",
    ) -> str | None:
        """Generate a Stripe billing portal URL for self-service management."""
        customer = _customers.get(tenant_id)
        if not customer or not customer.stripe_customer_id:
            return None
        if not self._stripe_configured:
            return None
        try:
            import stripe

            session = stripe.billing_portal.Session.create(
                customer=customer.stripe_customer_id,
                return_url=return_url or "https://console.control-fabric.io",
            )
            return session.url
        except Exception as e:
            logger.error("Billing portal URL failed: %s", e)
            return None

    def get_invoices(self, tenant_id: str, limit: int = 10) -> list[dict]:
        """Get invoice history for a tenant."""
        customer = _customers.get(tenant_id)
        if not customer or not customer.stripe_customer_id:
            return []
        if not self._stripe_configured:
            return [{"note": ("Stripe not configured — contact support for invoice history")}]
        try:
            import stripe

            invoices = stripe.Invoice.list(
                customer=customer.stripe_customer_id,
                limit=limit,
            )
            return [
                {
                    "invoice_id": inv.id,
                    "amount_gbp": round(inv.amount_paid / 100, 2),
                    "status": inv.status,
                    "period_start": datetime.fromtimestamp(inv.period_start, tz=UTC).isoformat(),
                    "period_end": datetime.fromtimestamp(inv.period_end, tz=UTC).isoformat(),
                    "pdf_url": inv.invoice_pdf,
                    "hosted_url": inv.hosted_invoice_url,
                }
                for inv in invoices.data
            ]
        except Exception as e:
            logger.error("Invoice retrieval failed: %s", e)
            return []

    def get_subscription_status(self, tenant_id: str) -> dict:
        """Get full subscription status for a tenant."""
        customer = _customers.get(tenant_id)
        if not customer:
            return {
                "tenant_id": tenant_id,
                "plan": "starter",
                "status": "no_subscription",
                "stripe_configured": self._stripe_configured,
            }

        plan = customer.plan
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])

        from app.core.metering.meter import metering_engine

        usage = metering_engine.get_usage(tenant_id)

        return {
            "tenant_id": tenant_id,
            "plan": plan,
            "status": customer.status,
            "stripe_customer_id": customer.stripe_customer_id,
            "stripe_subscription_id": customer.stripe_subscription_id,
            "monthly_price_gbp": limits.get("monthly_price_gbp", 0),
            "note": limits.get("note", ""),
            "limits": {k: v for k, v in limits.items() if k not in ("monthly_price_gbp", "note")},
            "current_usage": {
                "gate_submissions": usage.get("gate_submission", 0),
                "reconciliation_runs": usage.get("reconciliation_run", 0),
                "slm_enrichments": usage.get("slm_enrichment", 0),
                "total_billable": (
                    usage.get("gate_submission", 0)
                    + usage.get("reconciliation_run", 0)
                    + usage.get("slm_enrichment", 0)
                ),
            },
        }

    def _estimate_cost(self, tenant_id: str, total_billable: int) -> float:
        customer = _customers.get(tenant_id)
        plan = customer.plan if customer else "starter"
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])
        monthly = limits.get("monthly_price_gbp", 0)
        days_in_month = 30
        daily_rate = monthly / days_in_month
        overage = max(0, total_billable - limits.get("gate_submissions_per_day", 100))
        return round(daily_rate + overage * 0.01, 2)

    def set_pilot_plan(self, tenant_id: str) -> BillingCustomer:
        """
        Set a tenant to pilot plan — complimentary, commercial terms separate.
        Used for Vodafone and all initial pilot customers.
        """
        customer = _customers.get(tenant_id)
        if not customer:
            customer = BillingCustomer(
                tenant_id=tenant_id,
                plan="pilot",
                status="active",
            )
        customer.plan = "pilot"
        customer.status = "active"
        _customers[tenant_id] = customer
        logger.info("Pilot plan set for tenant %s", tenant_id)
        return customer


# Singleton
stripe_billing = StripeBillingService()
