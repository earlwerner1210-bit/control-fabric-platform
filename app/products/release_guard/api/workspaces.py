"""Workspace endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.products.release_guard.domain.enums import WorkspacePlan
from app.products.release_guard.services.workspace_service import workspace_service

router = APIRouter(prefix="/workspaces")


class CreateWorkspaceBody(BaseModel):
    name: str
    plan: WorkspacePlan = WorkspacePlan.STARTER


class InviteMemberBody(BaseModel):
    email: str
    role: str = "operator"


@router.post("")
def create_workspace(body: CreateWorkspaceBody) -> dict:
    ws = workspace_service.create(body.name, created_by="api-user", plan=body.plan)
    return asdict(ws)


@router.get("/me")
def get_my_workspace() -> dict:
    workspaces = workspace_service.get_by_tenant("default")
    if not workspaces:
        raise HTTPException(status_code=404, detail="No workspace found")
    return asdict(workspaces[0])


@router.get("/{workspace_id}")
def get_workspace(workspace_id: str) -> dict:
    ws = workspace_service.get(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return asdict(ws)


@router.post("/{workspace_id}/invite")
def invite_member(workspace_id: str, body: InviteMemberBody) -> dict:
    try:
        member = workspace_service.invite_member(workspace_id, body.email, body.role)
        return asdict(member)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{workspace_id}/users")
def get_members(workspace_id: str) -> dict:
    members = workspace_service.get_members(workspace_id)
    return {"count": len(members), "members": [asdict(m) for m in members]}
