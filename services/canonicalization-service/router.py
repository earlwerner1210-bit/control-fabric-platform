"""Canonicalization service HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.base import get_db
from shared.schemas.common import TenantContext
from shared.security.auth import get_current_user

from .schemas import (
    EntityResponse,
    MergeEntitiesRequest,
    RegisterEntityRequest,
    ResolveEntityRequest,
    ResolveEntityResponse,
)
from .service import CanonicalizationService

router = APIRouter(prefix="/entities", tags=["entities"])


def _entity_to_response(entity) -> EntityResponse:
    aliases = entity.aliases or []
    if isinstance(aliases, dict):
        aliases = list(aliases.values())
    return EntityResponse(
        id=entity.id,
        canonical_name=entity.canonical_name,
        entity_type=entity.entity_type,
        aliases=[str(a) for a in aliases],
        metadata=entity.metadata_ or {},
        tenant_id=entity.tenant_id,
    )


@router.post("/resolve", response_model=ResolveEntityResponse)
async def resolve_entity(
    body: ResolveEntityRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CanonicalizationService(db)
    result = await svc.resolve_entity(body.name, body.entity_type, ctx.tenant_id, body.threshold)
    entity_resp = _entity_to_response(result["entity"]) if result["entity"] else None
    candidates = [_entity_to_response(c) for c in result["candidates"]]
    return ResolveEntityResponse(
        resolved=result["resolved"],
        entity=entity_resp,
        similarity=result["similarity"],
        candidates=candidates,
    )


@router.post("", response_model=EntityResponse, status_code=201)
async def register_entity(
    body: RegisterEntityRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CanonicalizationService(db)
    entity = await svc.register_entity(
        body.canonical_name, body.entity_type, ctx.tenant_id, body.aliases, body.metadata
    )
    return _entity_to_response(entity)


@router.post("/merge", response_model=EntityResponse)
async def merge_entities(
    body: MergeEntitiesRequest,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CanonicalizationService(db)
    entity = await svc.merge_entities(body.source_id, body.target_id, ctx.tenant_id)
    return _entity_to_response(entity)


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CanonicalizationService(db)
    entity = await svc.get_entity(entity_id, ctx.tenant_id)
    return _entity_to_response(entity)


@router.get("", response_model=list[EntityResponse])
async def list_entities(
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CanonicalizationService(db)
    entities = await svc.list_entities(ctx.tenant_id, search, skip, limit)
    return [_entity_to_response(e) for e in entities]
