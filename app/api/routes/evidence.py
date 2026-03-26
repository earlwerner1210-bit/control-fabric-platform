"""Evidence review and traceability API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.evidence import (
    EvidenceBundleCreate,
    EvidenceBundleResponse,
    EvidenceTrace,
    ModelLineageTrace,
    ValidationTrace,
)
from app.services.evidence import EvidenceService

router = APIRouter(prefix="/pilot-cases", tags=["evidence"])

_evidence_service = EvidenceService()


@router.post("/{pilot_case_id}/evidence", response_model=EvidenceBundleResponse, status_code=201)
async def create_evidence_bundle(pilot_case_id: uuid.UUID, data: EvidenceBundleCreate):
    data.pilot_case_id = pilot_case_id
    return _evidence_service.create_bundle(data)


@router.get("/{pilot_case_id}/evidence", response_model=EvidenceBundleResponse)
async def get_evidence_bundle(pilot_case_id: uuid.UUID):
    bundle = _evidence_service.get_bundle(pilot_case_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="No evidence bundle found for this case")
    return bundle


@router.get("/{pilot_case_id}/evidence/trace", response_model=EvidenceTrace)
async def get_evidence_trace(pilot_case_id: uuid.UUID):
    trace = _evidence_service.get_trace(pilot_case_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="No evidence trace found for this case")
    return trace


@router.get("/{pilot_case_id}/validation-trace", response_model=ValidationTrace)
async def get_validation_trace(pilot_case_id: uuid.UUID):
    trace = _evidence_service.get_validation_trace(pilot_case_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="No validation trace found for this case")
    return trace


@router.get("/{pilot_case_id}/model-lineage", response_model=ModelLineageTrace)
async def get_model_lineage(pilot_case_id: uuid.UUID):
    lineage = _evidence_service.get_model_lineage(pilot_case_id)
    if lineage is None:
        raise HTTPException(status_code=404, detail="No model lineage found for this case")
    return lineage
