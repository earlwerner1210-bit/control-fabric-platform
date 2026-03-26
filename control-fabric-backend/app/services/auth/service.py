"""Authentication service -- JWT creation/verification and password hashing."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stub user store (replaced by real DB lookup in production)
# ---------------------------------------------------------------------------

_DEV_USERS: dict[str, dict[str, Any]] = {
    "admin@controlfabric.dev": {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "admin@controlfabric.dev",
        "full_name": "Dev Admin",
        "role": "admin",
        "tenant_id": "00000000-0000-0000-0000-000000000010",
        "is_active": True,
        # password: "changeme123"
        "hashed_password": "$2b$12$LJ3mFsXqH8kMvG5r2G1oiuKqjZ3X6OdEr2p6T3xJy6VK3Xq7q5IG",
    },
}


class AuthService:
    """Handles authentication, token management, and password hashing."""

    def __init__(self) -> None:
        settings = get_settings()
        self._secret = settings.JWT_SECRET
        self._algorithm = settings.JWT_ALGORITHM
        self._expiration_minutes = settings.JWT_EXPIRATION_MINUTES
        self._pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # ── Password utilities ────────────────────────────────────────────────

    def hash_password(self, password: str) -> str:
        """Return a bcrypt hash of *password*."""
        return self._pwd_ctx.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        """Check *plain* against *hashed*."""
        return self._pwd_ctx.verify(plain, hashed)

    # ── User lookup (stub) ────────────────────────────────────────────────

    def authenticate_user(self, email: str, password: str) -> dict[str, Any] | None:
        """Return the user dict if credentials are valid, otherwise ``None``.

        In production this queries the database; here we check a hardcoded dev
        user so the platform is usable without migrations.
        """
        user = _DEV_USERS.get(email)
        if user is None:
            logger.info("auth.login_failed: unknown email %s", email)
            return None

        if not self.verify_password(password, user["hashed_password"]):
            logger.info("auth.login_failed: bad password for %s", email)
            return None

        if not user.get("is_active", False):
            logger.info("auth.login_failed: inactive user %s", email)
            return None

        logger.info("auth.login_success: %s", email)
        return {k: v for k, v in user.items() if k != "hashed_password"}

    # ── Token management ──────────────────────────────────────────────────

    def create_access_token(
        self,
        user_id: str | UUID,
        tenant_id: str | UUID,
        roles: list[str] | None = None,
    ) -> str:
        """Create a signed JWT containing user identity claims."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self._expiration_minutes)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "roles": roles or [],
            "iat": now,
            "exp": expire,
        }
        token: str = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token

    def verify_token(self, token: str) -> dict[str, Any]:
        """Decode and validate *token*, returning the claims dict.

        Raises ``JWTError`` on invalid / expired tokens.
        """
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
            )
            return claims
        except JWTError:
            logger.warning("auth.token_invalid")
            raise

    def get_current_user(self, token: str) -> dict[str, Any]:
        """Convenience wrapper: verify token and return a user-shaped dict.

        Raises ``JWTError`` if the token is invalid or expired.
        """
        claims = self.verify_token(token)
        return {
            "id": claims["sub"],
            "tenant_id": claims["tenant_id"],
            "roles": claims.get("roles", []),
        }


# Singleton for DI / convenience import
auth_service = AuthService()
