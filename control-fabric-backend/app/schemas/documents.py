"""Document ingestion, parsing, and embedding schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class DocumentUploadResponse(BaseSchema):
    """Returned immediately after a document is uploaded."""

    id: UUID
    filename: str
    content_type: str = Field(
        ...,
        examples=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
    )
    file_size_bytes: int = Field(..., ge=0)
    checksum_sha256: str = Field(..., min_length=64, max_length=64)
    status: str = Field(default="uploaded", examples=["uploaded", "parsing", "parsed", "failed"])
    created_at: datetime


class ParseRequest(BaseSchema):
    """Optional hints sent when requesting document parsing."""

    domain: str | None = Field(
        default=None,
        description="Domain pack to use for parsing (e.g. 'contract-margin', 'telco-ops')",
    )


class ParseResponse(BaseSchema):
    """Result of parsing a document."""

    document_id: UUID
    document_type: str = Field(
        ..., examples=["contract", "sla", "rate_card", "work_order", "incident_report"]
    )
    status: str = Field(..., examples=["parsed", "failed"])
    parsed_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured output extracted from the document",
    )
    chunk_count: int = Field(..., ge=0, description="Number of text chunks produced")


class EmbedRequest(BaseSchema):
    """Optional overrides for the embedding step."""

    model: str | None = Field(
        default=None,
        description="Embedding model override (defaults to configured model)",
    )


class EmbedResponse(BaseSchema):
    """Result of embedding a document's chunks."""

    document_id: UUID
    chunks_embedded: int = Field(..., ge=0)
    model_used: str


class DocumentResponse(BaseSchema):
    """Full document representation for list / detail endpoints."""

    id: UUID
    tenant_id: UUID
    title: str | None = None
    filename: str
    content_type: str
    status: str = Field(..., examples=["uploaded", "parsing", "parsed", "embedded", "failed"])
    document_type: str | None = Field(
        default=None,
        examples=["contract", "sla", "rate_card", "work_order", "incident_report"],
    )
    created_at: datetime
    updated_at: datetime
