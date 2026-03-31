"""Workspace onboarding — step-by-step activation."""

from __future__ import annotations

from app.products.release_guard.domain.enums import (
    OnboardingStep,
)

STEP_GUIDANCE = {
    OnboardingStep.WELCOME: {
        "title": "Welcome to Release Guard",
        "description": (
            "Stop risky releases before they reach production."
            " Let's set up your workspace in 5 minutes."
        ),
        "action": "Tell us about your team",
        "api": "POST /rg/onboarding/start",
    },
    OnboardingStep.CONNECT_GITHUB: {
        "title": "Connect GitHub",
        "description": (
            "We'll pull CI/CD results and PR details automatically as evidence for your releases."
        ),
        "action": "Connect GitHub account",
        "api": "POST /rg/onboarding/connect/github",
    },
    OnboardingStep.CONNECT_JIRA: {
        "title": "Connect Jira",
        "description": (
            "Attach Jira tickets as change requests. We verify they exist and are approved."
        ),
        "action": "Connect Jira project",
        "api": "POST /rg/onboarding/connect/jira",
    },
    OnboardingStep.SELECT_PROFILE: {
        "title": "Choose your release rules",
        "description": (
            "Pick a preset that matches your team's risk tolerance. You can adjust later."
        ),
        "action": "Select a policy profile",
        "api": "POST /rg/onboarding/load-defaults",
    },
    OnboardingStep.INVITE_APPROVER: {
        "title": "Invite an approver",
        "description": (
            "Choose who approves high-risk releases."
            " They'll get notified when their review is needed."
        ),
        "action": "Invite approver",
        "api": "POST /rg/workspaces/me/invite",
    },
    OnboardingStep.RUN_DEMO: {
        "title": "See it in action",
        "description": ("We'll show you a blocked release and an approved release side by side."),
        "action": "Run demo",
        "api": "POST /rg/demo/seed",
    },
    OnboardingStep.COMPLETE: {
        "title": "You're live",
        "description": "Release Guard is active. Create your first real release request.",
        "action": "Create a release",
        "api": "POST /rg/releases",
    },
}


class OnboardingService:
    def get_status(self, workspace_id: str) -> dict:
        from app.products.release_guard.services.workspace_service import workspace_service

        ws = workspace_service.get(workspace_id)
        if not ws:
            return {"error": "Workspace not found"}
        steps = list(OnboardingStep)
        current_idx = steps.index(ws.onboarding_step)
        completed = steps[:current_idx]
        return {
            "workspace_id": workspace_id,
            "complete": ws.onboarding_complete,
            "current_step": ws.onboarding_step.value,
            "steps_complete": len(completed),
            "total_steps": len(steps) - 1,
            "progress_pct": round(len(completed) / (len(steps) - 1) * 100),
            "guidance": STEP_GUIDANCE.get(ws.onboarding_step, {}),
        }

    def complete_step(
        self,
        workspace_id: str,
        step: OnboardingStep,
        data: dict | None = None,
    ) -> dict:
        from app.products.release_guard.services.workspace_service import workspace_service

        workspace_service.advance_onboarding(workspace_id, step)
        return {
            "step_completed": step.value,
            "next_step": workspace_service.get(workspace_id).onboarding_step.value,
            "progress_pct": self.get_status(workspace_id)["progress_pct"],
            "guidance": STEP_GUIDANCE.get(workspace_service.get(workspace_id).onboarding_step, {}),
        }


onboarding_service = OnboardingService()
