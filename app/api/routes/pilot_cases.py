"""Pilot case management API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.pilot_case import (
    CaseStateTransitionRequest,
    CaseStateTransitionResponse,
    CaseTimelineResponse,
    PilotCaseArtifactCreate,
    PilotCaseArtifactResponse,
    PilotCaseAssignRequest,
    PilotCaseAssignResponse,
    PilotCaseCreate,
    PilotCaseListResponse,
    PilotCaseResponse,
    PilotCaseState,
    ValidTransitionsResponse,
)
from app.services.pilot_cases import PilotCaseService
from app.services.state_machine import InvalidTransitionError

router = APIRouter(prefix="/pilot-cases", tags=["pilot-cases"])

_case_service = PilotCaseService()

DEMO_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000099")
DEMO_USER = uuid.UUID("00000000-0000-0000-0000-000000000098")


@router.post("", response_model=PilotCaseResponse, status_code=status.HTTP_201_CREATED)
async def create_pilot_case(data: PilotCaseCreate):
    return _case_service.create_case(DEMO_TENANT, data, DEMO_USER)


@router.get("", response_model=PilotCaseListResponse)
async def list_pilot_cases(
    state: PilotCaseState | None = None,
    workflow_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = _case_service.list_cases(DEMO_TENANT, state, workflow_type, page, page_size)
    return PilotCaseListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{pilot_case_id}", response_model=PilotCaseResponse)
async def get_pilot_case(pilot_case_id: uuid.UUID):
    case = _case_service.get_case(pilot_case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Pilot case not found")
    return case


@router.post("/{pilot_case_id}/artifacts", response_model=PilotCaseArtifactResponse, status_code=status.HTTP_201_CREATED)
async def add_artifact(pilot_case_id: uuid.UUID, data: PilotCaseArtifactCreate):
    try:
        artifact = _case_service.add_artifact(
            pilot_case_id, data.artifact_type, data.artifact_id, data.label, data.metadata
        )
        return PilotCaseArtifactResponse(**artifact)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{pilot_case_id}/assign", response_model=PilotCaseAssignResponse)
async def assign_reviewer(pilot_case_id: uuid.UUID, data: PilotCaseAssignRequest):
    try:
        return _case_service.assign_reviewer(pilot_case_id, data.reviewer_id, DEMO_USER, data.notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{pilot_case_id}/timeline", response_model=CaseTimelineResponse)
async def get_timeline(pilot_case_id: uuid.UUID):
    case = _case_service.get_case(pilot_case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Pilot case not found")
    entries = _case_service.get_timeline(pilot_case_id)
    return CaseTimelineResponse(pilot_case_id=pilot_case_id, entries=entries)


@router.get("/{pilot_case_id}/state", response_model=ValidTransitionsResponse)
async def get_state(pilot_case_id: uuid.UUID):
    case = _case_service.get_case(pilot_case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Pilot case not found")
    from app.services.state_machine import CaseStateMachineService

    sm = CaseStateMachineService()
    valid = sm.get_valid_transitions(case.state)
    return ValidTransitionsResponse(current_state=case.state, valid_transitions=valid)


@router.post("/{pilot_case_id}/state/transition", response_model=CaseStateTransitionResponse)
async def transition_state(pilot_case_id: uuid.UUID, data: CaseStateTransitionRequest):
    try:
        result = _case_service.transition_state(
            pilot_case_id, data.target_state, DEMO_USER, data.reason, data.metadata
        )
        return CaseStateTransitionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))
