"""Control Fabric schemas — strongly-typed control object fabric layer."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ControlPlane(str, enum.Enum):
    COMMERCIAL = "commercial"
    FIELD = "field"
    SERVICE = "service"
    GOVERNANCE = "governance"


class ControlLinkType(str, enum.Enum):
    DEPENDS_ON = "depends_on"
    SATISFIES = "satisfies"
    CONTRADICTS = "contradicts"
    TRIGGERS = "triggers"
    BLOCKS = "blocks"
    AUTHORIZES = "authorizes"
    INVALIDATES = "invalidates"
    REFERENCES = "references"


class ControlObjectStatus(str, enum.Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETIRED = "retired"
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"


class FabricObjectCreate(BaseModel):
    control_type: str
    plane: ControlPlane
    domain: str
    label: str
    description: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    source_document_id: uuid.UUID | None = None
    source_chunk_id: uuid.UUID | None = None
    source_clause_ref: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FabricObjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    control_type: str
    plane: ControlPlane
    domain: str
    label: str
    description: str | None
    payload: dict[str, Any]
    source_document_id: uuid.UUID | None
    source_chunk_id: uuid.UUID | None
    source_clause_ref: str | None
    confidence: float
    status: ControlObjectStatus
    tags: list[str]
    metadata: dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime


class FabricLinkCreate(BaseModel):
    source_id: uuid.UUID
    target_id: uuid.UUID
    link_type: ControlLinkType
    weight: float = Field(ge=0.0, le=1.0, default=1.0)
    evidence_refs: list[uuid.UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FabricLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    link_type: ControlLinkType
    weight: float
    evidence_refs: list[uuid.UUID]
    metadata: dict[str, Any]
    created_at: datetime


class FabricSliceRequest(BaseModel):
    root_ids: list[uuid.UUID] = Field(default_factory=list)
    planes: list[ControlPlane] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    link_types: list[ControlLinkType] = Field(default_factory=list)
    max_depth: int = Field(ge=1, le=10, default=3)
    include_retired: bool = False


class FabricSliceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    objects: list[FabricObjectResponse]
    links: list[FabricLinkResponse]
    root_ids: list[uuid.UUID]
    total_objects: int
    total_links: int
    depth_reached: int


class FabricQueryFilter(BaseModel):
    planes: list[ControlPlane] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    control_types: list[str] = Field(default_factory=list)
    statuses: list[ControlObjectStatus] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    min_confidence: float = 0.0
    source_document_id: uuid.UUID | None = None
    page: int = 1
    page_size: int = 50


class FabricStats(BaseModel):
    total_objects: int = 0
    total_links: int = 0
    objects_by_plane: dict[str, int] = Field(default_factory=dict)
    objects_by_domain: dict[str, int] = Field(default_factory=dict)
    objects_by_type: dict[str, int] = Field(default_factory=dict)
    links_by_type: dict[str, int] = Field(default_factory=dict)
