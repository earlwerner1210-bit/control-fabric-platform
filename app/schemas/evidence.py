"""Evidence review and traceability schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    evidence_type: str = Field(..., description="document, chunk, control_object, rule_result, validation_result, model_output")
    source_id: uuid.UUID
    source_label: str | None = None
    content_summary: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundleCreate(BaseModel):
    pilot_case_id: uuid.UUID
    items: list[EvidenceItem] = Field(default_factory=list)
    chain_stages: list[str] = Field(default_factory=list, description="e.g. contract_basis, work_authorization, execution_evidence, billing_evidence")
    completeness_score: float = Field(ge=0.0, le=1.0, default=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    items: list[EvidenceItem]
    chain_stages: list[str]
    completeness_score: float
    metadata: dict[str, Any]
    created_at: datetime


class EvidenceObjectReference(BaseModel):
    object_type: str
    object_id: uuid.UUID
    label: str | None = None
    role: str | None = None


class EvidenceTrace(BaseModel):
    pilot_case_id: uuid.UUID
    documents_used: list[EvidenceObjectReference]
    chunks_used: list[EvidenceObjectReference]
    control_objects: list[EvidenceObjectReference]
    rules_fired: list[dict[str, Any]]
    cross_plane_conflicts: list[dict[str, Any]]


class ValidationTrace(BaseModel):
    pilot_case_id: uuid.UUID
    validators_run: list[dict[str, Any]]
    passed: list[str]
    failed: list[str]
    warnings: list[str]
    overall_status: str


class ModelLineageTrace(BaseModel):
    pilot_case_id: uuid.UUID
    model_id: str | None = None
    model_version: str | None = None
    prompt_template_id: uuid.UUID | None = None
    prompt_template_version: str | None = None
    inference_provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float | None = None
    raw_output_summary: dict[str, Any] = Field(default_factory=dict)
