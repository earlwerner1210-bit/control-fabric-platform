"""JWT authentication, token creation/verification, and FastAPI dependencies."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from shared.config import get_settings
from shared.schemas.common import TenantContext

_bearer_scheme = HTTPBearer()


def create_access_token(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    roles: list[str] | None = None,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Parameters
    ----------
    tenant_id:
        The tenant this token belongs to.
    user_id:
        The authenticated user.
    roles:
        List of role names (e.g. ``["admin", "analyst"]``).
    extra_claims:
        Additional claims to embed in the token payload.
    expires_delta:
        Custom expiry; defaults to ``JWT_EXPIRATION_MINUTES`` from settings.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.JWT_EXPIRATION_MINUTES))

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "roles": roles or [],
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token, returning the claims dict.

    Raises ``HTTPException`` (401) on invalid / expired tokens.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> TenantContext:
    """FastAPI dependency that extracts and validates the JWT bearer token.

    Returns a ``TenantContext`` with tenant_id, user_id, and roles.
    """
    claims = decode_token(credentials.credentials)

    sub = claims.get("sub")
    tenant_id = claims.get("tenant_id")
    if not sub or not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims (sub, tenant_id)",
        )

    return TenantContext(
        tenant_id=uuid.UUID(tenant_id),
        user_id=uuid.UUID(sub),
        roles=claims.get("roles", []),
    )


def require_role(*required_roles: str):
    """Return a FastAPI dependency that enforces role-based access.

    Usage::

        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
        async def admin_only():
            ...
    """

    async def _check_roles(
        ctx: Annotated[TenantContext, Depends(get_current_user)],
    ) -> TenantContext:
        if not any(role in ctx.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of the following roles is required: {', '.join(required_roles)}",
            )
        return ctx

    return _check_roles
