"""FastAPI dependency injection for the API gateway."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.db.base import async_session_factory
from shared.security.auth import decode_token

# ── Database dependency ───────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, committing on success."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Auth dependencies ─────────────────────────────────────────────────────


async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
) -> dict[str, Any]:
    """Extract and validate the bearer token, return decoded payload."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    token = authorization.removeprefix("Bearer ")
    return decode_token(token)


async def get_current_user_optional(
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict[str, Any] | None:
    """Optional auth — returns None when no header is present."""
    if authorization is None:
        return None
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ")
    try:
        return decode_token(token)
    except HTTPException:
        return None


async def get_tenant_context(
    user: dict[str, Any] = Depends(get_current_user),
) -> str:
    """Return the tenant_id from the current JWT payload."""
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing tenant_id in token",
        )
    return tenant_id


# ── Service factory helpers ───────────────────────────────────────────────


class ServiceClients:
    """Lazy-initialised handles to internal service HTTP clients."""

    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def temporal_host(self) -> str:
        return self._settings.TEMPORAL_HOST

    @property
    def temporal_namespace(self) -> str:
        return self._settings.TEMPORAL_NAMESPACE

    @property
    def redis_url(self) -> str:
        return self._settings.REDIS_URL


_service_clients: ServiceClients | None = None


def get_service_clients() -> ServiceClients:
    """Return a singleton ServiceClients instance."""
    global _service_clients
    if _service_clients is None:
        _service_clients = ServiceClients()
    return _service_clients
