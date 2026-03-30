"""Authentication and authorization schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class LoginRequest(BaseSchema):
    """Credentials submitted by the user to obtain a JWT."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")


class TokenResponse(BaseSchema):
    """JWT token returned after successful authentication."""

    access_token: str = Field(..., description="Signed JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(..., ge=1, description="Token lifetime in seconds")


class UserResponse(BaseSchema):
    """Public-facing representation of a user."""

    id: UUID
    email: str
    full_name: str
    role: str = Field(..., examples=["admin", "analyst", "viewer"])
    tenant_id: UUID
    is_active: bool = True
    created_at: datetime
