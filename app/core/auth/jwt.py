"""
JWT authentication for the Control Fabric Platform API.
Wires into RBAC — token claims map to platform roles.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta
from typing import Any

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production-minimum-32-chars")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    try:
        from jose import jwt
    except ImportError as exc:
        raise ImportError("python-jose required: pip install python-jose[cryptography]") from exc
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.now(UTC)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        from jose import jwt
    except ImportError as exc:
        raise ImportError("python-jose required") from exc
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception as e:
        raise ValueError(f"Invalid token: {e}") from e


def hash_password(password: str) -> str:
    return hashlib.sha256(f"{password}{SECRET_KEY}".encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed
