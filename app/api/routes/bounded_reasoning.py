"""API routes for Bounded Reasoning — graph-slice-isolated inference."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.bounded_reasoning import (
    BoundedReasoningRequest,
    BoundedReasoningResponse,
    ReasoningSummary,
)

router = APIRouter(prefix="/bounded-reasoning", tags=["bounded-reasoning"])


@router.post("/reason", response_model=BoundedReasoningResponse, status_code=201)
def reason(
    tenant_id: uuid.UUID,
    request: BoundedReasoningRequest,
) -> BoundedReasoningResponse:
    from app.services.bounded_reasoning import BoundedReasoningService
    from app.services.control_fabric import ControlFabricService
    from app.services.control_graph import ControlGraphService

    fabric_svc = ControlFabricService()
    graph_svc = ControlGraphService(fabric_svc)
    reasoning_svc = BoundedReasoningService(graph_svc)
    return reasoning_svc.reason(tenant_id, request)


@router.get("/sessions/{session_id}", response_model=BoundedReasoningResponse)
def get_session(session_id: uuid.UUID) -> BoundedReasoningResponse:
    from app.services.bounded_reasoning import BoundedReasoningService
    from app.services.control_fabric import ControlFabricService
    from app.services.control_graph import ControlGraphService

    fabric_svc = ControlFabricService()
    graph_svc = ControlGraphService(fabric_svc)
    reasoning_svc = BoundedReasoningService(graph_svc)
    result = reasoning_svc.get_session(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.get("/summary", response_model=ReasoningSummary)
def get_summary(tenant_id: uuid.UUID) -> ReasoningSummary:
    from app.services.bounded_reasoning import BoundedReasoningService
    from app.services.control_fabric import ControlFabricService
    from app.services.control_graph import ControlGraphService

    fabric_svc = ControlFabricService()
    graph_svc = ControlGraphService(fabric_svc)
    reasoning_svc = BoundedReasoningService(graph_svc)
    return reasoning_svc.get_summary(tenant_id)
