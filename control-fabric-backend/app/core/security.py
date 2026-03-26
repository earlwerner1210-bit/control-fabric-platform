"""Authentication and authorisation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Immutable context propagated through every request."""

    tenant_id: str
    user_id: str
    roles: list[str] = field(default_factory=list)


# ── JWT helpers ──────────────────────────────────────────────────────────────


def create_access_token(
    user_id: str,
    tenant_id: str,
    roles: list[str] | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": roles or [],
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, returning its payload dict.

    Raises ``AuthenticationError`` on any validation failure.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise AuthenticationError(detail=f"Invalid token: {exc}") from exc

    if "sub" not in payload or "tenant_id" not in payload:
        raise AuthenticationError(detail="Token missing required claims")

    return payload


def build_tenant_context(payload: dict[str, Any]) -> TenantContext:
    """Build a ``TenantContext`` from a decoded JWT payload."""
    return TenantContext(
        tenant_id=payload["tenant_id"],
        user_id=payload["sub"],
        roles=payload.get("roles", []),
    )


# ── Password helpers ─────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against its bcrypt hash."""
    return _pwd_ctx.verify(plain, hashed)
