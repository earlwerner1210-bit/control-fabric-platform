"""Exception workflow endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.products.release_guard.services.exception_service import exception_service

router = APIRouter(prefix="/exceptions")


class RaiseExceptionBody(BaseModel):
    workspace_id: str
    raised_by: str
    reason: str
    business_justification: str
    approver_email: str
    urgency: str = "high"


class ExceptionDecisionBody(BaseModel):
    decided_by: str
    note: str = ""


@router.post("/releases/{release_id}")
def raise_exception(release_id: str, body: RaiseExceptionBody) -> dict:
    try:
        exc = exception_service.raise_exception(
            release_id=release_id,
            workspace_id=body.workspace_id,
            raised_by=body.raised_by,
            reason=body.reason,
            business_justification=body.business_justification,
            approver_email=body.approver_email,
            urgency=body.urgency,
        )
        return asdict(exc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
def list_exceptions(workspace_id: str, status: str | None = None) -> dict:
    exceptions = exception_service.list_for_workspace(workspace_id, status)
    return {"count": len(exceptions), "exceptions": [asdict(e) for e in exceptions]}


@router.get("/pending")
def get_pending(approver_email: str) -> dict:
    items = exception_service.get_pending_for_approver(approver_email)
    return {"count": len(items), "items": items}


@router.get("/{exception_id}")
def get_exception(exception_id: str) -> dict:
    try:
        return asdict(exception_service.get(exception_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{exception_id}/approve")
def approve_exception(exception_id: str, body: ExceptionDecisionBody) -> dict:
    try:
        exc = exception_service.approve_exception(
            exception_id, body.decided_by, body.note
        )
        return {
            "exception_id": exception_id,
            "status": exc.status,
            "approved": exc.approved,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{exception_id}/reject")
def reject_exception(exception_id: str, body: ExceptionDecisionBody) -> dict:
    try:
        exc = exception_service.reject_exception(
            exception_id, body.decided_by, body.note
        )
        return {
            "exception_id": exception_id,
            "status": exc.status,
            "approved": exc.approved,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
