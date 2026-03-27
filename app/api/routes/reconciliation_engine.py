"""API routes for Reconciliation Engine — conflict detection and resolution."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.reconciliation import (
    ConflictResolutionRequest,
    ReconciliationConflictResponse,
    ReconciliationRunRequest,
    ReconciliationRunResponse,
    ReconciliationSummary,
)

router = APIRouter(prefix="/reconciliation", tags=["reconciliation-engine"])


@router.post("/runs", response_model=ReconciliationRunResponse, status_code=201)
def run_reconciliation(request: ReconciliationRunRequest) -> ReconciliationRunResponse:
    from app.services.control_fabric import ControlFabricService
    from app.services.reconciliation import ReconciliationEngine

    fabric_svc = ControlFabricService()
    engine = ReconciliationEngine(fabric_svc)
    return engine.run_reconciliation(request)


@router.get("/runs/{run_id}", response_model=ReconciliationRunResponse)
def get_run(run_id: uuid.UUID) -> ReconciliationRunResponse:
    from app.services.control_fabric import ControlFabricService
    from app.services.reconciliation import ReconciliationEngine

    fabric_svc = ControlFabricService()
    engine = ReconciliationEngine(fabric_svc)
    result = engine.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.patch(
    "/conflicts/{conflict_id}",
    response_model=ReconciliationConflictResponse,
)
def resolve_conflict(
    conflict_id: uuid.UUID,
    request: ConflictResolutionRequest,
) -> ReconciliationConflictResponse:
    from app.services.control_fabric import ControlFabricService
    from app.services.reconciliation import ReconciliationEngine

    fabric_svc = ControlFabricService()
    engine = ReconciliationEngine(fabric_svc)
    result = engine.resolve_conflict(conflict_id, request)
    if result is None:
        raise HTTPException(status_code=404, detail="Conflict not found")
    return result


@router.get("/summary", response_model=ReconciliationSummary)
def get_summary(tenant_id: uuid.UUID) -> ReconciliationSummary:
    from app.services.control_fabric import ControlFabricService
    from app.services.reconciliation import ReconciliationEngine

    fabric_svc = ControlFabricService()
    engine = ReconciliationEngine(fabric_svc)
    return engine.get_summary(tenant_id)
