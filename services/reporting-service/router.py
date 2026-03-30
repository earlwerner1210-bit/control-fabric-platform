"""Reporting service HTTP endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.security.auth import get_current_user

from .schemas import GenerateReportRequest, ReportResponse
from .service import ReportingService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate", response_model=ReportResponse, status_code=201)
async def generate_report(
    body: GenerateReportRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ReportingService(db)

    if body.report_type == "management_summary":
        content = await svc.generate_management_summary(body.case_id, ctx.tenant_id)
    else:
        content = await svc.generate_case_summary(
            body.case_id,
            ctx.tenant_id,
            body.include_audit_trail,
            body.include_validations,
        )

    if body.format == "text":
        exported = svc.export_report_data(content, "text")
        content = exported

    return ReportResponse(
        id=uuid.uuid4(),
        case_id=body.case_id,
        tenant_id=ctx.tenant_id,
        report_type=body.report_type,
        content=content,
        format=body.format,
        created_at=datetime.utcnow(),
    )


@router.get("/{case_id}", response_model=ReportResponse)
async def get_report(
    case_id: str,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ReportingService(db)
    content = await svc.generate_case_summary(case_id, ctx.tenant_id)
    return ReportResponse(
        id=uuid.uuid4(),
        case_id=case_id,
        tenant_id=ctx.tenant_id,
        report_type="case_summary",
        content=content,
        format="json",
        created_at=datetime.utcnow(),
    )
