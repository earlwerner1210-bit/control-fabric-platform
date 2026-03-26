"""Pilot case management schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PilotCaseState(str, enum.Enum):
    CREATED = "created"
    EVIDENCE_READY = "evidence_ready"
    WORKFLOW_EXECUTED = "workflow_executed"
    VALIDATION_COMPLETED = "validation_completed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    OVERRIDDEN = "overridden"
    ESCALATED = "escalated"
    EXPORTED = "exported"
    CLOSED = "closed"


class CaseSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BusinessImpact(str, enum.Enum):
    NEGLIGIBLE = "negligible"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    SEVERE = "severe"


class PilotCaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    workflow_type: str = Field(..., description="e.g. contract_compile, margin_diagnosis, work_order_readiness, incident_dispatch")
    external_refs: dict[str, str] = Field(default_factory=dict, description="ticket_id, work_order_id, contract_ref, etc.")
    tags: list[str] = Field(default_factory=list)
    category: str | None = None
    severity: CaseSeverity = CaseSeverity.MEDIUM
    business_impact: BusinessImpact = BusinessImpact.MODERATE
    metadata: dict[str, Any] = Field(default_factory=dict)


class PilotCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    description: str | None
    workflow_type: str
    state: PilotCaseState
    external_refs: dict[str, str]
    tags: list[str]
    category: str | None
    severity: CaseSeverity
    business_impact: BusinessImpact
    assigned_reviewer_id: uuid.UUID | None
    workflow_case_id: uuid.UUID | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PilotCaseListResponse(BaseModel):
    items: list[PilotCaseResponse]
    total: int
    page: int
    page_size: int


class PilotCaseArtifactCreate(BaseModel):
    artifact_type: str = Field(..., description="document, chunk, control_object, model_output, validation_result")
    artifact_id: uuid.UUID
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PilotCaseArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    artifact_type: str
    artifact_id: uuid.UUID
    label: str | None
    metadata: dict[str, Any]
    created_at: datetime


class PilotCaseAssignRequest(BaseModel):
    reviewer_id: uuid.UUID
    notes: str | None = None


class PilotCaseAssignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    reviewer_id: uuid.UUID
    assigned_by: uuid.UUID
    notes: str | None
    assigned_at: datetime


class CaseTimelineEntry(BaseModel):
    timestamp: datetime
    event_type: str
    actor_id: uuid.UUID | None
    from_state: str | None
    to_state: str | None
    details: dict[str, Any] = Field(default_factory=dict)


class CaseTimelineResponse(BaseModel):
    pilot_case_id: uuid.UUID
    entries: list[CaseTimelineEntry]


class CaseStateTransitionRequest(BaseModel):
    target_state: PilotCaseState
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaseStateTransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    from_state: PilotCaseState
    to_state: PilotCaseState
    actor_id: uuid.UUID
    reason: str | None
    metadata: dict[str, Any]
    transitioned_at: datetime


class ValidTransitionsResponse(BaseModel):
    current_state: PilotCaseState
    valid_transitions: list[PilotCaseState]
