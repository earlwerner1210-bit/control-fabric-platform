"""Default configuration routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.defaults.platform_defaults import (
    DEFAULT_EVIDENCE_REQUIREMENTS,
    DEFAULT_EXCEPTION_RULES,
    DEFAULT_POLICIES,
    DEFAULT_ROLE_MAPPINGS,
    SEVERITY_THRESHOLDS,
    get_all_defaults,
)

router = APIRouter(prefix="/defaults", tags=["defaults"])


@router.get("/")
def get_defaults() -> dict:
    """Return all platform defaults — apply these on first deployment."""
    return get_all_defaults()


@router.get("/policies")
def get_default_policies() -> dict:
    return {"count": len(DEFAULT_POLICIES), "policies": DEFAULT_POLICIES}


@router.get("/evidence-requirements")
def get_default_evidence() -> dict:
    return {
        "count": len(DEFAULT_EVIDENCE_REQUIREMENTS),
        "requirements": DEFAULT_EVIDENCE_REQUIREMENTS,
    }


@router.get("/role-mappings")
def get_default_roles() -> dict:
    return DEFAULT_ROLE_MAPPINGS


@router.get("/severity-thresholds")
def get_severity_thresholds() -> dict:
    return SEVERITY_THRESHOLDS


@router.get("/exception-rules")
def get_exception_rules() -> dict:
    return DEFAULT_EXCEPTION_RULES


@router.post("/apply")
def apply_defaults(tenant_id: str = "default") -> dict:
    """Apply all platform defaults for a tenant."""
    defaults = get_all_defaults()
    applied = []

    from app.core.policy_admin.manager import PolicyManager

    mgr = PolicyManager()
    for p in defaults["policies"]:
        try:
            mgr.create_draft(
                policy_name=p["name"],
                description=p.get("description", ""),
                rules=p.get("blocked_action_types", []),
                created_by="system",
            )
            applied.append(f"policy:{p['name']}")
        except Exception as e:
            applied.append(f"policy:{p['name']} (skipped: {e})")

    return {
        "tenant_id": tenant_id,
        "applied": applied,
        "total": len(applied),
        "message": "Platform defaults applied successfully",
    }
