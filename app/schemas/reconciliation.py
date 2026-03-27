"""Reconciliation schemas — cross-plane conflict detection and resolution."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.control_fabric import ControlPlane


class ConflictType(str, enum.Enum):
    CONTRADICTION = "contradiction"
    MISSING_DEPENDENCY = "missing_dependency"
    STALE_REFERENCE = "stale_reference"
    CONFIDENCE_DIVERGENCE = "confidence_divergence"
    DOMAIN_BOUNDARY_VIOLATION = "domain_boundary_violation"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    AUTHORIZATION_GAP = "authorization_gap"
    EVIDENCE_MISMATCH = "evidence_mismatch"


class ConflictSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ConflictResolution(str, enum.Enum):
    AUTO_RESOLVED = "auto_resolved"
    MANUAL_REQUIRED = "manual_required"
    ESCALATED = "escalated"
    SUPPRESSED = "suppressed"
    DEFERRED = "deferred"
    UNRESOLVED = "unresolved"


class ReconciliationRunRequest(BaseModel):
    tenant_id: uuid.UUID
    scope_planes: list[ControlPlane] = Field(default_factory=list)
    scope_domains: list[str] = Field(default_factory=list)
    include_retired: bool = False
    conflict_types: list[ConflictType] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReconciliationConflictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    conflict_type: ConflictType
    severity: ConflictSeverity
    source_object_id: uuid.UUID
    target_object_id: uuid.UUID | None
    source_plane: ControlPlane
    target_plane: ControlPlane | None
    description: str
    resolution: ConflictResolution
    resolution_detail: str | None
    metadata: dict[str, Any]
    created_at: datetime


class ReconciliationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    status: str
    total_objects_scanned: int
    total_conflicts: int
    conflicts_by_type: dict[str, int]
    conflicts_by_severity: dict[str, int]
    scope_planes: list[str]
    scope_domains: list[str]
    conflicts: list[ReconciliationConflictResponse]
    duration_ms: float | None
    metadata: dict[str, Any]
    created_at: datetime


class ReconciliationSummary(BaseModel):
    total_runs: int = 0
    total_conflicts: int = 0
    unresolved_conflicts: int = 0
    conflicts_by_type: dict[str, int] = Field(default_factory=dict)
    conflicts_by_severity: dict[str, int] = Field(default_factory=dict)
    conflicts_by_plane_pair: dict[str, int] = Field(default_factory=dict)
    avg_conflicts_per_run: float = 0.0


class ConflictResolutionRequest(BaseModel):
    resolution: ConflictResolution
    resolution_detail: str | None = None
    resolved_by: uuid.UUID | None = None
