"""Compile routes — trigger compilation of contracts, work orders, incidents."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db, get_tenant_context

router = APIRouter(tags=["compile"])


# ── Schemas ───────────────────────────────────────────────────────────────


class CompileRequest(BaseModel):
    domain_pack: str = "contract-margin"
    options: dict[str, Any] = Field(default_factory=dict)


class CompileResponse(BaseModel):
    id: str
    object_type: str
    status: str
    control_objects_created: int
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("/contracts/{contract_id}/compile", response_model=CompileResponse)
async def compile_contract(
    contract_id: str,
    body: CompileRequest | None = None,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_context),
) -> CompileResponse:
    """Compile a contract into control objects."""
    result = await db.execute(
        text("SELECT id FROM documents WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": contract_id, "tenant_id": tenant_id},
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contract document not found"
        )

    # Mark as compiling
    await db.execute(
        text("UPDATE documents SET status = :status WHERE id = :id"),
        {"status": "compiling", "id": contract_id},
    )

    return CompileResponse(
        id=contract_id,
        object_type="contract",
        status="compiling",
        control_objects_created=0,
        message="Contract compilation initiated",
    )


@router.post("/work-orders/{work_order_id}/compile", response_model=CompileResponse)
async def compile_work_order(
    work_order_id: str,
    body: CompileRequest | None = None,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_context),
) -> CompileResponse:
    """Compile a work order into control objects."""
    result = await db.execute(
        text("SELECT id FROM documents WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": work_order_id, "tenant_id": tenant_id},
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Work order document not found"
        )

    await db.execute(
        text("UPDATE documents SET status = :status WHERE id = :id"),
        {"status": "compiling", "id": work_order_id},
    )

    return CompileResponse(
        id=work_order_id,
        object_type="work_order",
        status="compiling",
        control_objects_created=0,
        message="Work order compilation initiated",
    )


@router.post("/incidents/{incident_id}/compile", response_model=CompileResponse)
async def compile_incident(
    incident_id: str,
    body: CompileRequest | None = None,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_context),
) -> CompileResponse:
    """Compile an incident into control objects."""
    result = await db.execute(
        text("SELECT id FROM documents WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": incident_id, "tenant_id": tenant_id},
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Incident document not found"
        )

    await db.execute(
        text("UPDATE documents SET status = :status WHERE id = :id"),
        {"status": "compiling", "id": incident_id},
    )

    return CompileResponse(
        id=incident_id,
        object_type="incident",
        status="compiling",
        control_objects_created=0,
        message="Incident compilation initiated",
    )
