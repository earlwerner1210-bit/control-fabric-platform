"""Workflow case endpoints -- margin diagnosis, case retrieval, audit, and validations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps.auth import get_current_user
from app.core.exceptions import NotFoundError
from app.core.security import TenantContext
from app.core.telemetry import metrics
from app.schemas.audit import AuditEventResponse, AuditTimelineResponse
from app.schemas.validation import ValidationResultResponse
from app.schemas.workflows import (
    MarginDiagnosisInput,
    MarginDiagnosisOutput,
    MarginVerdict,
    WorkflowCaseResponse,
    WorkflowStatusEnum,
)

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])

# ---------------------------------------------------------------------------
# In-memory stub store
# ---------------------------------------------------------------------------

_CASES: dict[str, dict[str, Any]] = {}


@router.post("/margin-diagnosis", response_model=MarginDiagnosisOutput, status_code=201)
async def start_margin_diagnosis(
    body: MarginDiagnosisInput,
    ctx: TenantContext = Depends(get_current_user),
) -> MarginDiagnosisOutput:
    """Start a margin-diagnosis workflow.

    In production this endpoint starts the Temporal workflow and returns
    the case reference.  Here we return a synchronous stub so the API
    is testable without Temporal.
    """
    metrics.increment("workflows.margin_diagnosis.started")

    case_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    case_record: dict[str, Any] = {
        "id": str(case_id),
        "tenant_id": ctx.tenant_id,
        "workflow_type": "margin_diagnosis",
        "status": WorkflowStatusEnum.RUNNING,
        "verdict": None,
        "input_payload": body.model_dump(mode="json"),
        "output_payload": {},
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }
    _CASES[str(case_id)] = case_record

    return MarginDiagnosisOutput(
        case_id=case_id,
        verdict=MarginVerdict.UNKNOWN,
        leakage_drivers=[],
        recovery_recommendations=[],
        evidence_object_ids=[],
        executive_summary=None,
        billability_details={},
        penalty_exposure={},
    )


@router.get("/{case_id}", response_model=WorkflowCaseResponse)
async def get_case(
    case_id: str,
    ctx: TenantContext = Depends(get_current_user),
) -> WorkflowCaseResponse:
    """Retrieve a workflow case by its ID."""
    case = _CASES.get(case_id)
    if case is None:
        raise NotFoundError(detail=f"Case {case_id} not found")

    return WorkflowCaseResponse(
        id=uuid.UUID(case["id"]),
        tenant_id=uuid.UUID(case["tenant_id"]) if isinstance(case["tenant_id"], str) else case["tenant_id"],
        workflow_type=case["workflow_type"],
        status=case["status"],
        verdict=case.get("verdict"),
        input_payload=case.get("input_payload", {}),
        output_payload=case.get("output_payload", {}),
        error_message=case.get("error_message"),
        created_at=case["created_at"],
        updated_at=case["updated_at"],
    )


@router.get("/{case_id}/audit", response_model=AuditTimelineResponse)
async def get_case_audit(
    case_id: str,
    ctx: TenantContext = Depends(get_current_user),
) -> AuditTimelineResponse:
    """Retrieve the audit timeline for a workflow case."""
    case = _CASES.get(case_id)
    if case is None:
        raise NotFoundError(detail=f"Case {case_id} not found")

    now = datetime.now(timezone.utc)
    events = [
        AuditEventResponse(
            id=uuid.uuid4(),
            event_type="workflow.started",
            actor_id=uuid.UUID(ctx.user_id),
            resource_type="workflow_case",
            resource_id=uuid.UUID(case_id),
            payload={"workflow_type": case["workflow_type"]},
            created_at=case["created_at"],
        ),
    ]

    return AuditTimelineResponse(events=events, total=len(events))


@router.get("/{case_id}/validations", response_model=list[ValidationResultResponse])
async def get_case_validations(
    case_id: str,
    ctx: TenantContext = Depends(get_current_user),
) -> list[ValidationResultResponse]:
    """Retrieve validation results associated with a workflow case."""
    case = _CASES.get(case_id)
    if case is None:
        raise NotFoundError(detail=f"Case {case_id} not found")

    # In production this queries the validation results table.
    # Stub: return an empty list.
    return []
