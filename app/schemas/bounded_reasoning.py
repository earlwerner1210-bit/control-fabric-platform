"""Bounded Reasoning schemas — graph-slice-isolated inference contexts."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.control_fabric import ControlPlane
from app.schemas.control_graph import GraphSlicePolicy


class ReasoningScope(str, enum.Enum):
    CASE_BOUNDED = "case_bounded"
    PLANE_BOUNDED = "plane_bounded"
    DOMAIN_BOUNDED = "domain_bounded"
    FULL_GRAPH = "full_graph"


class ReasoningStatus(str, enum.Enum):
    PENDING = "pending"
    CONTEXT_BUILT = "context_built"
    INFERENCE_RUNNING = "inference_running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class BoundedContextRequest(BaseModel):
    pilot_case_id: uuid.UUID | None = None
    root_object_ids: list[uuid.UUID] = Field(default_factory=list)
    scope: ReasoningScope = ReasoningScope.CASE_BOUNDED
    allowed_planes: list[ControlPlane] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    max_depth: int = Field(ge=1, le=10, default=3)
    slice_policy: GraphSlicePolicy = GraphSlicePolicy.BFS
    max_context_objects: int = Field(ge=1, le=200, default=50)
    include_evidence: bool = True
    prompt_template: str | None = None
    inference_params: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BoundedContextObject(BaseModel):
    object_id: uuid.UUID
    control_type: str
    plane: str
    domain: str
    label: str
    confidence: float
    payload: dict[str, Any] = Field(default_factory=dict)
    depth: int = 0


class BoundedContextEvidence(BaseModel):
    evidence_type: str
    source_id: uuid.UUID
    source_label: str | None = None
    confidence: float | None = None


class BoundedContext(BaseModel):
    context_id: uuid.UUID
    objects: list[BoundedContextObject]
    evidence: list[BoundedContextEvidence]
    total_objects: int
    total_evidence: int
    scope: ReasoningScope
    depth_reached: int
    planes_included: list[str]
    domains_included: list[str]


class BoundedReasoningRequest(BaseModel):
    context: BoundedContextRequest
    question: str
    output_format: str = "structured"
    max_tokens: int = 2000
    temperature: float = 0.0
    model_id: str | None = None


class BoundedReasoningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID | None
    status: ReasoningStatus
    scope: ReasoningScope
    context: BoundedContext | None
    question: str
    answer: str | None
    confidence: float | None
    reasoning_trace: list[str] = Field(default_factory=list)
    objects_consulted: int
    evidence_consulted: int
    model_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    duration_ms: float | None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ReasoningSummary(BaseModel):
    total_sessions: int = 0
    completed: int = 0
    failed: int = 0
    avg_objects_consulted: float = 0.0
    avg_confidence: float = 0.0
    avg_duration_ms: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
