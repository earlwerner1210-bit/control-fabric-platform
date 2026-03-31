"""
Usage Metering Engine

Records platform usage events for billing and analytics.
Every metered event is non-blocking — metering never breaks
the platform even if Redis or Stripe is unavailable.

Metered events:
  gate_submission, gate_block, gate_release,
  reconciliation_run, reconciliation_case,
  connector_fetch, webhook_received,
  slm_enrichment, audit_export, domain_pack_install

Stripe integration:
  Usage records pushed hourly via Celery task.
  Each tenant maps to a Stripe subscription item.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

EVENT_UNIT_COSTS_PENCE = {
    "gate_submission": 1,
    "gate_block": 0,
    "gate_release": 0,
    "reconciliation_run": 10,
    "reconciliation_case": 0,
    "connector_fetch": 0,
    "webhook_received": 0,
    "slm_enrichment": 5,
    "audit_export": 50,
    "domain_pack_install": 0,
}

BILLABLE_EVENTS = {"gate_submission", "reconciliation_run", "slm_enrichment"}


@dataclass
class MeterEvent:
    event_type: str
    tenant_id: str
    quantity: int = 1
    recorded_at: float = field(default_factory=time.time)


@dataclass
class UsageSummary:
    tenant_id: str
    period_start: str
    period_end: str
    events: dict
    total_events: int
    billable_units: int
    estimated_cost_gbp: float


class MeteringEngine:
    """
    Records platform usage events and optionally reports to Stripe.
    In-memory with Redis persistence. Falls back to in-memory if
    Redis is unavailable.
    """

    def __init__(self) -> None:
        self._counters: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._events: list[MeterEvent] = []
        self._redis = None
        self._stripe_configured = bool(os.getenv("STRIPE_SECRET_KEY"))
        self._try_connect_redis()

    def record(
        self,
        event_type: str,
        tenant_id: str = "default",
        quantity: int = 1,
        metadata: dict | None = None,
    ) -> None:
        """Record a metered event. Never raises."""
        try:
            event = MeterEvent(event_type=event_type, tenant_id=tenant_id, quantity=quantity)
            self._counters[tenant_id][event_type] += quantity
            self._events.append(event)
            self._push_to_redis(event)
        except Exception as e:
            logger.error("Metering record failed (non-fatal): %s", e)

    def get_usage(self, tenant_id: str, event_type: str | None = None) -> dict:
        if event_type:
            return {event_type: self._counters[tenant_id].get(event_type, 0)}
        return dict(self._counters[tenant_id])

    def get_summary(self, tenant_id: str) -> UsageSummary:
        events = dict(self._counters[tenant_id])
        total = sum(events.values())
        cost_pence = sum(events.get(et, 0) * cost for et, cost in EVENT_UNIT_COSTS_PENCE.items())
        billable = sum(events.get(et, 0) for et in BILLABLE_EVENTS)
        return UsageSummary(
            tenant_id=tenant_id,
            period_start=datetime.now(UTC).strftime("%Y-%m-01"),
            period_end=datetime.now(UTC).strftime("%Y-%m-%d"),
            events=events,
            total_events=total,
            billable_units=billable,
            estimated_cost_gbp=round(cost_pence / 100, 2),
        )

    def get_all_tenants(self) -> list[str]:
        return list(self._counters.keys())

    def report_to_stripe(self, tenant_id: str) -> dict:
        if not self._stripe_configured:
            return {"reported": False, "reason": "Stripe not configured — set STRIPE_SECRET_KEY"}
        try:
            import stripe

            stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
            sub_item_id = self._get_subscription_item_id(tenant_id)
            if not sub_item_id:
                return {"reported": False, "reason": f"No Stripe subscription item for {tenant_id}"}
            usage = self.get_usage(tenant_id)
            total_billable = sum(usage.get(et, 0) for et in BILLABLE_EVENTS)
            if total_billable == 0:
                return {"reported": True, "units": 0, "note": "No billable events this period"}
            record = stripe.SubscriptionItem.create_usage_record(
                sub_item_id,
                quantity=total_billable,
                timestamp=int(time.time()),
                action="set",
            )
            logger.info(
                "Stripe usage: tenant=%s units=%d record=%s", tenant_id, total_billable, record.id
            )
            return {"reported": True, "units": total_billable, "stripe_record_id": record.id}
        except Exception as e:
            logger.error("Stripe reporting failed: %s", e)
            return {"reported": False, "error": str(e)}

    def _push_to_redis(self, event: MeterEvent) -> None:
        if not self._redis:
            return
        try:
            key = f"cfp:meter:{event.tenant_id}:{event.event_type}"
            self._redis.incrby(key, event.quantity)
            self._redis.expire(key, 86400 * 35)
        except Exception:
            pass

    def _try_connect_redis(self) -> None:
        redis_url = os.getenv("REDIS_URL", "")
        if not redis_url:
            return
        try:
            import redis as redis_lib

            self._redis = redis_lib.from_url(redis_url, decode_responses=True, socket_timeout=2)
            self._redis.ping()
            logger.info("Metering: Redis connected")
        except Exception as e:
            logger.warning("Metering: Redis unavailable (%s) — in-memory fallback", e)
            self._redis = None

    def _get_subscription_item_id(self, tenant_id: str) -> str | None:
        env_key = f"STRIPE_SUB_ITEM_{tenant_id.upper().replace('-', '_')}"
        return os.getenv(env_key, os.getenv("STRIPE_DEFAULT_SUB_ITEM_ID", ""))


# Module-level singleton
metering_engine = MeteringEngine()


def meter(event_type: str, tenant_id: str = "default", quantity: int = 1) -> None:
    """Convenience function — import and call anywhere."""
    metering_engine.record(event_type, tenant_id, quantity)
