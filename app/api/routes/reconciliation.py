"""Reconciliation routes — cross-plane margin analysis and evidence validation."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.security import TenantContext
from app.db.session import get_db
from app.domain_packs.reconciliation import (
    ContradictionDetector,
    EvidenceChainValidator,
    MarginDiagnosisReconciler,
)
from app.services.reconciler.service import ReconcilerService

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ReconciliationRequest(BaseModel):
    contract: dict = Field(..., description="Parsed contract payload")
    work_orders: list[dict] = Field(default_factory=list)
    incidents: list[dict] = Field(default_factory=list)
    rate_card: list[dict] = Field(default_factory=list)
    obligations: list[dict] = Field(default_factory=list)


class ContradictionCheckRequest(BaseModel):
    contract: dict = Field(..., description="Parsed contract payload")
    work_orders: list[dict] = Field(default_factory=list)
    incidents: list[dict] = Field(default_factory=list)


class EvidenceChainRequest(BaseModel):
    evidence_stages: dict[str, list[str]] = Field(
        ...,
        description="Map of stage name to list of evidence references",
    )


class ReconciliationResponse(BaseModel):
    verdict: str
    total_at_risk_value: float = 0.0
    leakage_trigger_count: int = 0
    contradiction_count: int = 0
    evidence_chain_valid: bool = True
    executive_summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ContradictionResponse(BaseModel):
    contradictions: list[dict] = Field(default_factory=list)
    total: int = 0


class EvidenceChainResponse(BaseModel):
    valid: bool
    missing_stages: list[str] = Field(default_factory=list)
    stage_results: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/run", response_model=ReconciliationResponse)
async def run_reconciliation(
    body: ReconciliationRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    """Run full cross-plane margin reconciliation."""
    svc = ReconcilerService(db)
    result = await svc.run_margin_reconciliation(
        tenant_id=ctx.tenant_id,
        contract=body.contract,
        work_orders=body.work_orders,
        incidents=body.incidents,
        rate_card=body.rate_card,
        obligations=body.obligations,
    )
    return ReconciliationResponse(
        verdict=result.get("verdict", "unknown"),
        total_at_risk_value=result.get("total_at_risk_value", 0.0),
        leakage_trigger_count=result.get("leakage_trigger_count", 0),
        contradiction_count=result.get("contradiction_count", 0),
        evidence_chain_valid=result.get("evidence_chain_valid", True),
        executive_summary=result.get("executive_summary", ""),
        details=result,
    )


@router.post("/contradictions", response_model=ContradictionResponse)
async def check_contradictions(
    body: ContradictionCheckRequest,
    ctx: TenantContext = Depends(get_current_user),
):
    """Detect contradictions between contract, work orders, and incidents."""
    detector = ContradictionDetector()
    contradictions = detector.detect(
        contract=body.contract,
        work_orders=body.work_orders,
        incidents=body.incidents,
    )
    return ContradictionResponse(
        contradictions=[c.__dict__ if hasattr(c, "__dict__") else c for c in contradictions],
        total=len(contradictions),
    )


@router.post("/evidence-chain", response_model=EvidenceChainResponse)
async def validate_evidence_chain(
    body: EvidenceChainRequest,
    ctx: TenantContext = Depends(get_current_user),
):
    """Validate the 4-stage evidence chain for billing."""
    validator = EvidenceChainValidator()
    result = validator.validate(body.evidence_stages)
    return EvidenceChainResponse(
        valid=result.get("valid", False),
        missing_stages=result.get("missing_stages", []),
        stage_results=result.get("stage_results", {}),
    )


@router.get("/{case_id}/summary", response_model=ReconciliationResponse)
async def get_reconciliation_summary(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    """Retrieve stored reconciliation results for a case."""
    svc = ReconcilerService(db)
    result = await svc.get_reconciliation_result(case_id, ctx.tenant_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reconciliation result not found")
    return ReconciliationResponse(
        verdict=result.get("verdict", "unknown"),
        total_at_risk_value=result.get("total_at_risk_value", 0.0),
        leakage_trigger_count=result.get("leakage_trigger_count", 0),
        contradiction_count=result.get("contradiction_count", 0),
        evidence_chain_valid=result.get("evidence_chain_valid", True),
        executive_summary=result.get("executive_summary", ""),
        details=result,
    )
