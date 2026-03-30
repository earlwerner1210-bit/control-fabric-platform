"""
FastAPI auth middleware.
Extracts JWT from Authorization header, validates, injects user context.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth.jwt import decode_token

security = HTTPBearer(auto_error=False)


class CurrentUser:
    def __init__(self, user_id: str, username: str, roles: list[str], tenant_id: str) -> None:
        self.user_id = user_id
        self.username = username
        self.roles = roles
        self.tenant_id = tenant_id


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    """Dependency — inject into any route to require authentication."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        return CurrentUser(
            user_id=payload.get("sub", ""),
            username=payload.get("username", ""),
            roles=payload.get("roles", []),
            tenant_id=payload.get("tenant_id", "default"),
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def require_permission(permission: str):
    """Decorator factory — require a specific permission on a route."""

    def dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        from app.core.rbac.domain_types import ROLE_PERMISSIONS, Permission, Role

        user_perms: set[str] = set()
        for role_str in current_user.roles:
            try:
                role = Role(role_str)
                user_perms |= {p.value for p in ROLE_PERMISSIONS.get(role, set())}
            except ValueError:
                pass
        if permission not in user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}",
            )
        return current_user

    return dependency


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser | None:
    """Optional auth — returns None if no token provided."""
    if credentials is None:
        return None
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None
