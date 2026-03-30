"""RBAC Access Controller — role-based access with domain restrictions."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from .domain_types import (
    ROLE_PERMISSIONS,
    AccessDecision,
    Permission,
    Role,
    RoleAssignment,
)

logger = logging.getLogger(__name__)


class AccessController:
    """Manages role assignments and access decisions."""

    def __init__(self) -> None:
        self._assignments: dict[str, list[RoleAssignment]] = {}
        self._audit_log: list[AccessDecision] = []

    # ── role management ─────────────────────────────────────

    def assign_role(
        self,
        principal_id: str,
        role: Role,
        domain_restriction: str | None = None,
        assigned_by: str = "system",
    ) -> RoleAssignment:
        assignment = RoleAssignment(
            principal_id=principal_id,
            role=role,
            domain_restriction=domain_restriction,
            assigned_by=assigned_by,
        )
        self._assignments.setdefault(principal_id, []).append(assignment)
        logger.info("Assigned role %s to %s", role.value, principal_id)
        return assignment

    def revoke_role(self, principal_id: str, role: Role) -> bool:
        assignments = self._assignments.get(principal_id, [])
        before = len(assignments)
        self._assignments[principal_id] = [a for a in assignments if a.role != role]
        revoked = len(self._assignments[principal_id]) < before
        if revoked:
            logger.info("Revoked role %s from %s", role.value, principal_id)
        return revoked

    def get_roles(self, principal_id: str) -> list[RoleAssignment]:
        return self._assignments.get(principal_id, [])

    # ── access decisions ────────────────────────────────────

    def check_permission(
        self,
        principal_id: str,
        permission: Permission,
        resource: str = "",
        domain: str | None = None,
    ) -> AccessDecision:
        assignments = self._assignments.get(principal_id, [])

        for assignment in assignments:
            role_perms = ROLE_PERMISSIONS.get(assignment.role, set())
            if permission not in role_perms:
                continue
            if assignment.domain_restriction and domain:
                if assignment.domain_restriction != domain:
                    continue
            decision = AccessDecision(
                principal_id=principal_id,
                permission=permission,
                granted=True,
                role=assignment.role,
                domain_restriction=assignment.domain_restriction,
                resource=resource,
            )
            self._audit_log.append(decision)
            return decision

        # Denied
        decision = AccessDecision(
            principal_id=principal_id,
            permission=permission,
            granted=False,
            role=assignments[0].role if assignments else Role.VIEWER,
            resource=resource,
        )
        self._audit_log.append(decision)
        return decision

    def check_any_permission(
        self,
        principal_id: str,
        permissions: list[Permission],
        resource: str = "",
        domain: str | None = None,
    ) -> AccessDecision:
        for perm in permissions:
            decision = self.check_permission(principal_id, perm, resource, domain)
            if decision.granted:
                return decision
        return AccessDecision(
            principal_id=principal_id,
            permission=permissions[0] if permissions else Permission.OBJECT_READ,
            granted=False,
            role=Role.VIEWER,
            resource=resource,
        )

    # ── queries ─────────────────────────────────────────────

    def get_permission_matrix(self) -> dict[str, list[str]]:
        return {role.value: [p.value for p in perms] for role, perms in ROLE_PERMISSIONS.items()}

    def get_audit_log(self, principal_id: str | None = None) -> list[AccessDecision]:
        if principal_id:
            return [d for d in self._audit_log if d.principal_id == principal_id]
        return list(self._audit_log)

    def list_principals(self) -> list[str]:
        return list(self._assignments.keys())
