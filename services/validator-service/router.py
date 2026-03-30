"""Validator service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.schemas.validation import ValidationResultResponse, ValidationRuleResult
from shared.security.auth import get_current_user

from .schemas import ValidateRequest, ValidateResponse
from .service import ValidatorService

router = APIRouter(tags=["validator"])


def _vr_to_response(vr) -> ValidationResultResponse:
    return ValidationResultResponse(
        id=vr.id,
        tenant_id=vr.tenant_id,
        target_type=vr.target_type,
        target_id=vr.target_id,
        status=vr.status.value if hasattr(vr.status, "value") else vr.status,
        rules_passed=vr.rules_passed,
        rules_warned=vr.rules_warned,
        rules_blocked=vr.rules_blocked,
        rule_results=[ValidationRuleResult(**r) for r in (vr.rule_results or [])],
        metadata=vr.metadata_ or {},
        created_at=vr.created_at,
        updated_at=vr.updated_at,
    )


@router.post("/validate", response_model=ValidateResponse, status_code=200)
async def validate(
    body: ValidateRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ValidatorService(db)
    result = await svc.validate_output(
        control_object_ids=body.control_object_ids,
        domain=body.domain,
        rules=body.rules,
        tenant_id=ctx.tenant_id,
        case_id=body.case_id,
    )
    return ValidateResponse(
        case_id=result["case_id"],
        results=[_vr_to_response(vr) for vr in result["results"]],
        overall_status=result["overall_status"],
    )


@router.get("/validations/{case_id}", response_model=list[ValidationResultResponse])
async def get_validations(
    case_id: str,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ValidatorService(db)
    results = await svc.get_validations_by_case(case_id, ctx.tenant_id)
    return [_vr_to_response(vr) for vr in results]
