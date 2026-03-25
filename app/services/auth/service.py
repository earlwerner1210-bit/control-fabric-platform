"""Authentication service."""

from __future__ import annotations

import uuid
from datetime import timedelta

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.security import TenantContext, create_access_token
from app.db.models import User, Tenant

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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
            hashed_password=_pwd_ctx.hash(password),
            full_name=full_name,
            tenant_id=tenant_id,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def authenticate(self, email: str, password: str) -> tuple[User, str]:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not _pwd_ctx.verify(password, user.hashed_password):
            raise AuthenticationError("Invalid credentials")
        if not user.is_active:
            raise AuthenticationError("Account disabled")

        token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            roles=[r.name for r in user.roles] if user.roles else [],
        )
        return user, token

    async def get_user(self, user_id: uuid.UUID) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        return user
