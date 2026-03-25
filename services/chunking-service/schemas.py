"""Chunking service request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChunkCreateRequest(BaseModel):
    document_id: str
    chunk_size: int = Field(default=512, ge=64, le=4096, description="Target chunk size in tokens")
    overlap: int = Field(default=64, ge=0, le=512, description="Overlap between chunks in tokens")


class ChunkResponse(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    text: str
    token_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkCreateResponse(BaseModel):
    document_id: str
    chunks_created: int
    chunks: list[ChunkResponse]
