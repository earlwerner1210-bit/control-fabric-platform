"""Approval, override, and escalation schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OverrideReason(str, enum.Enum):
    EVIDENCE_INCOMPLETE = "evidence_incomplete"
    BUSINESS_CONTEXT_MISSING = "business_context_missing"
    MODEL_ACCEPTABLE_COMMERCIAL_DIFFERS = "model_acceptable_commercial_differs"
    RULE_ENGINE_NEEDS_REFINEMENT = "rule_engine_needs_refinement"
    FIELD_EVIDENCE_NOT_RECONCILED = "field_evidence_not_reconciled"
    SERVICE_STATE_CHANGED = "service_state_changed"
    OTHER = "other"


class EscalationRoute(str, enum.Enum):
    COMMERCIAL_LEAD = "commercial_lead"
    FIELD_OPS_LEAD = "field_ops_lead"
    SERVICE_DELIVERY_LEAD = "service_delivery_lead"
    GOVERNANCE_BOARD = "governance_board"
    DOMAIN_EXPERT = "domain_expert"
    SENIOR_MANAGEMENT = "senior_management"


class ApprovalRequest(BaseModel):
    reasoning: str = Field(..., min_length=1)
    business_impact_notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OverrideRequest(BaseModel):
    override_reason: OverrideReason
    override_detail: str = Field(..., min_length=1)
    corrected_outcome: dict[str, Any] = Field(default_factory=dict, description="The corrected decision payload")
    business_impact_notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EscalationRequest(BaseModel):
    escalation_route: EscalationRoute
    escalation_reason: str = Field(..., min_length=1)
    urgency: str = Field(default="normal", description="low, normal, high, urgent")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    approved_by: uuid.UUID
    reasoning: str
    business_impact_notes: str | None
    metadata: dict[str, Any]
    created_at: datetime


class OverrideResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    overridden_by: uuid.UUID
    override_reason: OverrideReason
    override_detail: str
    corrected_outcome: dict[str, Any]
    business_impact_notes: str | None
    metadata: dict[str, Any]
    created_at: datetime


class EscalationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    escalated_by: uuid.UUID
    escalation_route: EscalationRoute
    escalation_reason: str
    urgency: str
    metadata: dict[str, Any]
    created_at: datetime
