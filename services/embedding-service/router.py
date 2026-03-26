"""Embedding service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.security.auth import get_current_user

from .schemas import (
    EmbeddingBatchRequest,
    EmbeddingBatchResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)
from .service import EmbeddingService

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post("/generate", response_model=EmbeddingResponse, status_code=201)
async def generate_embedding(
    body: EmbeddingRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = EmbeddingService(db)
    vector = await svc.generate_and_persist(body.chunk_id, body.text, ctx.tenant_id)
    return EmbeddingResponse(
        chunk_id=body.chunk_id,
        model=svc.model_name,
        dimension=svc.dimension,
        vector=vector,
    )


@router.post("/batch", response_model=EmbeddingBatchResponse, status_code=201)
async def batch_embed(
    body: EmbeddingBatchRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = EmbeddingService(db)
    items = [{"chunk_id": item.chunk_id, "text": item.text} for item in body.items]
    vectors = await svc.batch_generate_and_persist(items, ctx.tenant_id)
    return EmbeddingBatchResponse(
        model=svc.model_name,
        count=len(vectors),
        embeddings=[
            EmbeddingResponse(
                chunk_id=body.items[i].chunk_id,
                model=svc.model_name,
                dimension=svc.dimension,
                vector=v,
            )
            for i, v in enumerate(vectors)
        ],
    )
