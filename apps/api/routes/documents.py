"""Document routes — upload, parse, embed, get, list."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user, get_db, get_tenant_context

router = APIRouter(prefix="/documents", tags=["documents"])


# ── Schemas ───────────────────────────────────────────────────────────────


class DocumentResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    document_type: str | None = None
    status: str
    tenant_id: str
    created_at: str | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class ParseResponse(BaseModel):
    document_id: str
    status: str
    message: str


class EmbedResponse(BaseModel):
    document_id: str
    status: str
    chunks_embedded: int


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str | None = Query(None, description="Optional document type hint"),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_context),
) -> DocumentResponse:
    """Upload a document and store its metadata."""
    content = await file.read()
    doc_id = str(uuid.uuid4())

    await db.execute(
        text(
            "INSERT INTO documents (id, filename, content_type, size_bytes, document_type, status, tenant_id, storage_path) "
            "VALUES (:id, :filename, :content_type, :size_bytes, :document_type, :status, :tenant_id, :storage_path)"
        ),
        {
            "id": doc_id,
            "filename": file.filename or "unnamed",
            "content_type": file.content_type or "application/octet-stream",
            "size_bytes": len(content),
            "document_type": document_type,
            "status": "uploaded",
            "tenant_id": tenant_id,
            "storage_path": f"documents/{tenant_id}/{doc_id}",
        },
    )

    return DocumentResponse(
        id=doc_id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        document_type=document_type,
        status="uploaded",
        tenant_id=tenant_id,
    )


@router.post("/{document_id}/parse", response_model=ParseResponse)
async def parse_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> ParseResponse:
    """Trigger document parsing via the ingest service."""
    result = await db.execute(
        text("SELECT id, status FROM documents WHERE id = :id"),
        {"id": document_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Update status to parsing
    await db.execute(
        text("UPDATE documents SET status = :status WHERE id = :id"),
        {"status": "parsing", "id": document_id},
    )

    return ParseResponse(
        document_id=document_id,
        status="parsing",
        message="Document parsing initiated",
    )


@router.post("/{document_id}/embed", response_model=EmbedResponse)
async def embed_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmbedResponse:
    """Trigger embedding generation for a parsed document."""
    result = await db.execute(
        text("SELECT id, status FROM documents WHERE id = :id"),
        {"id": document_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if row["status"] not in ("parsed", "embedded"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document must be parsed before embedding (current status: {row['status']})",
        )

    await db.execute(
        text("UPDATE documents SET status = :status WHERE id = :id"),
        {"status": "embedding", "id": document_id},
    )

    return EmbedResponse(
        document_id=document_id,
        status="embedding",
        chunks_embedded=0,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> DocumentResponse:
    """Retrieve a single document by ID."""
    result = await db.execute(
        text(
            "SELECT id, filename, content_type, size_bytes, document_type, status, tenant_id, created_at "
            "FROM documents WHERE id = :id"
        ),
        {"id": document_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse(
        id=row["id"],
        filename=row["filename"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        document_type=row["document_type"],
        status=row["status"],
        tenant_id=row["tenant_id"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_context),
) -> DocumentListResponse:
    """List documents for the current tenant, paginated."""
    offset = (page - 1) * page_size

    count_result = await db.execute(
        text("SELECT COUNT(*) FROM documents WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        text(
            "SELECT id, filename, content_type, size_bytes, document_type, status, tenant_id, created_at "
            "FROM documents WHERE tenant_id = :tenant_id "
            "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ),
        {"tenant_id": tenant_id, "limit": page_size, "offset": offset},
    )

    items = [
        DocumentResponse(
            id=r["id"],
            filename=r["filename"],
            content_type=r["content_type"],
            size_bytes=r["size_bytes"],
            document_type=r["document_type"],
            status=r["status"],
            tenant_id=r["tenant_id"],
            created_at=str(r["created_at"]) if r["created_at"] else None,
        )
        for r in result.mappings().all()
    ]

    return DocumentListResponse(items=items, total=total, page=page, page_size=page_size)
