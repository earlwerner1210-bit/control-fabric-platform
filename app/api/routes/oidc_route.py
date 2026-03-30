"""OIDC auth flow routes."""

from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.core.auth.jwt import create_access_token
from app.core.auth.oidc import (
    OIDC_ISSUER,
    build_auth_url,
    exchange_code_for_tokens,
    get_userinfo,
    map_oidc_roles,
)

router = APIRouter(prefix="/auth/oidc", tags=["auth"])
_state_store: dict[str, str] = {}


@router.get("/login")
async def oidc_login() -> RedirectResponse:
    if not OIDC_ISSUER:
        raise HTTPException(
            status_code=501,
            detail="OIDC not configured — set OIDC_ISSUER, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET",
        )
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    _state_store[state] = nonce
    return RedirectResponse(url=build_auth_url(state, nonce))


@router.get("/callback")
async def oidc_callback(code: str, state: str) -> dict:
    if state not in _state_store:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    del _state_store[state]
    try:
        tokens = await exchange_code_for_tokens(code)
        userinfo = await get_userinfo(tokens["access_token"])
        roles = map_oidc_roles(userinfo)
        platform_token = create_access_token(
            {
                "sub": userinfo.get("sub", str(uuid.uuid4())),
                "username": userinfo.get("email", userinfo.get("sub", "")),
                "roles": roles,
                "tenant_id": "default",
                "email": userinfo.get("email", ""),
                "oidc_provider": OIDC_ISSUER,
            }
        )
        return {
            "access_token": platform_token,
            "token_type": "bearer",
            "user": {"email": userinfo.get("email"), "roles": roles},
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OIDC callback failed: {e}") from e
