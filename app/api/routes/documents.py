"""Document management routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.security import TenantContext
from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.documents import (
    DocumentResponse,
    DocumentUploadResponse,
    EmbedRequest,
    EmbedResponse,
    ParseRequest,
    ParseResponse,
)
from app.services.chunking.service import ChunkingService
from app.services.embedding.service import EmbeddingService
from app.services.ingest.service import IngestService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    svc = IngestService(db)
    content = await file.read()
    doc = await svc.upload_document(
        tenant_id=ctx.tenant_id,
        filename=file.filename or "unnamed",
        content=content,
        content_type=file.content_type,
    )
    return DocumentUploadResponse(
        id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        file_size_bytes=doc.file_size_bytes,
        checksum_sha256=doc.checksum_sha256,
        status=doc.status,
        created_at=doc.created_at,
    )


@router.post("/{document_id}/parse", response_model=ParseResponse)
async def parse_document(
    document_id: uuid.UUID,
    body: ParseRequest = ParseRequest(),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    svc = IngestService(db)
    doc = await svc.parse_document(document_id, ctx.tenant_id, domain=body.domain)

    # Auto-chunk after parsing
    chunking = ChunkingService(db)
    chunks = await chunking.chunk_document(doc)

    return ParseResponse(
        document_id=doc.id,
        document_type=doc.document_type,
        status=doc.status,
        parsed_payload=doc.parsed_payload,
        chunk_count=len(chunks),
    )


@router.post("/{document_id}/embed", response_model=EmbedResponse)
async def embed_document(
    document_id: uuid.UUID,
    body: EmbedRequest = EmbedRequest(),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    svc = EmbeddingService(db)
    count = await svc.embed_document_chunks(document_id, ctx.tenant_id)
    return EmbedResponse(
        document_id=document_id,
        chunks_embedded=count,
        model_used=body.model or "default",
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    svc = IngestService(db)
    doc = await svc.get_document(document_id, ctx.tenant_id)
    return DocumentResponse.model_validate(doc)


@router.get("", response_model=PaginatedResponse[DocumentResponse])
async def list_documents(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    svc = IngestService(db)
    docs, total = await svc.list_documents(ctx.tenant_id, page, page_size)
    return PaginatedResponse(
        items=[DocumentResponse.model_validate(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )
