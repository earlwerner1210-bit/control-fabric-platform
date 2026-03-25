"""Auth service business logic."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.db.models import User
from shared.security.auth import create_access_token, create_refresh_token, decode_token
from shared.telemetry.logging import get_logger

logger = get_logger("auth_service")


def _hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations=100_000)
    return f"{salt}${h.hex()}"


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a PBKDF2 hash."""
    try:
        salt, h_hex = hashed.split("$", 1)
    except ValueError:
        return False
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations=100_000)
    return hmac.compare_digest(h.hex(), h_hex)


class AuthService:
    """Handles user registration, authentication, and token management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_user(
        self, email: str, password: str, full_name: str, tenant_id: str
    ) -> User:
        """Register a new user."""
        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        user = User(
            email=email,
            hashed_password=_hash_password(password),
            full_name=full_name,
            tenant_id=tenant_id,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()
        logger.info("Created user %s for tenant %s", user.id, tenant_id)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        """Verify credentials and return the user."""
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not _verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
            )
        return user

    def generate_tokens(self, user: User) -> dict[str, str]:
        """Generate access and refresh JWT tokens for a user."""
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "tenant_id": str(user.tenant_id),
        }
        return {
            "access_token": create_access_token(payload),
            "refresh_token": create_refresh_token(payload),
            "token_type": "bearer",
        }

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Decode and return token payload."""
        return decode_token(token)

    async def refresh_tokens(self, refresh_token: str) -> dict[str, str]:
        """Generate new token pair from a valid refresh token."""
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        user_id = payload.get("sub")
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return self.generate_tokens(user)

    async def get_user_by_id(self, user_id: str) -> User:
        """Retrieve a user by their ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user
