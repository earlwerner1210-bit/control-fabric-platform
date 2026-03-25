"""Compiler service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.schemas.control_objects import ControlObjectResponse
from shared.security.auth import get_current_user

from .schemas import CompileContractRequest, CompileIncidentRequest, CompileResponse, CompileWorkOrderRequest
from .service import CompilerService

router = APIRouter(prefix="/compile", tags=["compiler"])


def _obj_to_response(obj) -> ControlObjectResponse:
    return ControlObjectResponse(
        id=obj.id,
        tenant_id=obj.tenant_id,
        control_type=obj.control_type,
        label=obj.label,
        description=obj.description,
        payload=obj.payload or {},
        source_document_id=obj.source_document_id,
        source_chunk_id=obj.source_chunk_id,
        confidence=obj.confidence,
        is_active=obj.is_active,
        metadata=obj.metadata_ or {},
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


@router.post("/contract", response_model=CompileResponse, status_code=201)
async def compile_contract(
    body: CompileContractRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CompilerService(db)
    result = await svc.compile_contract(
        body.document_id,
        ctx.tenant_id,
        body.extract_obligations,
        body.extract_penalties,
        body.extract_billing,
    )
    return CompileResponse(
        document_id=body.document_id,
        control_objects=[_obj_to_response(o) for o in result["objects"]],
        links_created=result["links_created"],
        warnings=result["warnings"],
    )


@router.post("/work-order", response_model=CompileResponse, status_code=201)
async def compile_work_order(
    body: CompileWorkOrderRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CompilerService(db)
    result = await svc.compile_work_order(body.document_id, ctx.tenant_id)
    return CompileResponse(
        document_id=body.document_id,
        control_objects=[_obj_to_response(o) for o in result["objects"]],
        links_created=result["links_created"],
        warnings=result["warnings"],
    )


@router.post("/incident", response_model=CompileResponse, status_code=201)
async def compile_incident(
    body: CompileIncidentRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CompilerService(db)
    result = await svc.compile_incident(body.document_id, ctx.tenant_id, body.severity)
    return CompileResponse(
        document_id=body.document_id,
        control_objects=[_obj_to_response(o) for o in result["objects"]],
        links_created=result["links_created"],
        warnings=result["warnings"],
    )
