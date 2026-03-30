"""Tenant context middleware — injects tenant_id into request state."""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("middleware.tenant")


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Extract tenant from JWT claims or header and bind to request state.

    This middleware runs after auth and ensures all downstream handlers
    can access ``request.state.tenant_id`` for row-level filtering.
    """

    DEFAULT_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")

    EXEMPT_PATHS = {"/health", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.EXEMPT_PATHS:
            request.state.tenant_id = self.DEFAULT_TENANT
            return await call_next(request)

        # Try to extract from header (set by auth middleware or API gateway)
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            try:
                request.state.tenant_id = uuid.UUID(tenant_header)
            except ValueError:
                request.state.tenant_id = self.DEFAULT_TENANT
        else:
            request.state.tenant_id = self.DEFAULT_TENANT

        structlog.contextvars.bind_contextvars(tenant_id=str(request.state.tenant_id))

        response = await call_next(request)
        return response
