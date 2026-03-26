"""Authentication service."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from app.core.security import TokenPayload
from app.db.models import User

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Full-featured authentication and authorization service.

    Provides user authentication, JWT token management, password hashing,
    token verification, and role-based access control.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._settings = get_settings()

    # ── Registration ──────────────────────────────────────────────

    async def register(
        self,
        email: str,
        password: str,
        full_name: str | None,
        tenant_id: uuid.UUID,
    ) -> User:
        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ConflictError(f"User with email {email} already exists")

        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=self.hash_password(password),
            full_name=full_name,
            tenant_id=tenant_id,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    # ── Authentication ────────────────────────────────────────────

    async def authenticate(self, email: str, password: str) -> tuple[User, str]:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not self.verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid credentials")
        if not user.is_active:
            raise AuthenticationError("Account disabled")

        token = self.create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            roles=[r.name for r in user.roles] if user.roles else [],
        )
        return user, token

    async def authenticate_user(self, email: str, password: str) -> User | None:
        """Authenticate by email/password and return the User, or None on failure.

        Unlike ``authenticate``, this does not raise on bad credentials and does
        not mint a token — useful when you need to verify identity without
        immediately issuing a session.
        """
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    # ── Token management ──────────────────────────────────────────

    def create_access_token(
        self,
        user_id: str,
        tenant_id: str,
        roles: list[str] | None = None,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a signed JWT access token.

        Token payload contains: sub (user_id), tenant_id, roles, exp, iat, jti.
        Default expiry is read from ``JWT_EXPIRATION_MINUTES`` (default 60 min).
        """
        now = datetime.now(UTC)
        expire = now + (expires_delta or timedelta(minutes=self._settings.JWT_EXPIRATION_MINUTES))
        payload: dict[str, Any] = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "roles": roles or [],
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(
            payload,
            self._settings.JWT_SECRET,
            algorithm=self._settings.JWT_ALGORITHM,
        )

    def verify_token(self, token: str) -> TokenPayload:
        """Decode and validate a JWT, returning the structured payload.

        Raises ``AuthenticationError`` if the token is expired, malformed, or
        has an invalid signature.
        """
        try:
            data = jwt.decode(
                token,
                self._settings.JWT_SECRET,
                algorithms=[self._settings.JWT_ALGORITHM],
            )
            return TokenPayload(**data)
        except JWTError as exc:
            raise AuthenticationError(f"Invalid or expired token: {exc}") from exc

    # ── Password utilities ────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """Return a bcrypt hash of *password*."""
        return _pwd_ctx.hash(password)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        """Verify *plain* against a bcrypt *hashed* value."""
        return _pwd_ctx.verify(plain, hashed)

    # ── User lookup ───────────────────────────────────────────────

    async def get_user(self, user_id: uuid.UUID) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        return user

    async def get_current_user(self, token: str) -> dict[str, Any]:
        """Decode *token* and return the corresponding user as a dict.

        The returned dict contains ``id``, ``email``, ``full_name``,
        ``tenant_id``, ``roles``, and ``is_active``.

        Raises ``AuthenticationError`` on invalid token or missing user.
        """
        payload = self.verify_token(token)
        try:
            user = await self.get_user(uuid.UUID(payload.sub))
        except NotFoundError:
            raise AuthenticationError("User from token no longer exists")
        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "tenant_id": str(user.tenant_id),
            "roles": [r.name for r in user.roles] if user.roles else [],
            "is_active": user.is_active,
        }

    # ── Role-based access control ─────────────────────────────────

    def require_role(self, required_role: str) -> Callable[[str], Any]:
        """Return a dependency callable that enforces *required_role*.

        Usage as a FastAPI dependency::

            auth = AuthService(db)

            @router.get("/admin")
            async def admin_only(
                _: None = Depends(auth.require_role("admin")),
            ):
                ...

        The callable accepts a *token* string, verifies it, and raises
        ``AuthorizationError`` if the token's roles do not include
        *required_role*.
        """

        async def _check(token: str) -> TokenPayload:
            payload = self.verify_token(token)
            if required_role not in payload.roles:
                raise AuthorizationError(f"Role '{required_role}' is required for this operation")
            return payload

        return _check
