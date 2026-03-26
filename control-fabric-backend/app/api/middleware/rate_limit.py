"""Token-bucket rate limiting middleware scoped per tenant."""

from __future__ import annotations

import time
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Paths that are always exempt from rate limiting
_EXEMPT_PREFIXES = ("/health", "/ready", "/metrics")


class _TokenBucket:
    """Simple token-bucket implementation."""

    __slots__ = ("max_tokens", "refill_rate", "_tokens", "_last_refill", "_lock")

    def __init__(self, max_tokens: float, refill_rate: float) -> None:
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate  # tokens per second
        self._tokens = max_tokens
        self._last_refill = time.monotonic()
        self._lock = Lock()

    def consume(self) -> bool:
        """Try to consume one token.  Returns ``True`` if allowed."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.max_tokens, self._tokens + elapsed * self.refill_rate)
            self._last_refill = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-tenant token-bucket rate limiter.

    Parameters
    ----------
    app:
        The ASGI app to wrap.
    max_tokens:
        Maximum burst size (bucket capacity).
    refill_rate:
        Tokens restored per second.
    """

    def __init__(self, app, max_tokens: float = 60.0, refill_rate: float = 10.0) -> None:  # noqa: ANN001
        super().__init__(app)
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self._buckets: dict[str, _TokenBucket] = {}
        self._buckets_lock = Lock()

    def _get_bucket(self, key: str) -> _TokenBucket:
        """Return (or create) the token bucket for *key*."""
        if key not in self._buckets:
            with self._buckets_lock:
                if key not in self._buckets:
                    self._buckets[key] = _TokenBucket(self.max_tokens, self.refill_rate)
        return self._buckets[key]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Exempt health / readiness / metrics endpoints
        if any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES):
            return await call_next(request)

        # Use tenant_id from header or fall back to client IP
        tenant_key = (
            request.headers.get("X-Tenant-ID")
            or request.headers.get("Authorization", "")[:40]
            or (request.client.host if request.client else "unknown")
        )

        bucket = self._get_bucket(tenant_key)
        if not bucket.consume():
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please retry later.",
                    "code": "RATE_LIMIT_EXCEEDED",
                },
                headers={"Retry-After": str(int(1 / self.refill_rate) + 1)},
            )

        return await call_next(request)
