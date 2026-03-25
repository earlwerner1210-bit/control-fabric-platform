"""Chunking service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.security.auth import get_current_user

from .schemas import ChunkCreateRequest, ChunkCreateResponse, ChunkResponse
from .service import ChunkingService

router = APIRouter(prefix="/chunks", tags=["chunks"])


@router.post("/create", response_model=ChunkCreateResponse, status_code=201)
async def create_chunks(
    body: ChunkCreateRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ChunkingService(db)
    chunks = await svc.chunk_document(
        document_id=body.document_id,
        tenant_id=ctx.tenant_id,
        chunk_size=body.chunk_size,
        overlap=body.overlap,
    )
    return ChunkCreateResponse(
        document_id=body.document_id,
        chunks_created=len(chunks),
        chunks=[
            ChunkResponse(
                id=c.id,
                document_id=c.document_id,
                chunk_index=c.chunk_index,
                text=c.content,
                token_count=c.token_count,
                metadata=c.metadata_ or {},
            )
            for c in chunks
        ],
    )


@router.get("/{doc_id}", response_model=list[ChunkResponse])
async def get_chunks(
    doc_id: str,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ChunkingService(db)
    chunks = await svc.get_chunks_by_document(doc_id, ctx.tenant_id)
    return [
        ChunkResponse(
            id=c.id,
            document_id=c.document_id,
            chunk_index=c.chunk_index,
            text=c.content,
            token_count=c.token_count,
            metadata=c.metadata_ or {},
        )
        for c in chunks
    ]
