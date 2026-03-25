"""Auth routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.security import TenantContext
from app.db.session import get_db
from app.services.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str | None = None
    tenant_id: uuid.UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None = None
    tenant_id: uuid.UUID


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    user, token = await svc.authenticate(body.email, body.password)
    return TokenResponse(access_token=token)


@router.post("/register", response_model=UserResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    user = await svc.register(body.email, body.password, body.full_name, body.tenant_id)
    return UserResponse(id=user.id, email=user.email, full_name=user.full_name, tenant_id=user.tenant_id)


@router.get("/me", response_model=UserResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    svc = AuthService(db)
    user = await svc.get_user(ctx.user_id)
    return UserResponse(id=user.id, email=user.email, full_name=user.full_name, tenant_id=user.tenant_id)
