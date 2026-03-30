"""Auth routes — login, token refresh, registration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.auth.jwt import create_access_token, hash_password, verify_password
from app.core.auth.middleware import CurrentUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

_users: dict[str, dict] = {
    "admin": {
        "user_id": "admin-001",
        "username": "admin",
        "hashed_password": hash_password("admin"),
        "roles": ["platform_admin"],
        "tenant_id": "default",
    },
    "operator": {
        "user_id": "op-001",
        "username": "operator",
        "hashed_password": hash_password("operator"),
        "roles": ["operator"],
        "tenant_id": "default",
    },
}


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: str = "default"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 480 * 60
    user_id: str
    roles: list[str]


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest) -> TokenResponse:
    user = _users.get(req.username)
    if not user or not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(
        {
            "sub": user["user_id"],
            "username": user["username"],
            "roles": user["roles"],
            "tenant_id": req.tenant_id,
        }
    )
    return TokenResponse(access_token=token, user_id=user["user_id"], roles=user["roles"])


@router.get("/me")
def get_me(current_user: CurrentUser = Depends(get_current_user)) -> dict:
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "roles": current_user.roles,
        "tenant_id": current_user.tenant_id,
    }


@router.post("/register")
def register(req: LoginRequest) -> dict:
    if req.username in _users:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    user_id = f"user-{len(_users):04d}"
    _users[req.username] = {
        "user_id": user_id,
        "username": req.username,
        "hashed_password": hash_password(req.password),
        "roles": ["operator"],
        "tenant_id": req.tenant_id,
    }
    return {"user_id": user_id, "username": req.username, "roles": ["operator"]}
