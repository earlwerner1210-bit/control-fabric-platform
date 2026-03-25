"""Auth routes — login, register, current user."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user, get_db
from shared.security.auth import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request / Response schemas ────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    tenant_id: str = "default"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    tenant_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate a user and return a JWT access token."""
    # Look up user by email — using raw SQL for simplicity until ORM models exist
    result = await db.execute(
        text("SELECT id, email, full_name, role, tenant_id, password_hash FROM users WHERE email = :email"),
        {"email": body.email},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Verify password (passlib bcrypt)
    from passlib.hash import bcrypt

    if not bcrypt.verify(body.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(
        {
            "sub": row["id"],
            "email": row["email"],
            "role": row["role"],
            "tenant_id": row["tenant_id"],
        }
    )
    return TokenResponse(access_token=token)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> UserResponse:
    """Register a new user."""
    import uuid

    from passlib.hash import bcrypt

    # Check for existing user
    existing = await db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": body.email},
    )
    if existing.first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user_id = str(uuid.uuid4())
    password_hash = bcrypt.hash(body.password)

    await db.execute(
        text(
            "INSERT INTO users (id, email, full_name, role, tenant_id, password_hash, is_active) "
            "VALUES (:id, :email, :full_name, :role, :tenant_id, :password_hash, true)"
        ),
        {
            "id": user_id,
            "email": body.email,
            "full_name": body.full_name,
            "role": "user",
            "tenant_id": body.tenant_id,
            "password_hash": password_hash,
        },
    )
    return UserResponse(
        id=user_id,
        email=body.email,
        full_name=body.full_name,
        role="user",
        tenant_id=body.tenant_id,
    )


@router.get("/me", response_model=UserResponse)
async def me(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Return the currently authenticated user."""
    result = await db.execute(
        text("SELECT id, email, full_name, role, tenant_id FROM users WHERE id = :id"),
        {"id": user["sub"]},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(**dict(row))
