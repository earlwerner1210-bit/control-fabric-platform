"""
Per-tenant rate limiting.

Prevents one tenant from monopolising platform resources.
Limits are configurable per tier.

Default limits:
  Starter:    100 requests/minute, 20 reconciliation runs/hour
  Growth:     500 requests/minute, 100 reconciliation runs/hour
  Enterprise: 2000 requests/minute, unlimited reconciliation runs

Uses Redis counters when available, in-memory fallback otherwise.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


TIER_LIMITS = {
    "starter": {
        "requests_per_minute": 100,
        "reconciliation_per_hour": 20,
        "gate_submissions_per_minute": 50,
    },
    "growth": {
        "requests_per_minute": 500,
        "reconciliation_per_hour": 100,
        "gate_submissions_per_minute": 200,
    },
    "enterprise": {
        "requests_per_minute": 2000,
        "reconciliation_per_hour": -1,  # unlimited
        "gate_submissions_per_minute": 1000,
    },
    "default": {
        "requests_per_minute": 200,
        "reconciliation_per_hour": 50,
        "gate_submissions_per_minute": 100,
    },
}


class TenantRateLimiter:
    """
    Per-tenant rate limiter using sliding window counters.
    Falls back to in-memory when Redis unavailable.
    """

    def __init__(self) -> None:
        self._counters: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        self._tenant_tiers: dict[str, str] = {}
        self._redis = None
        self._try_connect_redis()

    def set_tier(self, tenant_id: str, tier: str) -> None:
        self._tenant_tiers[tenant_id] = tier

    def check(
        self,
        tenant_id: str,
        limit_type: str = "requests_per_minute",
    ) -> tuple[bool, str]:
        """
        Check if tenant is within rate limit.
        Returns (allowed, reason).
        """
        tier = self._tenant_tiers.get(tenant_id, "default")
        limits = TIER_LIMITS.get(tier, TIER_LIMITS["default"])
        limit = limits.get(limit_type, 200)

        if limit == -1:  # unlimited
            return True, "unlimited"

        window_seconds = 60 if "minute" in limit_type else 3600
        key = f"{tenant_id}:{limit_type}"
        now = time.time()

        # Use Redis if available
        if self._redis:
            try:
                pipe = self._redis.pipeline()
                pipe.zadd(key, {str(now): now})
                pipe.zremrangebyscore(key, 0, now - window_seconds)
                pipe.zcard(key)
                pipe.expire(key, window_seconds + 10)
                _, _, count, _ = pipe.execute()
                if count > limit:
                    return (
                        False,
                        f"Rate limit exceeded: {count}/{limit} {limit_type}",
                    )
                return True, f"{count}/{limit}"
            except Exception:
                pass  # Fall through to in-memory

        # In-memory sliding window
        timestamps = self._counters[tenant_id][limit_type]
        cutoff = now - window_seconds
        # Remove expired entries
        self._counters[tenant_id][limit_type] = [t for t in timestamps if t > cutoff]
        self._counters[tenant_id][limit_type].append(now)
        count = len(self._counters[tenant_id][limit_type])

        if count > limit:
            return False, f"Rate limit exceeded: {count}/{limit} {limit_type}"
        return True, f"{count}/{limit}"

    def get_tenant_usage(self, tenant_id: str) -> dict:
        tier = self._tenant_tiers.get(tenant_id, "default")
        result: dict = {"tenant_id": tenant_id, "tier": tier, "limits": {}}
        for limit_type in TIER_LIMITS[tier]:
            allowed, detail = self.check(tenant_id, limit_type)
            result["limits"][limit_type] = {
                "within_limit": allowed,
                "detail": detail,
                "max": TIER_LIMITS[tier][limit_type],
            }
        return result

    def _try_connect_redis(self) -> None:
        redis_url = os.getenv("REDIS_URL", "")
        if not redis_url:
            return
        try:
            import redis as redis_lib

            self._redis = redis_lib.from_url(redis_url, decode_responses=True, socket_timeout=1)
            self._redis.ping()
        except Exception:
            self._redis = None


# Singleton
tenant_rate_limiter = TenantRateLimiter()
