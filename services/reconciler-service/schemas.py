"""Reconciler service request/response schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema


class ReconcileRequest(BaseModel):
    case_id: uuid.UUID
    object_ids: list[uuid.UUID] = Field(..., min_length=1)


class Contradiction(BaseSchema):
    object_a_id: uuid.UUID
    object_b_id: uuid.UUID
    field: str
    value_a: str
    value_b: str
    severity: str = "warning"


class LeakageItem(BaseSchema):
    object_id: uuid.UUID
    description: str
    estimated_amount: float | None = None


class Recommendation(BaseSchema):
    action: str
    reason: str
    priority: str = "medium"


class ReconcileResponse(BaseSchema):
    case_id: uuid.UUID
    objects_reconciled: int
    contradictions: list[Contradiction] = Field(default_factory=list)
    leakage_items: list[LeakageItem] = Field(default_factory=list)
    missing_prerequisites: list[str] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    status: str = "completed"
