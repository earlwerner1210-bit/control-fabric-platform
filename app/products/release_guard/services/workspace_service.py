"""Workspace service — create and manage Release Guard workspaces."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from app.products.release_guard.domain.enums import (
    OnboardingStep,
    PolicyProfileName,
    WorkspacePlan,
)
from app.products.release_guard.domain.models import Workspace, WorkspaceMember

logger = logging.getLogger(__name__)

_workspaces: dict[str, Workspace] = {}
_members: dict[str, list[WorkspaceMember]] = {}


class WorkspaceService:
    def create(
        self,
        name: str,
        created_by: str,
        plan: WorkspacePlan = WorkspacePlan.STARTER,
        tenant_id: str = "default",
    ) -> Workspace:
        slug = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
        workspace = Workspace(
            name=name,
            slug=slug,
            plan=plan,
            tenant_id=tenant_id,
            created_by=created_by,
        )
        _workspaces[workspace.workspace_id] = workspace
        # Add creator as admin
        member = WorkspaceMember(
            workspace_id=workspace.workspace_id,
            user_id=created_by,
            email=created_by,
            name=created_by,
            role="admin",
        )
        member.accepted_at = datetime.now(UTC).isoformat()
        _members.setdefault(workspace.workspace_id, []).append(member)
        logger.info("Workspace created: %s (%s)", workspace.workspace_id[:8], name)
        return workspace

    def get(self, workspace_id: str) -> Workspace | None:
        return _workspaces.get(workspace_id)

    def get_by_tenant(self, tenant_id: str) -> list[Workspace]:
        return [w for w in _workspaces.values() if w.tenant_id == tenant_id]

    def update_plan(self, workspace_id: str, plan: WorkspacePlan) -> Workspace:
        ws = self._get(workspace_id)
        ws.plan = plan
        return ws

    def set_policy_profile(
        self,
        workspace_id: str,
        profile: PolicyProfileName,
    ) -> Workspace:
        ws = self._get(workspace_id)
        ws.policy_profile = profile
        return ws

    def invite_member(
        self,
        workspace_id: str,
        email: str,
        role: str = "operator",
        invited_by: str = "",
    ) -> WorkspaceMember:
        self._get(workspace_id)
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=email,
            email=email,
            name=email.split("@")[0],
            role=role,
        )
        _members.setdefault(workspace_id, []).append(member)
        ws = _workspaces[workspace_id]
        ws.member_count = len(_members[workspace_id])
        logger.info("Member invited: %s to %s as %s", email, workspace_id[:8], role)
        return member

    def get_members(self, workspace_id: str) -> list[WorkspaceMember]:
        return _members.get(workspace_id, [])

    def advance_onboarding(
        self,
        workspace_id: str,
        step: OnboardingStep,
    ) -> Workspace:
        ws = self._get(workspace_id)
        steps = list(OnboardingStep)
        current_idx = steps.index(step)
        if current_idx + 1 < len(steps):
            ws.onboarding_step = steps[current_idx + 1]
        else:
            ws.onboarding_complete = True
            ws.onboarding_step = OnboardingStep.COMPLETE
        return ws

    def _get(self, workspace_id: str) -> Workspace:
        ws = _workspaces.get(workspace_id)
        if not ws:
            raise ValueError(f"Workspace {workspace_id} not found")
        return ws


workspace_service = WorkspaceService()
