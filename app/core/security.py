"""JWT authentication and authorization utilities."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings

_settings = get_settings()


class TokenPayload(BaseModel):
    sub: str  # user_id
    tenant_id: str
    roles: list[str] = []
    exp: datetime | None = None


class TenantContext(BaseModel):
    """Request-scoped tenant and user context."""

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    roles: list[str] = []

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles


def create_access_token(
    user_id: str,
    tenant_id: str,
    roles: list[str] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=_settings.JWT_EXPIRATION_MINUTES))
    payload: dict[str, Any] = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": roles or [],
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _settings.JWT_SECRET, algorithm=_settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate a JWT access token."""
    try:
        data = jwt.decode(token, _settings.JWT_SECRET, algorithms=[_settings.JWT_ALGORITHM])
        return TokenPayload(**data)
    except JWTError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc


def build_tenant_context(token_payload: TokenPayload) -> TenantContext:
    """Build a TenantContext from a decoded token."""
    return TenantContext(
        tenant_id=uuid.UUID(token_payload.tenant_id),
        user_id=uuid.UUID(token_payload.sub),
        roles=token_payload.roles,
    )
