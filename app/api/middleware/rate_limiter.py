"""
Rate limiting configuration using slowapi (FastAPI-compatible).
Protects the API from abuse and ensures fair use across tenants.

Limits:
  - Default: 100 requests/minute per IP
  - Authenticated: 500 requests/minute per user
  - Reconciliation run: 10 requests/minute per tenant (expensive operation)
  - Bulk operations: 20 requests/minute per tenant
"""

from __future__ import annotations

import os

from fastapi import Request

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    def _get_tenant_or_ip(request: Request) -> str:
        tenant = getattr(request.state, "tenant_id", None)
        return tenant or get_remote_address(request)

    limiter = Limiter(
        key_func=_get_tenant_or_ip,
        default_limits=["100/minute"],
        storage_uri=os.getenv("REDIS_URL", "memory://"),
    )

    RATE_LIMIT_AVAILABLE = True

except ImportError:

    class _NoOpLimiter:
        def limit(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

        def shared_limit(self, *args, **kwargs):
            return self.limit(*args, **kwargs)

    limiter = _NoOpLimiter()  # type: ignore[assignment]
    RATE_LIMIT_AVAILABLE = False


STANDARD_LIMIT = "100/minute"
EXPENSIVE_LIMIT = "10/minute"
BULK_LIMIT = "20/minute"
AUTH_LIMIT = "10/minute"
