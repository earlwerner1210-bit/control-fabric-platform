"""Common Pydantic v2 schemas shared across all services."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Mixins ──────────────────────────────────────────────────────────────


class TenantMixin(BaseModel):
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenancy")


class TimestampMixin(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None


# ── Users ───────────────────────────────────────────────────────────────


class UserRecord(TenantMixin, TimestampMixin):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    full_name: str
    role: str = "user"
    is_active: bool = True


# ── Documents ───────────────────────────────────────────────────────────


class DocumentMeta(TenantMixin, TimestampMixin):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    checksum: str = ""
    document_type: str | None = None
    status: str = "uploaded"
    storage_path: str = ""
    parsed_content: dict[str, Any] | None = None


# ── Chunks ──────────────────────────────────────────────────────────────


class ChunkRecord(TenantMixin, TimestampMixin):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    chunk_index: int
    text: str
    token_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Embeddings ──────────────────────────────────────────────────────────


class EmbeddingRecord(TenantMixin, TimestampMixin):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chunk_id: str
    model: str
    vector: list[float] = Field(default_factory=list)
    dimension: int = 1536


# ── Entities ────────────────────────────────────────────────────────────


class EntityRecord(TenantMixin, TimestampMixin):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    canonical_name: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Control Objects ────────────────────────────────────────────────────


class ControlObject(TenantMixin, TimestampMixin):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    object_type: str  # contract, work_order, incident
    source_document_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    links: list[str] = Field(default_factory=list)
    status: str = "draft"


# ── Validation ──────────────────────────────────────────────────────────


class ValidationStatus(str, Enum):
    passed = "passed"
    warned = "warned"
    blocked = "blocked"
    escalated = "escalated"


class ValidationResult(TenantMixin, TimestampMixin):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str
    control_object_id: str
    domain: str
    status: ValidationStatus = ValidationStatus.passed
    rules_applied: list[str] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 1.0


# ── Audit ───────────────────────────────────────────────────────────────


class AuditEntry(TenantMixin, TimestampMixin):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str | None = None
    event_type: str
    actor: str = "system"
    service: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)


# ── Evals ───────────────────────────────────────────────────────────────


class EvalResult(TenantMixin, TimestampMixin):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    case_id: str
    expected: dict[str, Any] = Field(default_factory=dict)
    actual: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    passed: bool = False


# ── Notifications ───────────────────────────────────────────────────────


class NotificationRecord(TenantMixin, TimestampMixin):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel: str = "email"  # email, webhook, in-app
    recipient: str = ""
    subject: str = ""
    body: str = ""
    status: str = "pending"


# ── Reports ─────────────────────────────────────────────────────────────


class ReportRecord(TenantMixin, TimestampMixin):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str
    report_type: str  # case_summary, management_summary
    content: dict[str, Any] = Field(default_factory=dict)
    format: str = "json"
