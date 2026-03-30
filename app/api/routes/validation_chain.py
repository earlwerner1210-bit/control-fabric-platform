"""API routes for Validation Chain — 8-stage release gate."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.validation_chain import (
    ValidationChainRequest,
    ValidationChainResponse,
    ValidationChainSummary,
)

router = APIRouter(prefix="/validation-chain", tags=["validation-chain"])


@router.post("/run", response_model=ValidationChainResponse, status_code=201)
def run_chain(request: ValidationChainRequest) -> ValidationChainResponse:
    from app.services.validation_chain import ValidationChainService

    svc = ValidationChainService()
    return svc.run_chain(request)


@router.get("/runs/{run_id}", response_model=ValidationChainResponse)
def get_run(run_id: uuid.UUID) -> ValidationChainResponse:
    from app.services.validation_chain import ValidationChainService

    svc = ValidationChainService()
    result = svc.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.get("/summary", response_model=ValidationChainSummary)
def get_summary(tenant_id: uuid.UUID) -> ValidationChainSummary:
    from app.services.validation_chain import ValidationChainService

    svc = ValidationChainService()
    return svc.get_summary(tenant_id)
