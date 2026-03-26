"""Case routes — trigger workflows and query case state."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client as TemporalClient

from apps.api.dependencies import get_current_user, get_db, get_service_clients, get_tenant_context

router = APIRouter(prefix="/cases", tags=["cases"])


# ── Schemas ───────────────────────────────────────────────────────────────


class ContractCompileRequest(BaseModel):
    document_ids: list[str]
    domain_pack: str = "contract-margin"
    options: dict[str, Any] = Field(default_factory=dict)


class WorkOrderReadinessRequest(BaseModel):
    work_order_id: str
    engineer_id: str | None = None
    domain_pack: str = "utilities-field"
    options: dict[str, Any] = Field(default_factory=dict)


class IncidentDispatchRequest(BaseModel):
    incident_id: str
    domain_pack: str = "telco-ops"
    options: dict[str, Any] = Field(default_factory=dict)


class MarginDiagnosisRequest(BaseModel):
    contract_id: str
    period_start: str | None = None
    period_end: str | None = None
    domain_pack: str = "contract-margin"
    options: dict[str, Any] = Field(default_factory=dict)


class CaseStartResponse(BaseModel):
    case_id: str
    workflow_id: str
    workflow_type: str
    status: str


class CaseResponse(BaseModel):
    id: str
    workflow_type: str
    status: str
    tenant_id: str
    created_at: str | None = None
    completed_at: str | None = None
    result: dict[str, Any] | None = None


class CaseListResponse(BaseModel):
    items: list[CaseResponse]
    total: int
    page: int
    page_size: int


class AuditEntryResponse(BaseModel):
    id: str
    event_type: str
    actor: str
    service: str
    detail: dict[str, Any]
    created_at: str | None = None


class ValidationResponse(BaseModel):
    id: str
    domain: str
    status: str
    rules_applied: list[str]
    findings: list[dict[str, Any]]
    confidence: float


# ── Helpers ───────────────────────────────────────────────────────────────


async def _get_temporal_client() -> TemporalClient:
    """Create a Temporal client from current settings."""
    clients = get_service_clients()
    return await TemporalClient.connect(clients.temporal_host, namespace=clients.temporal_namespace)


async def _create_case_record(
    db: AsyncSession,
    case_id: str,
    workflow_type: str,
    tenant_id: str,
    workflow_id: str,
) -> None:
    """Insert a case tracking row."""
    await db.execute(
        text(
            "INSERT INTO cases (id, workflow_type, status, tenant_id, workflow_id) "
            "VALUES (:id, :workflow_type, :status, :tenant_id, :workflow_id)"
        ),
        {
            "id": case_id,
            "workflow_type": workflow_type,
            "status": "running",
            "tenant_id": tenant_id,
            "workflow_id": workflow_id,
        },
    )


# ── Workflow trigger endpoints ────────────────────────────────────────────


@router.post(
    "/contract-compile", response_model=CaseStartResponse, status_code=status.HTTP_202_ACCEPTED
)
async def trigger_contract_compile(
    body: ContractCompileRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_context),
) -> CaseStartResponse:
    """Start the contract compile workflow."""
    case_id = str(uuid.uuid4())
    workflow_id = f"contract-compile-{case_id}"

    client = await _get_temporal_client()
    await client.start_workflow(
        "ContractCompileWorkflow",
        {
            "case_id": case_id,
            "tenant_id": tenant_id,
            "document_ids": body.document_ids,
            "domain_pack": body.domain_pack,
            "options": body.options,
        },
        id=workflow_id,
        task_queue="control-fabric-workflows",
    )

    await _create_case_record(db, case_id, "contract_compile", tenant_id, workflow_id)

    return CaseStartResponse(
        case_id=case_id,
        workflow_id=workflow_id,
        workflow_type="contract_compile",
        status="running",
    )


@router.post(
    "/work-order-readiness", response_model=CaseStartResponse, status_code=status.HTTP_202_ACCEPTED
)
async def trigger_work_order_readiness(
    body: WorkOrderReadinessRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_context),
) -> CaseStartResponse:
    """Start the work order readiness workflow."""
    case_id = str(uuid.uuid4())
    workflow_id = f"work-order-readiness-{case_id}"

    client = await _get_temporal_client()
    await client.start_workflow(
        "WorkOrderReadinessWorkflow",
        {
            "case_id": case_id,
            "tenant_id": tenant_id,
            "work_order_id": body.work_order_id,
            "engineer_id": body.engineer_id,
            "domain_pack": body.domain_pack,
            "options": body.options,
        },
        id=workflow_id,
        task_queue="control-fabric-workflows",
    )

    await _create_case_record(db, case_id, "work_order_readiness", tenant_id, workflow_id)

    return CaseStartResponse(
        case_id=case_id,
        workflow_id=workflow_id,
        workflow_type="work_order_readiness",
        status="running",
    )


@router.post(
    "/incident-dispatch-reconcile",
    response_model=CaseStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_incident_dispatch(
    body: IncidentDispatchRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_context),
) -> CaseStartResponse:
    """Start the incident dispatch reconcile workflow."""
    case_id = str(uuid.uuid4())
    workflow_id = f"incident-dispatch-{case_id}"

    client = await _get_temporal_client()
    await client.start_workflow(
        "IncidentDispatchWorkflow",
        {
            "case_id": case_id,
            "tenant_id": tenant_id,
            "incident_id": body.incident_id,
            "domain_pack": body.domain_pack,
            "options": body.options,
        },
        id=workflow_id,
        task_queue="control-fabric-workflows",
    )

    await _create_case_record(db, case_id, "incident_dispatch_reconcile", tenant_id, workflow_id)

    return CaseStartResponse(
        case_id=case_id,
        workflow_id=workflow_id,
        workflow_type="incident_dispatch_reconcile",
        status="running",
    )


@router.post(
    "/margin-diagnosis", response_model=CaseStartResponse, status_code=status.HTTP_202_ACCEPTED
)
async def trigger_margin_diagnosis(
    body: MarginDiagnosisRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_context),
) -> CaseStartResponse:
    """Start the margin diagnosis workflow."""
    case_id = str(uuid.uuid4())
    workflow_id = f"margin-diagnosis-{case_id}"

    client = await _get_temporal_client()
    await client.start_workflow(
        "MarginDiagnosisWorkflow",
        {
            "case_id": case_id,
            "tenant_id": tenant_id,
            "contract_id": body.contract_id,
            "period_start": body.period_start,
            "period_end": body.period_end,
            "domain_pack": body.domain_pack,
            "options": body.options,
        },
        id=workflow_id,
        task_queue="control-fabric-workflows",
    )

    await _create_case_record(db, case_id, "margin_diagnosis", tenant_id, workflow_id)

    return CaseStartResponse(
        case_id=case_id,
        workflow_id=workflow_id,
        workflow_type="margin_diagnosis",
        status="running",
    )


# ── Query endpoints ──────────────────────────────────────────────────────


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> CaseResponse:
    """Retrieve a single case by ID."""
    result = await db.execute(
        text(
            "SELECT id, workflow_type, status, tenant_id, created_at, completed_at, result "
            "FROM cases WHERE id = :id"
        ),
        {"id": case_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return CaseResponse(
        id=row["id"],
        workflow_type=row["workflow_type"],
        status=row["status"],
        tenant_id=row["tenant_id"],
        created_at=str(row["created_at"]) if row.get("created_at") else None,
        completed_at=str(row["completed_at"]) if row.get("completed_at") else None,
        result=row["result"] if row.get("result") else None,
    )


@router.get("/{case_id}/audit", response_model=list[AuditEntryResponse])
async def get_case_audit(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> list[AuditEntryResponse]:
    """Retrieve the audit trail for a case."""
    result = await db.execute(
        text(
            "SELECT id, event_type, actor, service, detail, created_at "
            "FROM audit_entries WHERE case_id = :case_id ORDER BY created_at ASC"
        ),
        {"case_id": case_id},
    )
    return [
        AuditEntryResponse(
            id=r["id"],
            event_type=r["event_type"],
            actor=r["actor"],
            service=r["service"],
            detail=r["detail"] if r["detail"] else {},
            created_at=str(r["created_at"]) if r.get("created_at") else None,
        )
        for r in result.mappings().all()
    ]


@router.get("/{case_id}/validations", response_model=list[ValidationResponse])
async def get_case_validations(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> list[ValidationResponse]:
    """Retrieve validation results for a case."""
    result = await db.execute(
        text(
            "SELECT id, domain, status, rules_applied, findings, confidence "
            "FROM validation_results WHERE case_id = :case_id"
        ),
        {"case_id": case_id},
    )
    return [
        ValidationResponse(
            id=r["id"],
            domain=r["domain"],
            status=r["status"],
            rules_applied=r["rules_applied"] if r["rules_applied"] else [],
            findings=r["findings"] if r["findings"] else [],
            confidence=r["confidence"],
        )
        for r in result.mappings().all()
    ]


@router.get("", response_model=CaseListResponse)
async def list_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    workflow_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_context),
) -> CaseListResponse:
    """List cases for the current tenant, with optional filters."""
    conditions = ["tenant_id = :tenant_id"]
    params: dict[str, Any] = {"tenant_id": tenant_id}

    if workflow_type:
        conditions.append("workflow_type = :workflow_type")
        params["workflow_type"] = workflow_type

    if status_filter:
        conditions.append("status = :status")
        params["status"] = status_filter

    where_clause = " AND ".join(conditions)
    offset = (page - 1) * page_size

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM cases WHERE {where_clause}"),
        params,
    )
    total = count_result.scalar() or 0

    params["limit"] = page_size
    params["offset"] = offset
    result = await db.execute(
        text(
            f"SELECT id, workflow_type, status, tenant_id, created_at, completed_at, result "
            f"FROM cases WHERE {where_clause} "
            f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    )

    items = [
        CaseResponse(
            id=r["id"],
            workflow_type=r["workflow_type"],
            status=r["status"],
            tenant_id=r["tenant_id"],
            created_at=str(r["created_at"]) if r.get("created_at") else None,
            completed_at=str(r["completed_at"]) if r.get("completed_at") else None,
            result=r["result"] if r.get("result") else None,
        )
        for r in result.mappings().all()
    ]

    return CaseListResponse(items=items, total=total, page=page, page_size=page_size)
