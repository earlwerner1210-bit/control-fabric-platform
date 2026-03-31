"""Onboarding step endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.products.release_guard.domain.enums import (
    IntegrationProvider,
    OnboardingStep,
    PolicyProfileName,
)
from app.products.release_guard.services.onboarding_service import onboarding_service
from app.products.release_guard.services.workspace_service import workspace_service

router = APIRouter(prefix="/onboarding")


class StartBody(BaseModel):
    workspace_id: str


class ConnectBody(BaseModel):
    workspace_id: str
    config: dict = {}


class LoadDefaultsBody(BaseModel):
    workspace_id: str
    profile: PolicyProfileName = PolicyProfileName.STARTUP_DEFAULT


@router.get("/status/{workspace_id}")
def get_status(workspace_id: str) -> dict:
    return onboarding_service.get_status(workspace_id)


@router.post("/start")
def start_onboarding(body: StartBody) -> dict:
    return onboarding_service.complete_step(body.workspace_id, OnboardingStep.WELCOME)


@router.post("/connect/github")
def connect_github(body: ConnectBody) -> dict:
    from app.products.release_guard.services.integration_service import integration_service

    integration = integration_service.connect(
        body.workspace_id, IntegrationProvider.GITHUB, body.config, "onboarding"
    )
    result = onboarding_service.complete_step(body.workspace_id, OnboardingStep.CONNECT_GITHUB)
    result["integration"] = {"status": integration.status, "provider": "github"}
    return result


@router.post("/connect/jira")
def connect_jira(body: ConnectBody) -> dict:
    from app.products.release_guard.services.integration_service import integration_service

    integration = integration_service.connect(
        body.workspace_id, IntegrationProvider.JIRA, body.config, "onboarding"
    )
    result = onboarding_service.complete_step(body.workspace_id, OnboardingStep.CONNECT_JIRA)
    result["integration"] = {"status": integration.status, "provider": "jira"}
    return result


@router.post("/load-defaults")
def load_defaults(body: LoadDefaultsBody) -> dict:
    workspace_service.set_policy_profile(body.workspace_id, body.profile)
    return onboarding_service.complete_step(body.workspace_id, OnboardingStep.SELECT_PROFILE)


@router.post("/complete/{workspace_id}")
def complete_onboarding(workspace_id: str) -> dict:
    return onboarding_service.complete_step(workspace_id, OnboardingStep.RUN_DEMO)
