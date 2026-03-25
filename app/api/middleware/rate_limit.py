"""Rate limiting middleware using token bucket per tenant."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass
class _Bucket:
    tokens: float = 100.0
    max_tokens: float = 100.0
    refill_rate: float = 10.0  # tokens per second
    last_refill: float = field(default_factory=time.monotonic)

    def consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-tenant rate limiter using in-memory token buckets.

    For production, replace with Redis-backed sliding window.
    """

    def __init__(
        self,
        app,
        max_tokens: float = 100.0,
        refill_rate: float = 10.0,
        exempt_paths: set[str] | None = None,
    ):
        super().__init__(app)
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.exempt_paths = exempt_paths or {"/health", "/ready", "/metrics"}
        self._buckets: dict[str, _Bucket] = defaultdict(
            lambda: _Bucket(
                tokens=self.max_tokens,
                max_tokens=self.max_tokens,
                refill_rate=self.refill_rate,
            )
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Identify tenant from header or IP
        tenant_key = request.headers.get("X-Tenant-ID", request.client.host if request.client else "unknown")
        bucket = self._buckets[tenant_key]

        if not bucket.consume():
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "retry_after_seconds": 1.0 / self.refill_rate},
                headers={"Retry-After": str(int(1.0 / self.refill_rate) + 1)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
        return response
