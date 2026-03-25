"""Document-related Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shared.schemas.common import BaseSchema


class DocumentUploadRequest(BaseSchema):
    """Metadata sent alongside a document upload."""

    filename: str
    content_type: str = "application/pdf"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentResponse(BaseSchema):
    """Returned after a document is persisted."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    filename: str
    content_type: str
    s3_key: str
    size_bytes: int
    checksum: str
    page_count: int | None = None
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DocumentChunkResponse(BaseSchema):
    """A single chunk of a document."""

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int
    page_number: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
