"""Ingest service request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema


class ParseRequest(BaseModel):
    domain: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class UploadResponse(BaseSchema):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    checksum: str
    status: str


class ParseResponse(BaseSchema):
    document_id: uuid.UUID
    status: str
    document_type: str | None = None
    parsed_content: dict[str, Any] | None = None


class DocumentListItem(BaseSchema):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    checksum: str
    status: str
    document_type: str | None = None
    s3_key: str
    tenant_id: uuid.UUID
    created_at: datetime
