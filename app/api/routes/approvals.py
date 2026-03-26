"""Approval, override, and escalation API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.schemas.approval import (
    ApprovalRequest,
    ApprovalResponse,
    EscalationRequest,
    EscalationResponse,
    OverrideRequest,
    OverrideResponse,
)
from app.services.approval import ApprovalService
from app.services.pilot_cases import PilotCaseService
from app.services.state_machine import InvalidTransitionError

router = APIRouter(prefix="/pilot-cases", tags=["approvals"])

_case_service = PilotCaseService()
_approval_service = ApprovalService(_case_service)

DEMO_USER = uuid.UUID("00000000-0000-0000-0000-000000000098")


@router.post("/{pilot_case_id}/approve", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
async def approve_case(pilot_case_id: uuid.UUID, data: ApprovalRequest):
    try:
        return _approval_service.approve(pilot_case_id, DEMO_USER, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/{pilot_case_id}/override", response_model=OverrideResponse, status_code=status.HTTP_201_CREATED)
async def override_case(pilot_case_id: uuid.UUID, data: OverrideRequest):
    try:
        return _approval_service.override(pilot_case_id, DEMO_USER, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/{pilot_case_id}/escalate", response_model=EscalationResponse, status_code=status.HTTP_201_CREATED)
async def escalate_case(pilot_case_id: uuid.UUID, data: EscalationRequest):
    try:
        return _approval_service.escalate(pilot_case_id, DEMO_USER, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))
