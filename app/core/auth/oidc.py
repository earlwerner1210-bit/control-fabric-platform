"""
OIDC integration — supports Auth0, Okta, Azure AD, Google Workspace.
On successful OIDC login, maps external identity to platform roles.
"""

from __future__ import annotations

import os

import httpx

OIDC_ISSUER = os.getenv("OIDC_ISSUER", "")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
OIDC_REDIRECT_URI = os.getenv("OIDC_REDIRECT_URI", "http://localhost:8000/auth/oidc/callback")

DEFAULT_ROLE_MAPPING: dict[str, str] = {
    "admin": "platform_admin",
    "platform-admin": "platform_admin",
    "operator": "operator",
    "reviewer": "reviewer",
    "approver": "approver",
    "auditor": "auditor",
    "policy-admin": "policy_admin",
}


async def get_oidc_config() -> dict:
    """Fetch OIDC discovery document."""
    if not OIDC_ISSUER:
        raise ValueError("OIDC_ISSUER not configured")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{OIDC_ISSUER}/.well-known/openid-configuration")
        resp.raise_for_status()
        return resp.json()


def build_auth_url(state: str, nonce: str) -> str:
    """Build the OIDC authorization URL for redirect."""
    params = "&".join(
        [
            "response_type=code",
            f"client_id={OIDC_CLIENT_ID}",
            f"redirect_uri={OIDC_REDIRECT_URI}",
            "scope=openid+email+profile",
            f"state={state}",
            f"nonce={nonce}",
        ]
    )
    issuer = OIDC_ISSUER.rstrip("/")
    return f"{issuer}/authorize?{params}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for tokens."""
    config = await get_oidc_config()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            config["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": OIDC_REDIRECT_URI,
                "client_id": OIDC_CLIENT_ID,
                "client_secret": OIDC_CLIENT_SECRET,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_userinfo(access_token: str) -> dict:
    """Fetch user info from OIDC provider."""
    config = await get_oidc_config()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            config["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


def map_oidc_roles(userinfo: dict, custom_mapping: dict | None = None) -> list[str]:
    """Map OIDC groups/roles to platform roles."""
    mapping = {**DEFAULT_ROLE_MAPPING, **(custom_mapping or {})}
    oidc_groups: list[str] = (
        userinfo.get("groups", [])
        + userinfo.get("roles", [])
        + userinfo.get(f"{OIDC_ISSUER}roles", [])
    )
    platform_roles = [mapping[g] for g in oidc_groups if g in mapping]
    return platform_roles or ["operator"]
