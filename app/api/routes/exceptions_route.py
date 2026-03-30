"""
Exception and Override API Routes
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.exception_framework.domain_types import (
    ExceptionRisk,
    ExceptionType,
)
from app.core.exception_framework.manager import ExceptionError, ExceptionManager

router = APIRouter(prefix="/exceptions", tags=["exceptions"])
_manager = ExceptionManager()


class SubmitExceptionRequest(BaseModel):
    exception_type: ExceptionType
    requested_by: str
    justification: str
    affected_object_ids: list[str]
    affected_action_type: str
    policy_context_id: str
    compensating_controls: list[str] = []
    expires_in_hours: int = 24
    risk_assessment: ExceptionRisk


class DecideExceptionRequest(BaseModel):
    decided_by: str
    rationale: str
    conditions: list[str] = []


@router.post("/submit", summary="Submit a formal exception request")
def submit_exception(req: SubmitExceptionRequest) -> dict:
    from app.core.exception_framework.domain_types import ExceptionRequest

    expires_at = datetime.now(UTC) + timedelta(hours=req.expires_in_hours)
    exception_req = ExceptionRequest(
        exception_type=req.exception_type,
        requested_by=req.requested_by,
        justification=req.justification,
        affected_object_ids=req.affected_object_ids,
        affected_action_type=req.affected_action_type,
        policy_context_id=req.policy_context_id,
        compensating_controls=req.compensating_controls,
        expires_at=expires_at,
        risk_assessment=req.risk_assessment,
    )
    try:
        result = _manager.submit_exception(exception_req)
        return {
            "exception_id": result.exception_id,
            "status": "pending_approval",
            "expires_at": expires_at.isoformat(),
        }
    except ExceptionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{exception_id}/approve", summary="Approve an exception request")
def approve_exception(exception_id: str, req: DecideExceptionRequest) -> dict:
    try:
        decision = _manager.approve_exception(
            exception_id, req.decided_by, req.rationale, req.conditions
        )
        return {
            "exception_id": exception_id,
            "status": "approved",
            "review_task_id": decision.review_task_id,
        }
    except ExceptionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{exception_id}/reject", summary="Reject an exception request")
def reject_exception(exception_id: str, req: DecideExceptionRequest) -> dict:
    try:
        _manager.reject_exception(exception_id, req.decided_by, req.rationale)
        return {"exception_id": exception_id, "status": "rejected"}
    except ExceptionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/active", summary="Get all active exceptions")
def get_active() -> dict:
    active = _manager.get_active_exceptions()
    return {
        "count": len(active),
        "exceptions": [
            {
                "exception_id": e.exception_id,
                "type": e.exception_type.value,
                "risk": e.risk_assessment.value,
                "expires_at": e.expires_at.isoformat(),
                "requested_by": e.requested_by,
            }
            for e in active
        ],
    }


@router.get("/{exception_id}/audit", summary="Get audit trail for an exception")
def get_audit(exception_id: str) -> dict:
    trail = _manager.get_audit_trail(exception_id)
    if not trail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit trail for {exception_id}",
        )
    return {
        "exception_id": exception_id,
        "entries": [
            {
                "event_type": e.event_type,
                "detail": e.event_detail,
                "performed_by": e.performed_by,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in trail
        ],
    }
