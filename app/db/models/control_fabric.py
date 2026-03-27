"""Control Fabric DB models — planes, graph, reconciliation, validation, actions."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin

# ── Fabric Object ──────────────────────────────────────────────


class FabricControlPlane(str, enum.Enum):
    commercial = "commercial"
    field = "field"
    service = "service"
    governance = "governance"


class FabricObjectStatus(str, enum.Enum):
    active = "active"
    superseded = "superseded"
    retired = "retired"
    draft = "draft"
    under_review = "under_review"


class FabricObject(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "fabric_objects"

    control_type: Mapped[str] = mapped_column(String(127), nullable=False, index=True)
    plane: Mapped[FabricControlPlane] = mapped_column(
        Enum(FabricControlPlane, name="fabric_control_plane", create_constraint=True),
        nullable=False,
        index=True,
    )
    domain: Mapped[str] = mapped_column(String(63), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_clause_ref: Mapped[str | None] = mapped_column(String(63), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[FabricObjectStatus] = mapped_column(
        Enum(FabricObjectStatus, name="fabric_object_status", create_constraint=True),
        nullable=False,
        default=FabricObjectStatus.active,
    )
    tags: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


# ── Fabric Link ────────────────────────────────────────────────


class FabricLinkType(str, enum.Enum):
    depends_on = "depends_on"
    satisfies = "satisfies"
    contradicts = "contradicts"
    triggers = "triggers"
    blocks = "blocks"
    authorizes = "authorizes"
    invalidates = "invalidates"
    references = "references"


class FabricLink(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "fabric_links"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fabric_objects.id"), nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fabric_objects.id"), nullable=False, index=True
    )
    link_type: Mapped[FabricLinkType] = mapped_column(
        Enum(FabricLinkType, name="fabric_link_type", create_constraint=True),
        nullable=False,
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_refs: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


# ── Graph Snapshot ─────────────────────────────────────────────


class GraphSnapshotStatusEnum(str, enum.Enum):
    building = "building"
    ready = "ready"
    stale = "stale"
    error = "error"


class ControlGraphSnapshot(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "control_graph_snapshots"

    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[GraphSnapshotStatusEnum] = mapped_column(
        Enum(GraphSnapshotStatusEnum, name="graph_snapshot_status", create_constraint=True),
        nullable=False,
        default=GraphSnapshotStatusEnum.building,
    )
    node_count: Mapped[int] = mapped_column(Integer, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, default=0)
    scope_planes: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    scope_domains: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)


class ControlGraphNode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "control_graph_nodes"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("control_graph_snapshots.id"), nullable=False, index=True
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fabric_objects.id"), nullable=False
    )
    depth: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class ControlGraphEdge(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "control_graph_edges"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("control_graph_snapshots.id"), nullable=False, index=True
    )
    link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fabric_links.id"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


# ── Graph Slice Record ─────────────────────────────────────────


class GraphSliceRecord(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "graph_slice_records"

    root_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    node_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    edge_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    depth_reached: Mapped[int] = mapped_column(Integer, default=0)
    policy: Mapped[str] = mapped_column(String(31), nullable=False, default="bfs")
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


# ── Reconciliation ─────────────────────────────────────────────


class ReconciliationRunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class ReconciliationRun(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "reconciliation_runs"

    status: Mapped[ReconciliationRunStatus] = mapped_column(
        Enum(ReconciliationRunStatus, name="reconciliation_run_status", create_constraint=True),
        nullable=False,
        default=ReconciliationRunStatus.running,
    )
    total_objects_scanned: Mapped[int] = mapped_column(Integer, default=0)
    total_conflicts: Mapped[int] = mapped_column(Integer, default=0)
    conflicts_by_type: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    conflicts_by_severity: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scope_planes: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    scope_domains: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)


class ConflictTypeEnum(str, enum.Enum):
    contradiction = "contradiction"
    missing_dependency = "missing_dependency"
    stale_reference = "stale_reference"
    confidence_divergence = "confidence_divergence"
    domain_boundary_violation = "domain_boundary_violation"
    circular_dependency = "circular_dependency"
    authorization_gap = "authorization_gap"
    evidence_mismatch = "evidence_mismatch"


class ConflictSeverityEnum(str, enum.Enum):
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class ConflictResolutionEnum(str, enum.Enum):
    auto_resolved = "auto_resolved"
    manual_required = "manual_required"
    escalated = "escalated"
    suppressed = "suppressed"
    deferred = "deferred"
    unresolved = "unresolved"


class ReconciliationConflict(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reconciliation_conflicts"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reconciliation_runs.id"), nullable=False, index=True
    )
    conflict_type: Mapped[ConflictTypeEnum] = mapped_column(
        Enum(ConflictTypeEnum, name="conflict_type_enum", create_constraint=True),
        nullable=False,
    )
    severity: Mapped[ConflictSeverityEnum] = mapped_column(
        Enum(ConflictSeverityEnum, name="conflict_severity_enum", create_constraint=True),
        nullable=False,
    )
    source_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_plane: Mapped[str] = mapped_column(String(31), nullable=False)
    target_plane: Mapped[str | None] = mapped_column(String(31), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[ConflictResolutionEnum] = mapped_column(
        Enum(ConflictResolutionEnum, name="conflict_resolution_enum", create_constraint=True),
        nullable=False,
        default=ConflictResolutionEnum.unresolved,
    )
    resolution_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)


# ── Validation Chain ───────────────────────────────────────────


class ChainOutcomeEnum(str, enum.Enum):
    released = "released"
    blocked = "blocked"
    warn_released = "warn_released"
    escalated = "escalated"


class ValidationChainRun(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "validation_chain_runs"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    candidate_action_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    outcome: Mapped[ChainOutcomeEnum] = mapped_column(
        Enum(ChainOutcomeEnum, name="chain_outcome_enum", create_constraint=True),
        nullable=False,
    )
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    passed_steps: Mapped[int] = mapped_column(Integer, default=0)
    warned_steps: Mapped[int] = mapped_column(Integer, default=0)
    failed_steps: Mapped[int] = mapped_column(Integer, default=0)
    skipped_steps: Mapped[int] = mapped_column(Integer, default=0)
    blocking_stage: Mapped[str | None] = mapped_column(String(31), nullable=True)
    blocking_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    steps_data: Mapped[list] = mapped_column("steps", JSON, nullable=False, default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)


# ── Action Engine ──────────────────────────────────────────────


class ActionTypeEnum(str, enum.Enum):
    billing_adjustment = "billing_adjustment"
    contract_flag = "contract_flag"
    dispatch_order = "dispatch_order"
    escalation = "escalation"
    notification = "notification"
    workflow_trigger = "workflow_trigger"
    remediation = "remediation"
    audit_entry = "audit_entry"


class ActionStatusEnum(str, enum.Enum):
    candidate = "candidate"
    validating = "validating"
    released = "released"
    blocked = "blocked"
    escalated = "escalated"
    executed = "executed"
    rolled_back = "rolled_back"
    expired = "expired"


class CandidateActionRecord(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "candidate_actions"

    pilot_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action_type: Mapped[ActionTypeEnum] = mapped_column(
        Enum(ActionTypeEnum, name="action_type_enum", create_constraint=True),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[ActionStatusEnum] = mapped_column(
        Enum(ActionStatusEnum, name="action_status_enum", create_constraint=True),
        nullable=False,
        default=ActionStatusEnum.candidate,
    )
    evidence_refs: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    source_object_ids: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_chain_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    blocking_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    released_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)


class ActionEvidenceLink(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "action_evidence_links"

    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_actions.id"), nullable=False, index=True
    )
    evidence_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(63), nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0)
