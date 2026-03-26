"""Workflow case routes – trigger workflows and retrieve results."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.security import TenantContext
from app.db.models import ValidationResult, WorkflowCase
from app.db.session import get_db
from app.schemas.audit import AuditEventResponse
from app.schemas.common import PaginatedResponse
from app.schemas.validation import ValidationResultResponse
from app.schemas.workflows import (
    ContractCompileInput,
    ContractCompileOutput,
    IncidentDispatchInput,
    IncidentDispatchOutput,
    MarginDiagnosisInput,
    MarginDiagnosisOutput,
    ReconciliationSummaryOutput,
    SPENBillabilityInput,
    SPENBillabilityOutput,
    SPENReadinessInput,
    SPENReadinessOutput,
    VodafoneIncidentTriageInput,
    VodafoneIncidentTriageOutput,
    WorkflowCaseResponse,
    WorkflowTimelineEntry,
    WorkOrderReadinessInput,
    WorkOrderReadinessOutput,
)
from app.services.audit.service import AuditService
from app.services.reporting.service import ReportingService
from app.workflows.orchestrator import WorkflowOrchestrator

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("/contract-compile", response_model=ContractCompileOutput)
async def trigger_contract_compile(
    body: ContractCompileInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    orch = WorkflowOrchestrator(db)
    result = await orch.run_contract_compile(ctx.tenant_id, ctx.user_id, body)
    return result


@router.post("/work-order-readiness", response_model=WorkOrderReadinessOutput)
async def trigger_work_order_readiness(
    body: WorkOrderReadinessInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    orch = WorkflowOrchestrator(db)
    result = await orch.run_work_order_readiness(ctx.tenant_id, ctx.user_id, body)
    return result


@router.post("/incident-dispatch-reconcile", response_model=IncidentDispatchOutput)
async def trigger_incident_dispatch(
    body: IncidentDispatchInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    orch = WorkflowOrchestrator(db)
    result = await orch.run_incident_dispatch(ctx.tenant_id, ctx.user_id, body)
    return result


@router.post("/margin-diagnosis", response_model=MarginDiagnosisOutput)
async def trigger_margin_diagnosis(
    body: MarginDiagnosisInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    orch = WorkflowOrchestrator(db)
    result = await orch.run_margin_diagnosis(ctx.tenant_id, ctx.user_id, body)
    return result


@router.post("/spen-readiness", response_model=SPENReadinessOutput)
async def trigger_spen_readiness(
    body: SPENReadinessInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    orch = WorkflowOrchestrator(db)
    result = await orch.run_spen_readiness(ctx.tenant_id, ctx.user_id, body)
    return result


@router.post("/spen-billability", response_model=SPENBillabilityOutput)
async def trigger_spen_billability(
    body: SPENBillabilityInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    orch = WorkflowOrchestrator(db)
    result = await orch.run_spen_billability(ctx.tenant_id, ctx.user_id, body)
    return result


@router.post("/vodafone-incident-triage", response_model=VodafoneIncidentTriageOutput)
async def trigger_vodafone_incident_triage(
    body: VodafoneIncidentTriageInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    orch = WorkflowOrchestrator(db)
    result = await orch.run_vodafone_incident_triage(ctx.tenant_id, ctx.user_id, body)
    return result


@router.get("/{case_id}", response_model=WorkflowCaseResponse)
async def get_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    result = await db.execute(
        select(WorkflowCase).where(
            WorkflowCase.id == case_id, WorkflowCase.tenant_id == ctx.tenant_id
        )
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return WorkflowCaseResponse.model_validate(case)


@router.get("/{case_id}/audit", response_model=list[AuditEventResponse])
async def get_case_audit(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    svc = AuditService(db)
    events = await svc.get_case_audit_trail(case_id, ctx.tenant_id)
    return [AuditEventResponse.model_validate(e) for e in events]


@router.get("/{case_id}/validations", response_model=list[ValidationResultResponse])
async def get_case_validations(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    result = await db.execute(
        select(ValidationResult).where(
            ValidationResult.workflow_case_id == case_id,
            ValidationResult.tenant_id == ctx.tenant_id,
        )
    )
    validations = result.scalars().all()
    return [ValidationResultResponse.model_validate(v) for v in validations]


@router.get("/{case_id}/timeline", response_model=list[WorkflowTimelineEntry])
async def get_case_timeline(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    """Get ordered audit timeline for a workflow case."""
    svc = AuditService(db)
    timeline = await svc.get_workflow_timeline(case_id, ctx.tenant_id)
    return timeline


@router.get("/{case_id}/report", response_model=dict)
async def get_case_report(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    """Get full margin report for a completed case."""
    svc = ReportingService(db)
    report = await svc.generate_margin_report(ctx.tenant_id, case_id)
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])
    return report


@router.get("/{case_id}/reconciliation", response_model=ReconciliationSummaryOutput)
async def get_case_reconciliation(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    """Get reconciliation summary for a case."""
    svc = ReportingService(db)
    report = await svc.generate_reconciliation_report(ctx.tenant_id, case_id)
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])
    return ReconciliationSummaryOutput(
        case_id=uuid.UUID(report["case_id"]),
        links_found=report.get("links_found", 0),
        conflicts_found=report.get("conflicts_found", 0),
        leakage_patterns_found=report.get("leakage_patterns_found", 0),
        verdict=report.get("verdict", ""),
        conflicts=report.get("conflicts", []),
        evidence_chain_status=report.get("evidence_chain_status", "unknown"),
    )


@router.get("", response_model=PaginatedResponse[WorkflowCaseResponse])
async def list_cases(
    page: int = 1,
    page_size: int = 50,
    workflow_type: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    stmt = select(WorkflowCase).where(WorkflowCase.tenant_id == ctx.tenant_id)
    if workflow_type:
        stmt = stmt.where(WorkflowCase.workflow_type == workflow_type)
    if status:
        stmt = stmt.where(WorkflowCase.status == status)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar() or 0

    stmt = (
        stmt.offset((page - 1) * page_size)
        .limit(page_size)
        .order_by(WorkflowCase.created_at.desc())
    )
    result = await db.execute(stmt)
    cases = result.scalars().all()

    return PaginatedResponse(
        items=[WorkflowCaseResponse.model_validate(c) for c in cases],
        total=total,
        page=page,
        page_size=page_size,
    )
