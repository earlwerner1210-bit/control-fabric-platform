"""Domain types for RBAC and Governance Permissions."""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Role(str, enum.Enum):
    PLATFORM_ADMIN = "platform_admin"
    DOMAIN_OWNER = "domain_owner"
    POLICY_AUTHOR = "policy_author"
    OPERATOR = "operator"
    AUDITOR = "auditor"
    VIEWER = "viewer"
    SERVICE_ACCOUNT = "service_account"


class Permission(str, enum.Enum):
    # Object operations
    OBJECT_READ = "object:read"
    OBJECT_WRITE = "object:write"
    OBJECT_DELETE = "object:delete"
    # Graph operations
    GRAPH_READ = "graph:read"
    GRAPH_WRITE = "graph:write"
    # Case operations
    CASE_READ = "case:read"
    CASE_WRITE = "case:write"
    CASE_CLOSE = "case:close"
    # Rule operations
    RULE_READ = "rule:read"
    RULE_WRITE = "rule:write"
    RULE_ACTIVATE = "rule:activate"
    # Policy operations
    POLICY_READ = "policy:read"
    POLICY_WRITE = "policy:write"
    POLICY_PUBLISH = "policy:publish"
    POLICY_ROLLBACK = "policy:rollback"
    # Pack operations
    PACK_READ = "pack:read"
    PACK_INSTALL = "pack:install"
    PACK_UNINSTALL = "pack:uninstall"
    # Exception operations
    EXCEPTION_READ = "exception:read"
    EXCEPTION_REQUEST = "exception:request"
    EXCEPTION_APPROVE = "exception:approve"
    # Release operations
    RELEASE_READ = "release:read"
    RELEASE_APPROVE = "release:approve"
    # Admin operations
    ADMIN_USERS = "admin:users"
    ADMIN_AUDIT = "admin:audit"


# ── role → permissions mapping ──────────────────────────

ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.PLATFORM_ADMIN: set(Permission),
    Role.DOMAIN_OWNER: {
        Permission.OBJECT_READ,
        Permission.OBJECT_WRITE,
        Permission.GRAPH_READ,
        Permission.GRAPH_WRITE,
        Permission.CASE_READ,
        Permission.CASE_WRITE,
        Permission.CASE_CLOSE,
        Permission.RULE_READ,
        Permission.RULE_WRITE,
        Permission.RULE_ACTIVATE,
        Permission.POLICY_READ,
        Permission.POLICY_WRITE,
        Permission.PACK_READ,
        Permission.PACK_INSTALL,
        Permission.EXCEPTION_READ,
        Permission.EXCEPTION_REQUEST,
        Permission.RELEASE_READ,
    },
    Role.POLICY_AUTHOR: {
        Permission.POLICY_READ,
        Permission.POLICY_WRITE,
        Permission.RULE_READ,
        Permission.RULE_WRITE,
        Permission.PACK_READ,
        Permission.CASE_READ,
    },
    Role.OPERATOR: {
        Permission.OBJECT_READ,
        Permission.GRAPH_READ,
        Permission.CASE_READ,
        Permission.CASE_WRITE,
        Permission.CASE_CLOSE,
        Permission.RULE_READ,
        Permission.POLICY_READ,
        Permission.PACK_READ,
        Permission.EXCEPTION_READ,
        Permission.EXCEPTION_REQUEST,
        Permission.RELEASE_READ,
    },
    Role.AUDITOR: {
        Permission.OBJECT_READ,
        Permission.GRAPH_READ,
        Permission.CASE_READ,
        Permission.RULE_READ,
        Permission.POLICY_READ,
        Permission.PACK_READ,
        Permission.EXCEPTION_READ,
        Permission.RELEASE_READ,
        Permission.ADMIN_AUDIT,
    },
    Role.VIEWER: {
        Permission.OBJECT_READ,
        Permission.GRAPH_READ,
        Permission.CASE_READ,
        Permission.RULE_READ,
        Permission.POLICY_READ,
        Permission.PACK_READ,
        Permission.RELEASE_READ,
    },
    Role.SERVICE_ACCOUNT: {
        Permission.OBJECT_READ,
        Permission.OBJECT_WRITE,
        Permission.GRAPH_READ,
        Permission.GRAPH_WRITE,
        Permission.CASE_READ,
        Permission.CASE_WRITE,
        Permission.RULE_READ,
        Permission.RELEASE_READ,
    },
}


class RoleAssignment(BaseModel, frozen=True):
    """Immutable assignment of a role to a principal."""

    principal_id: str
    role: Role
    domain_restriction: str | None = None
    assigned_by: str = "system"
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AccessDecision(BaseModel, frozen=True):
    """Immutable audit record of an access decision."""

    principal_id: str
    permission: Permission
    granted: bool
    role: Role
    domain_restriction: str | None = None
    resource: str = ""
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
