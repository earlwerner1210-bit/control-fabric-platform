"""
SQLAlchemy ORM models for all platform data — production persistence layer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(UTC)


class TenantMixin:
    """Adds tenant_id to all models for multi-tenancy."""

    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="default", index=True
    )


class ControlObjectDB(TenantMixin, Base):
    __tablename__ = "control_objects_v2"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    schema_namespace: Mapped[str] = mapped_column(String(64), default="core")
    operational_plane: Mapped[str] = mapped_column(String(64), index=True)
    object_hash: Mapped[str] = mapped_column(String(64))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    source_system: Mapped[str] = mapped_column(String(128), default="")
    source_hash: Mapped[str] = mapped_column(String(64), default="")
    ingested_by: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (Index("ix_objects_v2_tenant_plane", "tenant_id", "operational_plane"),)


class ControlEdgeDB(TenantMixin, Base):
    __tablename__ = "control_edges_v2"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    source_object_id: Mapped[str] = mapped_column(String(64), index=True)
    target_object_id: Mapped[str] = mapped_column(String(64), index=True)
    relationship_type: Mapped[str] = mapped_column(String(64), index=True)
    enforcement_weight: Mapped[float] = mapped_column(Float, default=1.0)
    asserted_by: Mapped[str] = mapped_column(String(128))
    evidence_references: Mapped[list] = mapped_column(JSON, default=list)
    edge_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ReconciliationCaseDB(TenantMixin, Base):
    __tablename__ = "reconciliation_cases_v2"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    case_type: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    affected_object_ids: Mapped[list] = mapped_column(JSON, default=list)
    affected_planes: Mapped[list] = mapped_column(JSON, default=list)
    violated_rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remediation_suggestions: Mapped[list] = mapped_column(JSON, default=list)
    severity_score: Mapped[float] = mapped_column(Float, default=0.0)
    case_hash: Mapped[str] = mapped_column(String(64))
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class EvidencePackageDB(TenantMixin, Base):
    __tablename__ = "evidence_packages_v2"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    action_type: Mapped[str] = mapped_column(String(64), index=True)
    action_manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    validation_certificate_hash: Mapped[str] = mapped_column(String(64))
    evidence_chain: Mapped[list] = mapped_column(JSON, default=list)
    provenance_trail: Mapped[list] = mapped_column(JSON, default=list)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_by: Mapped[str] = mapped_column(String(128))
    origin: Mapped[str] = mapped_column(String(32))
    package_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="compiled")
    compiled_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditLogDB(TenantMixin, Base):
    __tablename__ = "audit_log_v2"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    performed_by: Mapped[str] = mapped_column(String(128))
    event_detail: Mapped[str] = mapped_column(Text, default="")
    event_data: Mapped[dict] = mapped_column(JSON, default=dict)
    event_hash: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    __table_args__ = (Index("ix_audit_v2_tenant_time", "tenant_id", "occurred_at"),)


class ExceptionRequestDB(TenantMixin, Base):
    __tablename__ = "exception_requests_v2"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    exception_type: Mapped[str] = mapped_column(String(64))
    requested_by: Mapped[str] = mapped_column(String(128))
    justification: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending_approval", index=True)
    affected_object_ids: Mapped[list] = mapped_column(JSON, default=list)
    affected_action_type: Mapped[str] = mapped_column(String(64))
    policy_context_id: Mapped[str] = mapped_column(String(64))
    compensating_controls: Mapped[list] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    risk_assessment: Mapped[str] = mapped_column(String(16))
    review_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AlertConfigDB(TenantMixin, Base):
    __tablename__ = "alert_configs_v2"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128))
    channel: Mapped[str] = mapped_column(String(32))
    destination: Mapped[str] = mapped_column(String(512))
    min_severity: Mapped[str] = mapped_column(String(16), default="critical")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
