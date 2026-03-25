"""Ingest service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.security.auth import get_current_tenant

from .schemas import DocumentResponse, ParseRequest, ParseResponse, UploadResponse
from .service import IngestService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    svc = IngestService(db)
    doc = await svc.upload_document(file, tenant_id)
    return UploadResponse(
        id=str(doc.id),
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
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    svc = IngestService(db)
    doc = await svc.parse_document(document_id, tenant_id, body.domain, body.options)
    parsed = doc.metadata_.get("parsed_content") if doc.metadata_ else None
    doc_type = doc.metadata_.get("document_type") if doc.metadata_ else None
    return ParseResponse(
        document_id=str(doc.id),
        status=doc.status,
        document_type=doc_type,
        parsed_content=parsed,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    svc = IngestService(db)
    doc = await svc.get_document(document_id, tenant_id)
    return DocumentResponse(
        id=str(doc.id),
        filename=doc.filename,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        checksum=doc.checksum,
        status=doc.status,
        document_type=doc.metadata_.get("document_type") if doc.metadata_ else None,
        storage_path=doc.s3_key,
        tenant_id=str(doc.tenant_id),
        created_at=str(doc.created_at),
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    svc = IngestService(db)
    docs = await svc.list_documents(tenant_id, skip, limit)
    return [
        DocumentResponse(
            id=str(d.id),
            filename=d.filename,
            content_type=d.content_type,
            size_bytes=d.size_bytes,
            checksum=d.checksum,
            status=d.status,
            document_type=d.metadata_.get("document_type") if d.metadata_ else None,
            storage_path=d.s3_key,
            tenant_id=str(d.tenant_id),
            created_at=str(d.created_at),
        )
        for d in docs
    ]
