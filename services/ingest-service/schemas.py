"""Ingest service request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    checksum: str
    status: str


class ParseRequest(BaseModel):
    domain: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class ParseResponse(BaseModel):
    document_id: str
    status: str
    document_type: str | None = None
    parsed_content: dict[str, Any] | None = None


class DocumentResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    checksum: str
    status: str
    document_type: str | None = None
    storage_path: str
    tenant_id: str
    created_at: str
