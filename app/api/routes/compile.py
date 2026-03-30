"""Compile routes – compile individual documents into control objects."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.exceptions import NotFoundError
from app.core.security import TenantContext
from app.db.models import Document
from app.db.session import get_db
from app.schemas.control_objects import ControlObjectResponse
from app.services.compiler.service import CompilerService

router = APIRouter(tags=["compile"])


@router.post("/contracts/{document_id}/compile", response_model=list[ControlObjectResponse])
async def compile_contract(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    doc = await _get_doc(db, document_id, ctx.tenant_id)
    compiler = CompilerService(db)
    objects = await compiler.compile_contract(
        tenant_id=ctx.tenant_id,
        parsed_payload=doc.parsed_payload or {},
        source_document_id=doc.id,
    )
    return [ControlObjectResponse.model_validate(o) for o in objects]


@router.post("/work-orders/{document_id}/compile", response_model=list[ControlObjectResponse])
async def compile_work_order(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    doc = await _get_doc(db, document_id, ctx.tenant_id)
    compiler = CompilerService(db)
    objects = await compiler.compile_work_order(
        tenant_id=ctx.tenant_id,
        parsed_payload=doc.parsed_payload or {},
        source_document_id=doc.id,
    )
    return [ControlObjectResponse.model_validate(o) for o in objects]


@router.post("/incidents/{document_id}/compile", response_model=list[ControlObjectResponse])
async def compile_incident(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    doc = await _get_doc(db, document_id, ctx.tenant_id)
    compiler = CompilerService(db)
    objects = await compiler.compile_incident(
        tenant_id=ctx.tenant_id,
        parsed_payload=doc.parsed_payload or {},
        source_document_id=doc.id,
    )
    return [ControlObjectResponse.model_validate(o) for o in objects]


async def _get_doc(db: AsyncSession, doc_id: uuid.UUID, tenant_id: uuid.UUID) -> Document:
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.tenant_id == tenant_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError(f"Document {doc_id} not found")
    if not doc.parsed_payload:
        raise NotFoundError(f"Document {doc_id} has not been parsed yet")
    return doc
