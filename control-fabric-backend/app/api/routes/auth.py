"""Authentication endpoints -- login and registration."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter

from app.core.exceptions import AuthenticationError
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.auth.service import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    """Authenticate a user and return a signed JWT."""
    user = auth_service.authenticate_user(body.email, body.password)
    if user is None:
        raise AuthenticationError(detail="Invalid email or password")

    token = auth_service.create_access_token(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        roles=[user.get("role", "viewer")],
    )

    from app.core.config import get_settings

    settings = get_settings()
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
    )


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: LoginRequest) -> UserResponse:
    """Register a new user (stub -- returns a placeholder response)."""
    return UserResponse(
        id=UUID("00000000-0000-0000-0000-000000000099"),
        email=body.email,
        full_name="New User",
        role="viewer",
        tenant_id=UUID("00000000-0000-0000-0000-000000000010"),
        is_active=True,
        created_at=datetime.now(UTC),
    )
