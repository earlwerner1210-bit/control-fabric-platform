"""Contract compilation endpoint -- triggers the contract-compile workflow."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.deps.auth import get_current_user
from app.core.security import TenantContext
from app.core.telemetry import metrics
from app.schemas.workflows import (
    ContractCompileInput,
    ContractCompileOutput,
    ValidationStatus,
    WorkflowStatusEnum,
)

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])


@router.post("/{contract_id}/compile", response_model=ContractCompileOutput)
async def compile_contract(
    contract_id: str,
    body: ContractCompileInput | None = None,
    ctx: TenantContext = Depends(get_current_user),
) -> ContractCompileOutput:
    """Trigger the contract-compile workflow for a given contract document.

    In a production deployment this endpoint starts the Temporal workflow
    and returns the initial case reference.  Here we return a synchronous
    stub response so the API is testable without Temporal running.
    """
    metrics.increment("workflows.contract_compile.started")

    case_id = uuid.uuid4()
    contract_uuid = uuid.UUID(contract_id)

    sla_ids = body.sla_document_ids if body else []
    rate_card_ids = body.rate_card_document_ids if body else []

    return ContractCompileOutput(
        case_id=case_id,
        status=WorkflowStatusEnum.RUNNING,
        contract_summary=None,
        obligation_count=0,
        penalty_count=0,
        billable_event_count=0,
        control_object_ids=[],
        validation_status=None,
        errors=[],
    )
