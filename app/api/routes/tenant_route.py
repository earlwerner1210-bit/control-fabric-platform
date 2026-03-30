"""Tenant management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth.middleware import CurrentUser, get_current_user

router = APIRouter(prefix="/tenants", tags=["tenants"])

_tenants: dict[str, dict] = {
    "default": {
        "tenant_id": "default",
        "name": "Default Tenant",
        "plan": "enterprise",
        "created_at": "2026-01-01T00:00:00Z",
    },
}


@router.get("/current")
def get_current_tenant(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    return _tenants.get(
        current_user.tenant_id,
        {"tenant_id": current_user.tenant_id, "name": "Unknown tenant"},
    )


@router.get("/")
def list_tenants(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if "platform_admin" not in current_user.roles:
        return {"tenants": [_tenants.get(current_user.tenant_id, {})]}
    return {"tenants": list(_tenants.values())}
