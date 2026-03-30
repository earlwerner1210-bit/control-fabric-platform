"""Chunking service request/response schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema


class ChunkCreateRequest(BaseModel):
    document_id: uuid.UUID
    chunk_size: int = Field(default=512, ge=64, le=4096, description="Target chunk size in tokens")
    overlap: int = Field(default=64, ge=0, le=512, description="Overlap between chunks in tokens")


class ChunkResponse(BaseSchema):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    text: str
    token_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkCreateResponse(BaseSchema):
    document_id: uuid.UUID
    chunks_created: int
    chunks: list[ChunkResponse]
