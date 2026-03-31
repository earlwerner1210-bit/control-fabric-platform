"""Demo scenario endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.products.release_guard.domain.enums import PolicyProfileName
from app.products.release_guard.services.demo_service import demo_service

router = APIRouter(prefix="/demo")


class SeedBody(BaseModel):
    workspace_id: str
    policy_profile: PolicyProfileName = PolicyProfileName.REGULATED_DEFAULT


@router.post("/seed")
def seed_demo(body: SeedBody) -> dict:
    try:
        return demo_service.seed(body.workspace_id, body.policy_profile)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset/{workspace_id}")
def reset_demo(workspace_id: str) -> dict:
    try:
        return demo_service.reset(workspace_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status/{workspace_id}")
def get_demo_status(workspace_id: str) -> dict:
    return demo_service.get_status(workspace_id)
