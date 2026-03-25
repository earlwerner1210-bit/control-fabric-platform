"""Authentication dependencies for FastAPI."""

from __future__ import annotations

import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TenantContext, decode_access_token, build_tenant_context
from app.db.session import get_db


async def get_current_user(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """Extract and validate user from Authorization header."""
    if not authorization:
        # Dev fallback: return default tenant context
        return TenantContext(
            tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            roles=["admin"],
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth header")

    try:
        payload = decode_access_token(token)
        return build_tenant_context(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


def require_role(*roles: str):
    """Dependency factory that checks for required roles."""
    async def _check(ctx: TenantContext = Depends(get_current_user)) -> TenantContext:
        if not any(r in ctx.roles for r in roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return ctx
    return _check
