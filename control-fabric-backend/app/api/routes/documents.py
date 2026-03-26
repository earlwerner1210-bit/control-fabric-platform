"""Document management endpoints -- upload, parse, embed, list, and retrieve."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, UploadFile

from app.api.deps.auth import get_current_user
from app.core.security import TenantContext
from app.core.telemetry import metrics
from app.schemas.common import PaginatedResponse
from app.schemas.documents import (
    DocumentResponse,
    DocumentUploadResponse,
    EmbedResponse,
    ParseResponse,
)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


# ---------------------------------------------------------------------------
# In-memory stub store (replaced by real DB in production)
# ---------------------------------------------------------------------------

_DOCUMENTS: dict[str, dict[str, Any]] = {}


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    ctx: TenantContext = Depends(get_current_user),
) -> DocumentUploadResponse:
    """Upload a document and store metadata."""
    content = await file.read()
    doc_id = str(uuid.uuid4())
    checksum = hashlib.sha256(content).hexdigest()
    now = datetime.now(UTC)

    doc = {
        "id": doc_id,
        "tenant_id": ctx.tenant_id,
        "filename": file.filename or "unnamed",
        "content_type": file.content_type or "application/octet-stream",
        "file_size_bytes": len(content),
        "checksum_sha256": checksum,
        "status": "uploaded",
        "document_type": None,
        "title": None,
        "created_at": now,
        "updated_at": now,
    }
    _DOCUMENTS[doc_id] = doc
    metrics.increment("documents.uploaded")

    return DocumentUploadResponse(
        id=uuid.UUID(doc_id),
        filename=doc["filename"],
        content_type=doc["content_type"],
        file_size_bytes=doc["file_size_bytes"],
        checksum_sha256=checksum,
        status="uploaded",
        created_at=now,
    )


@router.post("/{document_id}/parse", response_model=ParseResponse)
async def parse_document(
    document_id: str,
    ctx: TenantContext = Depends(get_current_user),
) -> ParseResponse:
    """Trigger parsing of an uploaded document."""
    doc = _DOCUMENTS.get(document_id)
    if doc is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError(detail=f"Document {document_id} not found")

    doc["status"] = "parsed"
    doc["document_type"] = "contract"
    doc["updated_at"] = datetime.now(UTC)
    metrics.increment("documents.parsed")

    return ParseResponse(
        document_id=uuid.UUID(document_id),
        document_type="contract",
        status="parsed",
        parsed_payload={"sections": [], "clauses": []},
        chunk_count=0,
    )


@router.post("/{document_id}/embed", response_model=EmbedResponse)
async def embed_document(
    document_id: str,
    ctx: TenantContext = Depends(get_current_user),
) -> EmbedResponse:
    """Generate and store vector embeddings for a parsed document."""
    doc = _DOCUMENTS.get(document_id)
    if doc is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError(detail=f"Document {document_id} not found")

    doc["status"] = "embedded"
    doc["updated_at"] = datetime.now(UTC)
    metrics.increment("documents.embedded")

    return EmbedResponse(
        document_id=uuid.UUID(document_id),
        chunks_embedded=0,
        model_used="text-embedding-3-small",
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    ctx: TenantContext = Depends(get_current_user),
) -> DocumentResponse:
    """Retrieve a single document by ID."""
    doc = _DOCUMENTS.get(document_id)
    if doc is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError(detail=f"Document {document_id} not found")

    return DocumentResponse(
        id=uuid.UUID(doc["id"]),
        tenant_id=uuid.UUID(doc["tenant_id"])
        if isinstance(doc["tenant_id"], str)
        else doc["tenant_id"],
        title=doc.get("title"),
        filename=doc["filename"],
        content_type=doc["content_type"],
        status=doc["status"],
        document_type=doc.get("document_type"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@router.get("", response_model=PaginatedResponse[DocumentResponse])
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ctx: TenantContext = Depends(get_current_user),
) -> PaginatedResponse[DocumentResponse]:
    """List documents for the current tenant with pagination."""
    tenant_docs = [d for d in _DOCUMENTS.values() if str(d.get("tenant_id")) == str(ctx.tenant_id)]
    total = len(tenant_docs)

    start = (page - 1) * page_size
    end = start + page_size
    page_items = tenant_docs[start:end]

    items = [
        DocumentResponse(
            id=uuid.UUID(d["id"]),
            tenant_id=uuid.UUID(d["tenant_id"])
            if isinstance(d["tenant_id"], str)
            else d["tenant_id"],
            title=d.get("title"),
            filename=d["filename"],
            content_type=d["content_type"],
            status=d["status"],
            document_type=d.get("document_type"),
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )
        for d in page_items
    ]

    return PaginatedResponse[DocumentResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
