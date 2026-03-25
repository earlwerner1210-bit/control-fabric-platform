"""Document-related request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema


class DocumentUploadResponse(BaseSchema):
    id: uuid.UUID
    filename: str
    content_type: str | None = None
    file_size_bytes: int | None = None
    checksum_sha256: str | None = None
    status: str
    created_at: datetime


class DocumentResponse(BaseSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    filename: str
    content_type: str | None = None
    document_type: str | None = None
    file_size_bytes: int | None = None
    checksum_sha256: str | None = None
    status: str
    parsed_payload: dict | None = None
    created_at: datetime
    updated_at: datetime


class DocumentChunkResponse(BaseSchema):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    start_offset: int | None = None
    end_offset: int | None = None
    metadata: dict | None = Field(None, alias="metadata_")


class ParseRequest(BaseSchema):
    domain: str = "auto"  # auto, contract_margin, utilities_field, telco_ops
    options: dict | None = None


class ParseResponse(BaseSchema):
    document_id: uuid.UUID
    document_type: str | None = None
    status: str
    parsed_payload: dict | None = None
    chunk_count: int = 0


class EmbedRequest(BaseSchema):
    model: str | None = None
    force: bool = False


class EmbedResponse(BaseSchema):
    document_id: uuid.UUID
    chunks_embedded: int
    model_used: str
