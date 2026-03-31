"""Policy profile endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.products.release_guard.domain.enums import PolicyProfileName
from app.products.release_guard.policies.profiles import PROFILES, get_profile
from app.products.release_guard.services.workspace_service import workspace_service

router = APIRouter(prefix="/policies")


class SelectProfileBody(BaseModel):
    workspace_id: str
    profile: PolicyProfileName


class UpdateTogglesBody(BaseModel):
    workspace_id: str
    toggles: dict


@router.get("/profiles")
def list_profiles() -> dict:
    return {
        "profiles": [
            {
                "name": name.value,
                "display_name": profile["name"],
                "description": profile["description"],
                "required_evidence": profile["required_evidence"],
                "toggles": profile["toggles"],
            }
            for name, profile in PROFILES.items()
        ]
    }


@router.get("/profile/{workspace_id}")
def get_workspace_profile(workspace_id: str) -> dict:
    ws = workspace_service.get(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    profile = get_profile(ws.policy_profile)
    return {
        "workspace_id": workspace_id,
        "profile_name": ws.policy_profile.value,
        "display_name": profile["name"],
        "description": profile["description"],
        "required_evidence": profile["required_evidence"],
        "toggles": profile["toggles"],
    }


@router.post("/profile/select")
def select_profile(body: SelectProfileBody) -> dict:
    try:
        ws = workspace_service.set_policy_profile(body.workspace_id, body.profile)
        return {
            "workspace_id": body.workspace_id,
            "profile_name": ws.policy_profile.value,
            "applied": True,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
