"""Extended database models for evidence traces, baselines, and reporting."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EvidenceReference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evidence_references"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False
    )
    evidence_bundle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_bundles.id"), nullable=False
    )
    object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_evidence_references_bundle", "evidence_bundle_id"),
        Index("ix_evidence_references_case", "pilot_case_id"),
        Index("ix_evidence_references_object", "object_type", "object_id"),
    )


class ValidationTraceRecord(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "validation_trace_records"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False
    )
    workflow_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    validators_run: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    passed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    failed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    overall_status: Mapped[str] = mapped_column(String(30), nullable=False)
    rule_count: Mapped[int] = mapped_column(nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(nullable=False, default=0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("ix_validation_trace_records_case", "pilot_case_id"),
        Index("ix_validation_trace_records_status", "overall_status"),
    )


class ModelLineageRecord(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "model_lineage_records"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False
    )
    workflow_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    prompt_template_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inference_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_output_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("ix_model_lineage_records_case", "pilot_case_id"),
        Index("ix_model_lineage_records_model", "model_id"),
    )


class BaselineExpectationRecord(Base, UUIDPrimaryKeyMixin, TenantMixin):
    __tablename__ = "baseline_expectations"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pilot_cases.id"), nullable=False
    )
    expected_outcome: Mapped[str] = mapped_column(String(200), nullable=False)
    expected_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    expected_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expected_billability: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expected_next_action: Mapped[str | None] = mapped_column(String(200), nullable=True)
    expected_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expected_escalation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expected_recovery_action: Mapped[str | None] = mapped_column(String(200), nullable=True)
    expected_evidence_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("ix_baseline_expectations_case", "pilot_case_id"),
        Index("ix_baseline_expectations_tenant", "tenant_id"),
    )


class PilotReportSnapshot(Base, UUIDPrimaryKeyMixin, TenantMixin):
    __tablename__ = "pilot_report_snapshots"

    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    total_cases: Mapped[int] = mapped_column(nullable=False, default=0)
    cases_by_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    cases_by_workflow: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    kpi_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    baseline_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    feedback_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("ix_pilot_report_snapshots_type", "report_type"),
        Index("ix_pilot_report_snapshots_tenant", "tenant_id"),
        Index("ix_pilot_report_snapshots_created", "created_at"),
    )
