"""Admin routes — prompt templates, domain packs, model runs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user, get_db

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Schemas ───────────────────────────────────────────────────────────────


class PromptTemplate(BaseModel):
    id: str
    name: str
    domain_pack: str
    version: int
    template: str
    variables: list[str] = Field(default_factory=list)
    updated_at: str | None = None


class PromptUpdateRequest(BaseModel):
    template: str
    variables: list[str] | None = None


class DomainPackInfo(BaseModel):
    name: str
    version: str
    description: str
    prompts_count: int
    rules_count: int


class ModelRunRecord(BaseModel):
    id: str
    case_id: str | None = None
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    created_at: str | None = None


class ModelRunListResponse(BaseModel):
    items: list[ModelRunRecord]
    total: int
    page: int
    page_size: int


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("/prompts", response_model=list[PromptTemplate])
async def list_prompts(
    domain_pack: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> list[PromptTemplate]:
    """List all prompt templates, optionally filtered by domain pack."""
    if domain_pack:
        result = await db.execute(
            text(
                "SELECT id, name, domain_pack, version, template, variables, updated_at "
                "FROM prompt_templates WHERE domain_pack = :domain_pack ORDER BY name"
            ),
            {"domain_pack": domain_pack},
        )
    else:
        result = await db.execute(
            text(
                "SELECT id, name, domain_pack, version, template, variables, updated_at "
                "FROM prompt_templates ORDER BY domain_pack, name"
            ),
        )
    return [
        PromptTemplate(
            id=r["id"],
            name=r["name"],
            domain_pack=r["domain_pack"],
            version=r["version"],
            template=r["template"],
            variables=r["variables"] if r["variables"] else [],
            updated_at=str(r["updated_at"]) if r.get("updated_at") else None,
        )
        for r in result.mappings().all()
    ]


@router.put("/prompts/{prompt_id}", response_model=PromptTemplate)
async def update_prompt(
    prompt_id: str,
    body: PromptUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> PromptTemplate:
    """Update a prompt template (creates a new version)."""
    result = await db.execute(
        text(
            "SELECT id, name, domain_pack, version, template, variables "
            "FROM prompt_templates WHERE id = :id"
        ),
        {"id": prompt_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prompt template not found"
        )

    new_version = row["version"] + 1
    variables = body.variables if body.variables is not None else row["variables"]

    await db.execute(
        text(
            "UPDATE prompt_templates SET template = :template, variables = :variables, "
            "version = :version, updated_at = NOW() WHERE id = :id"
        ),
        {
            "id": prompt_id,
            "template": body.template,
            "variables": variables,
            "version": new_version,
        },
    )

    return PromptTemplate(
        id=prompt_id,
        name=row["name"],
        domain_pack=row["domain_pack"],
        version=new_version,
        template=body.template,
        variables=variables if variables else [],
    )


@router.get("/domain-packs", response_model=list[DomainPackInfo])
async def list_domain_packs(
    user: dict[str, Any] = Depends(get_current_user),
) -> list[DomainPackInfo]:
    """List available domain packs and their versions."""
    import os

    packs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "domain-packs")
    packs_dir = os.path.normpath(packs_dir)

    packs: list[DomainPackInfo] = []
    if os.path.isdir(packs_dir):
        for entry in sorted(os.listdir(packs_dir)):
            pack_path = os.path.join(packs_dir, entry)
            if not os.path.isdir(pack_path) or entry.startswith("."):
                continue

            # Count prompts and rules
            prompts_dir = os.path.join(pack_path, "prompts")
            rules_dir = os.path.join(pack_path, "rules")
            prompts_count = len(os.listdir(prompts_dir)) if os.path.isdir(prompts_dir) else 0
            rules_count = len(os.listdir(rules_dir)) if os.path.isdir(rules_dir) else 0

            # Read version from manifest if it exists
            manifest_path = os.path.join(pack_path, "manifest.json")
            version = "1.0.0"
            description = f"Domain pack: {entry}"
            if os.path.isfile(manifest_path):
                import json

                with open(manifest_path) as f:
                    manifest = json.load(f)
                    version = manifest.get("version", version)
                    description = manifest.get("description", description)

            packs.append(
                DomainPackInfo(
                    name=entry,
                    version=version,
                    description=description,
                    prompts_count=prompts_count,
                    rules_count=rules_count,
                )
            )

    return packs


@router.get("/model-runs", response_model=ModelRunListResponse)
async def list_model_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    model: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> ModelRunListResponse:
    """List model inference runs with optional filtering."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if model:
        conditions.append("model = :model")
        params["model"] = model

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * page_size

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM model_runs{where_clause}"),
        params,
    )
    total = count_result.scalar() or 0

    params["limit"] = page_size
    params["offset"] = offset
    result = await db.execute(
        text(
            f"SELECT id, case_id, model, prompt_tokens, completion_tokens, latency_ms, created_at "
            f"FROM model_runs{where_clause} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    )

    items = [
        ModelRunRecord(
            id=r["id"],
            case_id=r["case_id"],
            model=r["model"],
            prompt_tokens=r["prompt_tokens"],
            completion_tokens=r["completion_tokens"],
            latency_ms=r["latency_ms"],
            created_at=str(r["created_at"]) if r.get("created_at") else None,
        )
        for r in result.mappings().all()
    ]

    return ModelRunListResponse(items=items, total=total, page=page, page_size=page_size)
