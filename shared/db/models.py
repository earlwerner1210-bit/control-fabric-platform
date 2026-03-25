"""SQLAlchemy ORM models for the Control Fabric Platform."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db.base import Base


# ── Enums ──────────────────────────────────────────────────────────────


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


class WorkflowStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ValidationStatus(str, enum.Enum):
    passed = "passed"
    warned = "warned"
    blocked = "blocked"
    escalated = "escalated"


class CaseVerdict(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"
    needs_review = "needs_review"
    escalated = "escalated"


# ── Mixin ──────────────────────────────────────────────────────────────


class TimestampMixin:
    """Provides created_at / updated_at with server defaults."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """Provides a tenant_id foreign key."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


# ── Models ─────────────────────────────────────────────────────────────


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)

    # relationships
    users: Mapped[list[User]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    permissions: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    users: Mapped[list[User]] = relationship(back_populates="role")


class User(TimestampMixin, TenantMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(512), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="SET NULL")
    )

    tenant: Mapped[Tenant] = relationship(back_populates="users")
    role: Mapped[Role | None] = relationship(back_populates="users")


class Document(TimestampMixin, TenantMixin, Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(64), default="uploaded", nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(TimestampMixin, TenantMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_embedding", "embedding", postgresql_using="ivfflat"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    embedding = mapped_column(Vector(1536))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)

    document: Mapped[Document] = relationship(back_populates="chunks")


class CanonicalEntity(TimestampMixin, TenantMixin, Base):
    __tablename__ = "canonical_entities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_type", "canonical_name", name="uq_entity_canonical"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False)
    aliases: Mapped[dict | None] = mapped_column(JSONB, default=list)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)


class ControlObject(TimestampMixin, TenantMixin, Base):
    __tablename__ = "control_objects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    control_type: Mapped[ControlObjectType] = mapped_column(
        Enum(ControlObjectType, name="control_object_type", create_constraint=True),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="SET NULL")
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)

    links_from: Mapped[list[ControlLink]] = relationship(
        foreign_keys="ControlLink.source_id", back_populates="source", cascade="all, delete-orphan"
    )
    links_to: Mapped[list[ControlLink]] = relationship(
        foreign_keys="ControlLink.target_id", back_populates="target", cascade="all, delete-orphan"
    )


class ControlLink(TimestampMixin, TenantMixin, Base):
    __tablename__ = "control_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("control_objects.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("control_objects.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(128), nullable=False)
    weight: Mapped[float | None] = mapped_column(Float, default=1.0)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)

    source: Mapped[ControlObject] = relationship(foreign_keys=[source_id], back_populates="links_from")
    target: Mapped[ControlObject] = relationship(foreign_keys=[target_id], back_populates="links_to")


class WorkflowCase(TimestampMixin, TenantMixin, Base):
    __tablename__ = "workflow_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status", create_constraint=True),
        nullable=False,
        default=WorkflowStatus.pending,
    )
    verdict: Mapped[CaseVerdict | None] = mapped_column(
        Enum(CaseVerdict, name="case_verdict", create_constraint=True)
    )
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_payload: Mapped[dict | None] = mapped_column(JSONB)
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)


class ValidationResult(TimestampMixin, TenantMixin, Base):
    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_type: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status", create_constraint=True),
        nullable=False,
    )
    rules_passed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rules_warned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rules_blocked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rule_results: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)


class ModelRun(TimestampMixin, TenantMixin, Base):
    __tablename__ = "model_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    model_name: Mapped[str] = mapped_column(String(256), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_templates.id", ondelete="SET NULL")
    )
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_payload: Mapped[dict | None] = mapped_column(JSONB)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)


class AuditEvent(TimestampMixin, TenantMixin, Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(512))


class PromptTemplate(TimestampMixin, TenantMixin, Base):
    __tablename__ = "prompt_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[dict | None] = mapped_column(JSONB, default=list)
    domain_pack: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_prompt_template_name_version"),
    )


class DomainPackVersion(TimestampMixin, Base):
    __tablename__ = "domain_pack_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pack_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("pack_name", "version", name="uq_domain_pack_version"),
    )


class EvalCase(TimestampMixin, TenantMixin, Base):
    __tablename__ = "eval_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    eval_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    expected_output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    tags: Mapped[dict | None] = mapped_column(JSONB, default=list)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)


class EvalRun(TimestampMixin, TenantMixin, Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    eval_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_cases.id", ondelete="CASCADE"), nullable=False
    )
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL")
    )
    actual_output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    score: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    detail: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    eval_case: Mapped[EvalCase] = relationship()


class NotificationEvent(TimestampMixin, TenantMixin, Base):
    __tablename__ = "notification_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel: Mapped[str] = mapped_column(String(64), nullable=False)  # email, slack, webhook
    recipient: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_detail: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)
