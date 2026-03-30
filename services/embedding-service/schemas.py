"""Embedding service request/response schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema


class EmbeddingRequest(BaseModel):
    chunk_id: uuid.UUID
    text: str
    model: str | None = None


class EmbeddingBatchRequest(BaseModel):
    items: list[EmbeddingRequest]
    model: str | None = None


class EmbeddingResponse(BaseSchema):
    chunk_id: uuid.UUID
    model: str
    dimension: int
    vector: list[float] = Field(default_factory=list)


class EmbeddingBatchResponse(BaseSchema):
    model: str
    count: int
    embeddings: list[EmbeddingResponse]
