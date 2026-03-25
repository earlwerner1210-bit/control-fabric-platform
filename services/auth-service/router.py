"""Auth service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.security.auth import get_current_user

from .schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse
from .service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    user = await svc.create_user(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        tenant_id=body.tenant_id,
    )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    user = await svc.authenticate(body.email, body.password)
    tokens = svc.generate_tokens(user)
    return TokenResponse(**tokens)


@router.get("/me", response_model=UserResponse)
async def me(
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    user = await svc.get_user_by_id(ctx.user_id)
    return UserResponse.model_validate(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    tokens = await svc.refresh_tokens(body.refresh_token)
    return TokenResponse(**tokens)
