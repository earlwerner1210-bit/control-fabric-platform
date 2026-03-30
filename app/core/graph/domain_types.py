from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ControlObjectState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    QUARANTINED = "quarantined"


VALID_STATE_TRANSITIONS: dict[ControlObjectState, set[ControlObjectState]] = {
    ControlObjectState.DRAFT: {ControlObjectState.ACTIVE, ControlObjectState.QUARANTINED},
    ControlObjectState.ACTIVE: {
        ControlObjectState.UNDER_REVIEW,
        ControlObjectState.DEPRECATED,
        ControlObjectState.QUARANTINED,
    },
    ControlObjectState.UNDER_REVIEW: {
        ControlObjectState.ACTIVE,
        ControlObjectState.DEPRECATED,
        ControlObjectState.QUARANTINED,
    },
    ControlObjectState.DEPRECATED: {ControlObjectState.RETIRED},
    ControlObjectState.QUARANTINED: {ControlObjectState.DRAFT, ControlObjectState.RETIRED},
    ControlObjectState.RETIRED: set(),
}


class ControlObjectType(str, Enum):
    REGULATORY_MANDATE = "regulatory_mandate"
    RISK_CONTROL = "risk_control"
    COMPLIANCE_REQUIREMENT = "compliance_requirement"
    SECURITY_CONTROL = "security_control"
    OPERATIONAL_POLICY = "operational_policy"
    TECHNICAL_CONTROL = "technical_control"
    AUDIT_FINDING = "audit_finding"
    VULNERABILITY = "vulnerability"
    ASSET = "asset"
    PROCESS = "process"
    DOMAIN_PACK_EXTENSION = "domain_pack_extension"


class RelationshipType(str, Enum):
    MITIGATES = "mitigates"
    SATISFIES = "satisfies"
    VIOLATES = "violates"
    REQUIRES = "requires"
    IMPLEMENTS = "implements"
    SUPERSEDES = "supersedes"
    DEPENDS_ON = "depends_on"
    CONFLICTS = "conflicts"
    VALIDATES = "validates"
    REFERENCES = "references"


RELATIONSHIP_ENFORCEMENT_WEIGHT: dict[RelationshipType, int] = {
    RelationshipType.VIOLATES: 100,
    RelationshipType.CONFLICTS: 90,
    RelationshipType.SATISFIES: 80,
    RelationshipType.REQUIRES: 70,
    RelationshipType.MITIGATES: 60,
    RelationshipType.IMPLEMENTS: 50,
    RelationshipType.SUPERSEDES: 40,
    RelationshipType.VALIDATES: 30,
    RelationshipType.DEPENDS_ON: 20,
    RelationshipType.REFERENCES: 10,
}


class ControlObjectProvenance(BaseModel):
    model_config = {"frozen": True}
    source_system: str
    source_uri: str | None = None
    source_hash: str
    ingested_by: str
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    origin_ip: str | None = None

    @classmethod
    def create(
        cls,
        source_system: str,
        source_content: str | bytes,
        ingested_by: str,
        source_uri: str | None = None,
        origin_ip: str | None = None,
    ) -> ControlObjectProvenance:
        if isinstance(source_content, str):
            source_content = source_content.encode()
        return cls(
            source_system=source_system,
            source_uri=source_uri,
            source_hash=hashlib.sha256(source_content).hexdigest(),
            ingested_by=ingested_by,
            origin_ip=origin_ip,
        )


class ControlObject(BaseModel):
    object_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    object_type: ControlObjectType
    name: str = Field(max_length=500)
    description: str = Field(default="")
    state: ControlObjectState = Field(default=ControlObjectState.DRAFT)
    version: int = Field(default=1, ge=1)
    schema_namespace: str
    provenance: ControlObjectProvenance
    evidence_links: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    operational_plane: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    object_hash: str = Field(default="")

    @model_validator(mode="after")
    def compute_object_hash(self) -> ControlObject:
        payload = f"{self.object_id}{self.object_type}{self.name}{self.state}{self.version}{self.schema_namespace}{self.provenance.source_hash}{self.operational_plane}"
        self.object_hash = hashlib.sha256(payload.encode()).hexdigest()
        return self

    def transition_to(self, new_state: ControlObjectState) -> ControlObject:
        valid_targets = VALID_STATE_TRANSITIONS.get(self.state, set())
        if new_state not in valid_targets:
            raise ValueError(
                f"Invalid transition: {self.state} → {new_state}. Valid: {valid_targets}"
            )
        return self.model_copy(
            update={
                "state": new_state,
                "version": self.version + 1,
                "updated_at": datetime.now(UTC),
            }
        )

    def is_active(self) -> bool:
        return self.state == ControlObjectState.ACTIVE

    def is_terminal(self) -> bool:
        return self.state == ControlObjectState.RETIRED


class ControlEdge(BaseModel):
    edge_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_object_id: str
    target_object_id: str
    relationship_type: RelationshipType
    enforcement_weight: int = Field(default=0)
    evidence_references: list[str] = Field(default_factory=list)
    valid_from: datetime = Field(default_factory=lambda: datetime.now(UTC))
    valid_until: datetime | None = None
    asserted_by: str
    context: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(default=True)
    edge_hash: str = Field(default="")

    @model_validator(mode="after")
    def set_enforcement_weight(self) -> ControlEdge:
        self.enforcement_weight = RELATIONSHIP_ENFORCEMENT_WEIGHT.get(self.relationship_type, 0)
        return self

    @model_validator(mode="after")
    def compute_edge_hash(self) -> ControlEdge:
        payload = f"{self.edge_id}{self.source_object_id}{self.target_object_id}{self.relationship_type}{self.valid_from.isoformat()}{self.asserted_by}"
        self.edge_hash = hashlib.sha256(payload.encode()).hexdigest()
        return self

    def is_valid_at(self, point_in_time: datetime) -> bool:
        if point_in_time < self.valid_from:
            return False
        if self.valid_until is not None and point_in_time > self.valid_until:
            return False
        return self.is_active


class GraphPath(BaseModel):
    path_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    nodes: list[str]
    edges: list[str]
    depth: int
    total_enforcement_weight: int


class GraphTraversalResult(BaseModel):
    query_object_id: str
    direction: str
    max_depth: int
    relationship_filter: list[str] = Field(default_factory=list)
    discovered_objects: list[str]
    discovered_edges: list[str]
    paths: list[GraphPath] = Field(default_factory=list)
    traversal_depth_reached: int
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
