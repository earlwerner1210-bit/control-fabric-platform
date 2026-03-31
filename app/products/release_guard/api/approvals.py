"""Approval endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.products.release_guard.services.approval_service import approval_service

router = APIRouter(prefix="/approvals")


class DecisionBody(BaseModel):
    decided_by: str
    note: str = ""


@router.get("/inbox")
def get_inbox(approver_email: str) -> dict:
    items = approval_service.get_pending_inbox(approver_email)
    return {"count": len(items), "items": items}


@router.post("/{step_id}/approve")
def approve(step_id: str, body: DecisionBody) -> dict:
    try:
        step = approval_service.approve(step_id, body.decided_by, body.note)
        return {"step_id": step_id, "status": step.status.value, "decided_by": body.decided_by}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{step_id}/reject")
def reject(step_id: str, body: DecisionBody) -> dict:
    try:
        step = approval_service.reject(step_id, body.decided_by, body.note)
        return {"step_id": step_id, "status": step.status.value, "decided_by": body.decided_by}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/releases/{release_id}")
def get_release_approvals(release_id: str) -> dict:
    steps = approval_service.get_steps_for_release(release_id)
    return {"release_id": release_id, "steps": [asdict(s) for s in steps]}
