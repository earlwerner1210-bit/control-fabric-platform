"""API routes for RBAC and Governance Permissions."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.rbac import AccessController, AccessDecision, Permission, Role, RoleAssignment

router = APIRouter(prefix="/rbac", tags=["rbac"])

_controller = AccessController()


class AssignRoleRequest(BaseModel):
    principal_id: str
    role: Role
    domain_restriction: str | None = None
    assigned_by: str = "system"


class CheckPermissionRequest(BaseModel):
    principal_id: str
    permission: Permission
    resource: str = ""
    domain: str | None = None


@router.post("/assign", response_model=RoleAssignment)
async def assign_role(req: AssignRoleRequest) -> RoleAssignment:
    """Assign a role to a principal."""
    return _controller.assign_role(
        principal_id=req.principal_id,
        role=req.role,
        domain_restriction=req.domain_restriction,
        assigned_by=req.assigned_by,
    )


@router.post("/revoke")
async def revoke_role(principal_id: str, role: Role) -> dict[str, object]:
    """Revoke a role from a principal."""
    revoked = _controller.revoke_role(principal_id, role)
    return {"principal_id": principal_id, "role": role.value, "revoked": revoked}


@router.get("/roles/{principal_id}", response_model=list[RoleAssignment])
async def get_roles(principal_id: str) -> list[RoleAssignment]:
    """Get all roles for a principal."""
    return _controller.get_roles(principal_id)


@router.post("/check", response_model=AccessDecision)
async def check_permission(req: CheckPermissionRequest) -> AccessDecision:
    """Check if a principal has a specific permission."""
    return _controller.check_permission(
        principal_id=req.principal_id,
        permission=req.permission,
        resource=req.resource,
        domain=req.domain,
    )


@router.get("/matrix")
async def permission_matrix() -> dict[str, list[str]]:
    """Return the full role-permission matrix."""
    return _controller.get_permission_matrix()


@router.get("/audit")
async def audit_log(principal_id: str | None = None) -> list[dict[str, object]]:
    """Return access decision audit log."""
    decisions = _controller.get_audit_log(principal_id)
    return [d.model_dump() for d in decisions]


@router.get("/principals")
async def list_principals() -> list[str]:
    """List all known principals."""
    return _controller.list_principals()
