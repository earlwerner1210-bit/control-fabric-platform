"""ControlObject — the first-class entity of the control fabric."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import (
    ControlObjectFrozenError,
    ControlObjectStateError,
    InvalidControlObjectError,
)
from app.core.types import (
    VALID_STATE_TRANSITIONS,
    AuditContext,
    ConfidenceScore,
    ControlObjectId,
    ControlObjectType,
    ControlProvenance,
    ControlState,
    EvidenceRef,
    FabricVersion,
    PlaneType,
    new_object_id,
)


class ControlObject(BaseModel):
    """An immutable-identity, typed, versioned control object within the fabric."""

    model_config = ConfigDict(frozen=False)

    id: ControlObjectId = Field(default_factory=new_object_id)
    tenant_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    object_type: ControlObjectType
    object_kind: str = ""
    plane: PlaneType
    domain: str
    label: str
    description: str | None = None
    state: ControlState = ControlState.DRAFT
    version: FabricVersion = FabricVersion(1)
    confidence: ConfidenceScore = ConfidenceScore(1.0)
    provenance: ControlProvenance = Field(
        default_factory=lambda: ControlProvenance(
            created_by="system", creation_method="deterministic"
        )
    )
    evidence: list[EvidenceRef] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_keys: dict[str, str] = Field(default_factory=dict)
    external_refs: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    schema_version: str = "1.0"
    superseded_by: ControlObjectId | None = None
    derived_from: list[ControlObjectId] = Field(default_factory=list)
    audit_trail: list[AuditContext] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def transition_state(self, new_state: ControlState, audit: AuditContext) -> None:
        valid = VALID_STATE_TRANSITIONS.get(self.state, set())
        if new_state not in valid:
            raise ControlObjectStateError(
                f"Cannot transition from {self.state.value} to {new_state.value}. "
                f"Valid: {[s.value for s in valid]}"
            )
        self.state = new_state
        self.updated_at = datetime.now(UTC)
        self.audit_trail.append(audit)

    def enrich(self, payload_update: dict[str, Any], audit: AuditContext) -> None:
        if self.state == ControlState.FROZEN:
            raise ControlObjectFrozenError("Cannot enrich a frozen control object")
        self.payload.update(payload_update)
        if self.state == ControlState.ACTIVE:
            self.transition_state(ControlState.ENRICHED, audit)
        else:
            self.updated_at = datetime.now(UTC)
            self.audit_trail.append(audit)

    def attach_evidence(self, evidence: EvidenceRef) -> None:
        if self.state == ControlState.FROZEN:
            raise ControlObjectFrozenError("Cannot attach evidence to a frozen control object")
        self.evidence.append(evidence)
        self.updated_at = datetime.now(UTC)

    def freeze(self, audit: AuditContext) -> None:
        if self.state in (ControlState.ACTIVE, ControlState.ENRICHED):
            self.transition_state(ControlState.FROZEN, audit)
        else:
            raise ControlObjectStateError(f"Cannot freeze from state {self.state.value}")

    def mark_reconciled(self, audit: AuditContext) -> None:
        self.transition_state(ControlState.RECONCILED, audit)

    def mark_disputed(self, audit: AuditContext) -> None:
        self.transition_state(ControlState.DISPUTED, audit)

    def mark_actioned(self, audit: AuditContext) -> None:
        self.transition_state(ControlState.ACTIONED, audit)

    def supersede(self, new_version_id: ControlObjectId, audit: AuditContext) -> None:
        self.superseded_by = new_version_id
        self.transition_state(ControlState.SUPERSEDED, audit)

    def deprecate(self, audit: AuditContext) -> None:
        self.transition_state(ControlState.DEPRECATED, audit)

    def activate(self, audit: AuditContext) -> None:
        self.transition_state(ControlState.ACTIVE, audit)

    @property
    def is_mutable(self) -> bool:
        return self.state not in (
            ControlState.FROZEN,
            ControlState.SUPERSEDED,
            ControlState.DEPRECATED,
        )


class ControlObjectCreate(BaseModel):
    """Input for creating a control object."""

    object_type: ControlObjectType
    object_kind: str = ""
    plane: PlaneType
    domain: str
    label: str
    description: str | None = None
    confidence: float = 1.0
    provenance: ControlProvenance | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_keys: dict[str, str] = Field(default_factory=dict)
    external_refs: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    derived_from: list[uuid.UUID] = Field(default_factory=list)


def build_control_object(
    tenant_id: uuid.UUID,
    create: ControlObjectCreate,
    actor: str = "system",
) -> ControlObject:
    """Factory function to build a validated ControlObject."""
    if not create.label.strip():
        raise InvalidControlObjectError("Control object label must not be empty")
    if not create.domain.strip():
        raise InvalidControlObjectError("Control object domain must not be empty")
    if create.confidence < 0.0 or create.confidence > 1.0:
        raise InvalidControlObjectError("Confidence must be between 0.0 and 1.0")

    now = datetime.now(UTC)
    provenance = create.provenance or ControlProvenance(
        created_by=actor, creation_method="deterministic"
    )

    obj = ControlObject(
        tenant_id=tenant_id,
        object_type=create.object_type,
        object_kind=create.object_kind,
        plane=create.plane,
        domain=create.domain,
        label=create.label,
        description=create.description,
        state=ControlState.DRAFT,
        confidence=ConfidenceScore(create.confidence),
        provenance=provenance,
        evidence=list(create.evidence),
        payload=dict(create.payload),
        correlation_keys=dict(create.correlation_keys),
        external_refs=dict(create.external_refs),
        tags=list(create.tags),
        derived_from=[ControlObjectId(d) for d in create.derived_from],
        audit_trail=[
            AuditContext(
                actor=actor,
                action="created",
                timestamp=now,
            )
        ],
        created_at=now,
        updated_at=now,
    )
    return obj


def supersede_object(
    original: ControlObject,
    update: ControlObjectCreate,
    actor: str = "system",
) -> ControlObject:
    """Create a new version of a control object, superseding the original."""
    new_obj = build_control_object(original.tenant_id, update, actor)
    new_obj.version = FabricVersion(original.version + 1)
    new_obj.derived_from = [original.id]
    now = datetime.now(UTC)
    original.supersede(
        new_obj.id,
        AuditContext(actor=actor, action="superseded", timestamp=now),
    )
    return new_obj
