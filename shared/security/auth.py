"""Authentication / authorisation FastAPI dependencies."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status

from shared.config import get_settings


def create_access_token(data: dict[str, Any], expires_minutes: int | None = None) -> str:
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.JWT_EXPIRATION_MINUTES)
    to_encode = {**data, "exp": expire}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode = {**data, "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_user(authorization: str = Header(..., alias="Authorization")) -> dict[str, Any]:
    """Extract and validate the bearer token, return decoded payload."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    token = authorization.removeprefix("Bearer ")
    return decode_token(token)


async def get_current_tenant(user: dict[str, Any] = Depends(get_current_user)) -> str:
    """Return the tenant_id from the current JWT payload."""
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing tenant_id in token")
    return tenant_id
