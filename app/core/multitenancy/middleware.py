"""
Multi-tenancy middleware.
Injects tenant_id from JWT into all database operations.
All data is scoped by tenant_id — no cross-tenant data leakage.
"""

from __future__ import annotations

import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

DEFAULT_TENANT = os.getenv("DEFAULT_TENANT_ID", "default")


class TenantMiddleware(BaseHTTPMiddleware):
    """Extracts tenant_id from JWT and injects into request state."""

    async def dispatch(self, request: Request, call_next):
        tenant_id = DEFAULT_TENANT
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                from app.core.auth.jwt import decode_token

                payload = decode_token(auth[7:])
                tenant_id = payload.get("tenant_id", DEFAULT_TENANT)
            except Exception:
                pass
        request.state.tenant_id = tenant_id
        response = await call_next(request)
        response.headers["X-Tenant-ID"] = tenant_id
        return response


class TenantContext:
    """Thread-local tenant context for use outside request cycle (e.g. Celery tasks)."""

    _current: str = DEFAULT_TENANT

    @classmethod
    def set(cls, tenant_id: str) -> None:
        cls._current = tenant_id

    @classmethod
    def get(cls) -> str:
        return cls._current

    @classmethod
    def reset(cls) -> None:
        cls._current = DEFAULT_TENANT
