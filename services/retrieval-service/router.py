"""Retrieval service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.security.auth import get_current_user

from .schemas import Citation, RetrievalMode, RetrievalRequest, RetrievalResponse
from .service import RetrievalService

router = APIRouter(tags=["retrieval"])


@router.post("/retrieve", response_model=RetrievalResponse)
async def retrieve(
    body: RetrievalRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RetrievalService(db)

    if body.mode == RetrievalMode.keyword:
        raw = await svc.keyword_search(body.query, ctx.tenant_id, body.filters, body.top_k)
    elif body.mode == RetrievalMode.vector:
        raw = await svc.vector_search(body.query, ctx.tenant_id, body.filters, body.top_k)
    else:
        raw = await svc.hybrid_search(body.query, ctx.tenant_id, body.filters, body.top_k)

    citations = svc.build_citations(raw)
    return RetrievalResponse(
        query=body.query,
        mode=body.mode.value,
        total_results=len(citations),
        results=[Citation(**c) for c in citations],
    )
