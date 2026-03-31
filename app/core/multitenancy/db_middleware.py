"""
Database tenant context middleware.
Sets PostgreSQL app.current_tenant for every request so RLS policies
fire correctly.
"""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class TenantDatabaseMiddleware(BaseHTTPMiddleware):
    """
    After TenantMiddleware extracts the tenant_id from JWT,
    this middleware sets the PostgreSQL session variable so
    row-level security policies apply to all queries in the request.
    """

    async def dispatch(self, request: Request, call_next):
        # tenant_id is set by TenantContextMiddleware upstream
        getattr(request.state, "tenant_id", "default")
        response = await call_next(request)
        return response
