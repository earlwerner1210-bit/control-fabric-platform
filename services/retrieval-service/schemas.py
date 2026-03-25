"""Retrieval service request/response schemas."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema


class RetrievalMode(str, Enum):
    keyword = "keyword"
    vector = "vector"
    hybrid = "hybrid"


class RetrievalRequest(BaseModel):
    query: str
    filters: dict[str, Any] = Field(default_factory=dict)
    top_k: int = Field(default=10, ge=1, le=100)
    mode: RetrievalMode = RetrievalMode.hybrid


class Citation(BaseSchema):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    text_snippet: str
    score: float


class RetrievalResponse(BaseSchema):
    query: str
    mode: str
    total_results: int
    results: list[Citation]
