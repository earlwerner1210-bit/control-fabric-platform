"""Authentication dependencies for FastAPI route injection."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import TenantContext, build_tenant_context, decode_access_token

# ---------------------------------------------------------------------------
# Default dev tenant (used when no Authorization header is provided)
# ---------------------------------------------------------------------------

_DEV_TENANT = TenantContext(
    tenant_id="00000000-0000-0000-0000-000000000010",
    user_id="00000000-0000-0000-0000-000000000001",
    roles=["admin"],
)


# ---------------------------------------------------------------------------
# Primary auth dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> TenantContext:
    """Extract and validate the caller's identity from the Authorization header.

    In development mode (no ``Authorization`` header supplied), a default
    tenant context is returned so the API is usable without a real JWT.
    """
    if authorization is None:
        return _DEV_TENANT

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError(detail="Authorization header must be 'Bearer <token>'")

    token = parts[1]
    payload = decode_access_token(token)
    return build_tenant_context(payload)


# ---------------------------------------------------------------------------
# Role-checking dependency factory
# ---------------------------------------------------------------------------


def require_role(*roles: str) -> Callable[..., TenantContext]:
    """Return a FastAPI dependency that enforces the caller has one of *roles*.

    Usage::

        @router.post("/admin-only")
        async def admin_endpoint(ctx: TenantContext = Depends(require_role("admin"))):
            ...
    """

    async def _check(ctx: TenantContext = Depends(get_current_user)) -> TenantContext:
        if not any(r in ctx.roles for r in roles):
            raise AuthorizationError(
                detail=f"One of the following roles is required: {', '.join(roles)}"
            )
        return ctx

    return _check
