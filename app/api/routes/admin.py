"""Admin routes – prompts, domain packs, model runs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user, require_role
from app.core.security import TenantContext
from app.db.models import DomainPackVersion, ModelRun, PromptTemplate
from app.db.session import get_db
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/admin", tags=["admin"])


class PromptTemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    domain: str
    version: int
    system_prompt: str
    user_template: str
    is_active: bool

    class Config:
        from_attributes = True


class PromptTemplateUpdate(BaseModel):
    system_prompt: str | None = None
    user_template: str | None = None
    is_active: bool | None = None


@router.get("/prompts", response_model=list[PromptTemplateResponse])
async def list_prompts(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.tenant_id == ctx.tenant_id)
    )
    return [PromptTemplateResponse.model_validate(p) for p in result.scalars().all()]


@router.put("/prompts/{prompt_id}", response_model=PromptTemplateResponse)
async def update_prompt(
    prompt_id: uuid.UUID,
    body: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.id == prompt_id, PromptTemplate.tenant_id == ctx.tenant_id)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    if body.system_prompt is not None:
        prompt.system_prompt = body.system_prompt
    if body.user_template is not None:
        prompt.user_template = body.user_template
    if body.is_active is not None:
        prompt.is_active = body.is_active
    prompt.version += 1
    await db.flush()
    return PromptTemplateResponse.model_validate(prompt)


@router.get("/domain-packs")
async def list_domain_packs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DomainPackVersion).order_by(DomainPackVersion.pack_name))
    return [{"id": str(p.id), "pack_name": p.pack_name, "version": p.version, "is_active": p.is_active} for p in result.scalars().all()]


@router.get("/model-runs")
async def list_model_runs(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_user),
):
    stmt = select(ModelRun).where(ModelRun.tenant_id == ctx.tenant_id).order_by(ModelRun.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "provider": r.provider,
            "model_name": r.model_name,
            "operation": r.operation,
            "latency_ms": r.latency_ms,
            "success": r.success,
            "created_at": str(r.created_at),
        }
        for r in runs
    ]
