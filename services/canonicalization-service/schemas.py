"""Canonicalization service request/response schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema


class ResolveEntityRequest(BaseModel):
    name: str
    entity_type: str
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class RegisterEntityRequest(BaseModel):
    canonical_name: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MergeEntitiesRequest(BaseModel):
    source_id: uuid.UUID
    target_id: uuid.UUID


class EntityResponse(BaseSchema):
    id: uuid.UUID
    canonical_name: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tenant_id: uuid.UUID


class ResolveEntityResponse(BaseSchema):
    resolved: bool
    entity: EntityResponse | None = None
    similarity: float = 0.0
    candidates: list[EntityResponse] = Field(default_factory=list)
