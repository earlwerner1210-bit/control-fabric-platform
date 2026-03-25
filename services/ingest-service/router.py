"""Ingest service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.schemas.documents import DocumentResponse
from shared.security.auth import get_current_user

from .schemas import DocumentListItem, ParseRequest, ParseResponse, UploadResponse
from .service import IngestService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = IngestService(db)
    doc = await svc.upload_document(file, ctx.tenant_id)
    return UploadResponse(
        id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        checksum=doc.checksum,
        status=doc.status,
    )


@router.post("/{document_id}/parse", response_model=ParseResponse)
async def parse_document(
    document_id: str,
    body: ParseRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = IngestService(db)
    doc = await svc.parse_document(document_id, ctx.tenant_id, body.domain, body.options)
    parsed = doc.metadata_.get("parsed_content") if doc.metadata_ else None
    doc_type = doc.metadata_.get("document_type") if doc.metadata_ else None
    return ParseResponse(
        document_id=doc.id,
        status=doc.status,
        document_type=doc_type,
        parsed_content=parsed,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = IngestService(db)
    doc = await svc.get_document(document_id, ctx.tenant_id)
    return DocumentResponse.model_validate(doc)


@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = IngestService(db)
    docs = await svc.list_documents(ctx.tenant_id, skip, limit)
    return [
        DocumentListItem(
            id=d.id,
            filename=d.filename,
            content_type=d.content_type,
            size_bytes=d.size_bytes,
            checksum=d.checksum,
            status=d.status,
            document_type=(d.metadata_ or {}).get("document_type"),
            s3_key=d.s3_key,
            tenant_id=d.tenant_id,
            created_at=d.created_at,
        )
        for d in docs
    ]
