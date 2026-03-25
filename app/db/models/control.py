"""ControlObject and ControlLink models."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, TenantMixin, UUIDPrimaryKeyMixin


class ControlObjectType(str, enum.Enum):
    obligation = "obligation"
    billable_event = "billable_event"
    penalty_condition = "penalty_condition"
    dispatch_precondition = "dispatch_precondition"
    skill_requirement = "skill_requirement"
    incident_state = "incident_state"
    escalation_rule = "escalation_rule"
    service_state = "service_state"
    readiness_check = "readiness_check"
    leakage_trigger = "leakage_trigger"


class ControlObject(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "control_objects"

    control_type: Mapped[ControlObjectType] = mapped_column(
        Enum(ControlObjectType, name="control_object_type", create_constraint=True),
        nullable=False,
        index=True,
    )
    domain: Mapped[str] = mapped_column(String(63), nullable=False, index=True)  # contract_margin, utilities_field, telco_ops
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_clause_ref: Mapped[str | None] = mapped_column(String(63), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    workflow_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)


class ControlLink(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "control_links"

    source_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("control_objects.id"), nullable=False, index=True
    )
    target_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("control_objects.id"), nullable=False, index=True
    )
    link_type: Mapped[str] = mapped_column(String(63), nullable=False)  # e.g. "requires", "conflicts_with", "derived_from"
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
