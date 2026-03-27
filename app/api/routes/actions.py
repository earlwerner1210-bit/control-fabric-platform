"""API routes for Action Engine — candidate action management and release."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.action_engine import (
    ActionBlockRequest,
    ActionEngineSummary,
    ActionReleaseRequest,
    ActionStatus,
    CandidateActionCreate,
    CandidateActionResponse,
)

router = APIRouter(prefix="/actions", tags=["action-engine"])


@router.post("/candidates", response_model=CandidateActionResponse, status_code=201)
def create_candidate(
    tenant_id: uuid.UUID,
    create: CandidateActionCreate,
) -> CandidateActionResponse:
    from app.services.action_engine import ActionEngineService

    svc = ActionEngineService()
    return svc.create_candidate(tenant_id, create)


@router.get("/candidates/{action_id}", response_model=CandidateActionResponse)
def get_action(action_id: uuid.UUID) -> CandidateActionResponse:
    from app.services.action_engine import ActionEngineService

    svc = ActionEngineService()
    result = svc.get_action(action_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Action not found")
    return result


@router.get(
    "/cases/{pilot_case_id}/actions",
    response_model=list[CandidateActionResponse],
)
def list_case_actions(pilot_case_id: uuid.UUID) -> list[CandidateActionResponse]:
    from app.services.action_engine import ActionEngineService

    svc = ActionEngineService()
    return svc.list_actions(pilot_case_id)


@router.post(
    "/candidates/{action_id}/validate-and-release",
    response_model=CandidateActionResponse,
)
def validate_and_release(
    action_id: uuid.UUID,
    context: dict | None = None,
) -> CandidateActionResponse:
    from app.services.action_engine import ActionEngineService

    svc = ActionEngineService()
    result = svc.validate_and_release(action_id, context)
    if result is None:
        raise HTTPException(status_code=404, detail="Action not found")
    return result


@router.post(
    "/candidates/{action_id}/release",
    response_model=CandidateActionResponse,
)
def release_action(
    action_id: uuid.UUID,
    request: ActionReleaseRequest,
) -> CandidateActionResponse:
    from app.services.action_engine import ActionEngineService

    svc = ActionEngineService()
    result = svc.release(action_id, request)
    if result is None:
        raise HTTPException(status_code=404, detail="Action not found")
    return result


@router.post(
    "/candidates/{action_id}/block",
    response_model=CandidateActionResponse,
)
def block_action(
    action_id: uuid.UUID,
    request: ActionBlockRequest,
) -> CandidateActionResponse:
    from app.services.action_engine import ActionEngineService

    svc = ActionEngineService()
    result = svc.block(action_id, request)
    if result is None:
        raise HTTPException(status_code=404, detail="Action not found")
    return result


@router.post(
    "/candidates/{action_id}/execute",
    response_model=CandidateActionResponse,
)
def mark_executed(action_id: uuid.UUID) -> CandidateActionResponse:
    from app.services.action_engine import ActionEngineService

    svc = ActionEngineService()
    result = svc.mark_executed(action_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Action not found")
    return result


@router.get("/summary", response_model=ActionEngineSummary)
def get_summary(tenant_id: uuid.UUID) -> ActionEngineSummary:
    from app.services.action_engine import ActionEngineService

    svc = ActionEngineService()
    return svc.get_summary(tenant_id)
