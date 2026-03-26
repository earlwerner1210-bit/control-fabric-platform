"""Pilot case and related database models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class PilotCase(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "pilot_cases"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_type: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    external_refs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    business_impact: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    assigned_reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    workflow_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_pilot_cases_tenant_state", "tenant_id", "state"),
        Index("ix_pilot_cases_workflow_type", "workflow_type"),
        Index("ix_pilot_cases_reviewer", "assigned_reviewer_id"),
        Index("ix_pilot_cases_created", "created_at"),
    )


class PilotCaseArtifact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pilot_case_artifacts"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_pilot_case_artifacts_case", "pilot_case_id"),
    )


class PilotCaseAssignment(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "pilot_case_assignments"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assigned_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_pilot_case_assignments_case", "pilot_case_id"),
        Index("ix_pilot_case_assignments_reviewer", "reviewer_id"),
    )


class CaseStateTransition(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "case_state_transitions"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False)
    from_state: Mapped[str] = mapped_column(String(50), nullable=False)
    to_state: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    transitioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_case_state_transitions_case", "pilot_case_id"),
        Index("ix_case_state_transitions_time", "transitioned_at"),
    )


class ReviewDecision(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "review_decisions"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    business_impact_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_commentary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_review_decisions_case", "pilot_case_id"),
        Index("ix_review_decisions_reviewer", "reviewer_id"),
    )


class ReviewerNote(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "reviewer_notes"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    note_type: Mapped[str] = mapped_column(String(30), nullable=False, default="general")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    references: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_reviewer_notes_case", "pilot_case_id"),
    )


class ApprovalDecision(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "approval_decisions"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False)
    approved_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    business_impact_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_approval_decisions_case", "pilot_case_id"),
    )


class OverrideDecision(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "override_decisions"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False)
    overridden_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    override_reason: Mapped[str] = mapped_column(String(60), nullable=False)
    override_detail: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_outcome: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    business_impact_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_override_decisions_case", "pilot_case_id"),
    )


class EvidenceBundle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evidence_bundles"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False)
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    chain_stages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    completeness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_evidence_bundles_case", "pilot_case_id"),
    )


class BaselineComparison(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "baseline_comparisons"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False)
    expected_outcome: Mapped[str] = mapped_column(String(200), nullable=False)
    expected_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    expected_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    platform_outcome: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewer_outcome: Mapped[str | None] = mapped_column(String(200), nullable=True)
    match_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_baseline_comparisons_case", "pilot_case_id"),
        Index("ix_baseline_comparisons_match_type", "match_type"),
    )


class KpiMeasurement(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "kpi_measurements"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dimension: Mapped[str | None] = mapped_column(String(50), nullable=True)
    dimension_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_kpi_measurements_case", "pilot_case_id"),
        Index("ix_kpi_measurements_metric", "metric_name"),
    )


class FeedbackEntry(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "feedback_entries"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_component: Mapped[str | None] = mapped_column(String(50), nullable=True)
    suggested_improvement: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_feedback_entries_case", "pilot_case_id"),
        Index("ix_feedback_entries_category", "category"),
    )


class CaseExport(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "case_exports"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="json")
    exported_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_case_exports_case", "pilot_case_id"),
    )
