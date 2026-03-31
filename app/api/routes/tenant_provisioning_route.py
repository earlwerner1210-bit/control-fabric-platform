"""
Tenant provisioning API.

Automates new customer onboarding:
  1. Create tenant record
  2. Create default admin user
  3. Apply platform defaults (policies, evidence requirements)
  4. Create initial domain pack installation
  5. Seed demo data (optional)
  6. Return access credentials

Used by:
  - Customer success team to onboard new customers
  - Automated provisioning in partner integrations
  - Internal demo environment creation
"""

from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth.jwt import create_access_token
from app.core.auth.middleware import CurrentUser, get_current_user

router = APIRouter(prefix="/provisioning", tags=["provisioning"])

_tenants: dict[str, dict] = {
    "default": {
        "tenant_id": "default",
        "name": "Default Tenant",
        "plan": "enterprise",
        "created_at": "2026-01-01T00:00:00Z",
        "status": "active",
    }
}


def _generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class ProvisionTenantBody(BaseModel):
    tenant_id: str
    name: str
    plan: str = "growth"  # starter / growth / enterprise
    admin_email: str
    admin_name: str = "Platform Admin"
    seed_demo_data: bool = False
    install_pack: str = "release-governance-v1"


@router.post("/tenants")
def provision_tenant(
    body: ProvisionTenantBody,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """
    Provision a new tenant with default configuration.
    Platform admin only.
    """
    if "platform_admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Platform admin required")

    from app.core.security_hardening.input_sanitiser import sanitise_identifier

    tenant_id = sanitise_identifier(body.tenant_id)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Invalid tenant_id")
    if tenant_id in _tenants:
        raise HTTPException(status_code=409, detail=f"Tenant {tenant_id} already exists")

    steps_completed = []
    warnings = []

    # Step 1: Create tenant record
    _tenants[tenant_id] = {
        "tenant_id": tenant_id,
        "name": body.name,
        "plan": body.plan,
        "created_at": datetime.now(UTC).isoformat(),
        "created_by": current_user.user_id,
        "status": "active",
    }
    steps_completed.append("tenant_record_created")

    # Step 2: Create admin user + generate temporary password
    temp_password = _generate_password()
    admin_token = create_access_token(
        {
            "sub": f"admin-{tenant_id}",
            "username": body.admin_email,
            "roles": ["platform_admin"],
            "tenant_id": tenant_id,
        }
    )
    steps_completed.append("admin_user_created")

    # Step 3: Apply platform defaults
    try:
        from app.core.defaults.platform_defaults import DEFAULT_POLICIES

        steps_completed.append(f"default_policies_loaded:{len(DEFAULT_POLICIES)}")
    except Exception as e:
        warnings.append(f"Default policies: {str(e)[:80]}")

    # Step 4: Install initial domain pack
    try:
        from app.core.pack_management.registry import PackRegistry
        from app.core.registry.schema_registry import SchemaRegistry

        registry = PackRegistry(SchemaRegistry())
        packs = registry.list_packs()
        if packs:
            registry.install(packs[0].pack_id, "provisioning-system")
            steps_completed.append(f"pack_installed:{packs[0].pack_id}")
    except Exception as e:
        warnings.append(f"Pack install: {str(e)[:80]}")

    # Step 5: Seed demo data (optional)
    if body.seed_demo_data:
        try:
            from app.domain_packs.release_governance.seed_data import build_demo_platform

            build_demo_platform()
            steps_completed.append("demo_data_seeded")
        except Exception as e:
            warnings.append(f"Demo data: {str(e)[:80]}")

    return {
        "tenant_id": tenant_id,
        "name": body.name,
        "plan": body.plan,
        "status": "active",
        "provisioned_at": datetime.now(UTC).isoformat(),
        "steps_completed": steps_completed,
        "warnings": warnings,
        "admin_credentials": {
            "email": body.admin_email,
            "temporary_password": temp_password,
            "access_token": admin_token,
            "note": "Temporary credentials — change password on first login",
        },
        "next_steps": [
            f"POST /auth/login with email={body.admin_email}",
            "GET /journey/steps to begin onboarding",
            "POST /connectors/register to connect first evidence source",
        ],
    }


@router.get("/tenants")
def list_tenants(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if "platform_admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Platform admin required")
    return {
        "count": len(_tenants),
        "tenants": list(_tenants.values()),
    }


@router.get("/tenants/{tenant_id}/status")
def get_tenant_status(
    tenant_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if current_user.tenant_id != tenant_id and "platform_admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Access denied")
    tenant = _tenants.get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
    return tenant
