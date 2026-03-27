"""Core value types for the control fabric."""

from __future__ import annotations

import enum
import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, NewType

from pydantic import BaseModel, Field

ControlObjectId = NewType("ControlObjectId", uuid.UUID)
ControlLinkId = NewType("ControlLinkId", uuid.UUID)
FabricVersion = NewType("FabricVersion", int)
ConfidenceScore = NewType("ConfidenceScore", float)


def new_object_id() -> ControlObjectId:
    return ControlObjectId(uuid.uuid4())


def new_link_id() -> ControlLinkId:
    return ControlLinkId(uuid.uuid4())


class PlaneType(str, enum.Enum):
    COMMERCIAL = "commercial"
    FIELD = "field"
    SERVICE = "service"


class ControlObjectType(str, enum.Enum):
    OBLIGATION = "obligation"
    BILLABLE_EVENT = "billable_event"
    PENALTY_CONDITION = "penalty_condition"
    DISPATCH_PRECONDITION = "dispatch_precondition"
    SKILL_REQUIREMENT = "skill_requirement"
    INCIDENT_STATE = "incident_state"
    ESCALATION_RULE = "escalation_rule"
    SERVICE_STATE = "service_state"
    READINESS_CHECK = "readiness_check"
    LEAKAGE_TRIGGER = "leakage_trigger"
    RATE_CARD = "rate_card"
    SCOPE_BOUNDARY = "scope_boundary"
    WORK_ORDER = "work_order"
    COMPLETION_CERTIFICATE = "completion_certificate"
    BILLING_GATE = "billing_gate"
    RECONCILIATION_CASE = "reconciliation_case"
    RECOVERY_RECOMMENDATION = "recovery_recommendation"
    CUSTOM = "custom"


class ControlState(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ENRICHED = "enriched"
    FROZEN = "frozen"
    RECONCILED = "reconciled"
    DISPUTED = "disputed"
    ACTIONED = "actioned"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"


VALID_STATE_TRANSITIONS: dict[ControlState, set[ControlState]] = {
    ControlState.DRAFT: {ControlState.ACTIVE},
    ControlState.ACTIVE: {
        ControlState.ENRICHED,
        ControlState.FROZEN,
        ControlState.SUPERSEDED,
        ControlState.DEPRECATED,
    },
    ControlState.ENRICHED: {
        ControlState.FROZEN,
        ControlState.ACTIVE,
        ControlState.SUPERSEDED,
        ControlState.DEPRECATED,
    },
    ControlState.FROZEN: {
        ControlState.RECONCILED,
        ControlState.DISPUTED,
        ControlState.ACTIVE,
    },
    ControlState.RECONCILED: {
        ControlState.ACTIONED,
        ControlState.DISPUTED,
        ControlState.ACTIVE,
    },
    ControlState.DISPUTED: {
        ControlState.ACTIVE,
        ControlState.FROZEN,
        ControlState.DEPRECATED,
    },
    ControlState.ACTIONED: {
        ControlState.SUPERSEDED,
        ControlState.DEPRECATED,
    },
    ControlState.SUPERSEDED: set(),
    ControlState.DEPRECATED: set(),
}


class DeterminismLevel(str, enum.Enum):
    DETERMINISTIC = "deterministic"
    MODEL_ASSISTED = "model_assisted"
    HUMAN_DETERMINED = "human_determined"


class ReasoningScope(str, enum.Enum):
    SINGLE_OBJECT = "single_object"
    PLANE_LOCAL = "plane_local"
    CROSS_PLANE = "cross_plane"
    FULL_GRAPH = "full_graph"


class ValidationStatus(str, enum.Enum):
    NOT_VALIDATED = "not_validated"
    VALIDATING = "validating"
    PASSED = "passed"
    FAILED = "failed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"


class ActionEligibility(str, enum.Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    PENDING_VALIDATION = "pending_validation"
    PENDING_APPROVAL = "pending_approval"


class ControlLinkType(str, enum.Enum):
    DERIVES_FROM = "derives_from"
    EVIDENCES = "evidences"
    CONTRADICTS = "contradicts"
    CORRELATES_WITH = "correlates_with"
    IMPLEMENTS = "implements"
    ALLOCATES_TO = "allocates_to"
    FULFILLS = "fulfills"
    BILLS_FOR = "bills_for"
    IMPACTS = "impacts"
    BLOCKS = "blocks"
    VALIDATES = "validates"
    SUPERCEDES = "supercedes"


class LinkDirectionality(str, enum.Enum):
    DIRECTED = "directed"
    BIDIRECTIONAL = "bidirectional"


LINK_DIRECTIONALITY: dict[ControlLinkType, LinkDirectionality] = {
    ControlLinkType.DERIVES_FROM: LinkDirectionality.DIRECTED,
    ControlLinkType.EVIDENCES: LinkDirectionality.DIRECTED,
    ControlLinkType.CONTRADICTS: LinkDirectionality.BIDIRECTIONAL,
    ControlLinkType.CORRELATES_WITH: LinkDirectionality.BIDIRECTIONAL,
    ControlLinkType.IMPLEMENTS: LinkDirectionality.DIRECTED,
    ControlLinkType.ALLOCATES_TO: LinkDirectionality.DIRECTED,
    ControlLinkType.FULFILLS: LinkDirectionality.DIRECTED,
    ControlLinkType.BILLS_FOR: LinkDirectionality.DIRECTED,
    ControlLinkType.IMPACTS: LinkDirectionality.DIRECTED,
    ControlLinkType.BLOCKS: LinkDirectionality.DIRECTED,
    ControlLinkType.VALIDATES: LinkDirectionality.DIRECTED,
    ControlLinkType.SUPERCEDES: LinkDirectionality.DIRECTED,
}


class EvidenceRef(BaseModel):
    """A reference to a piece of evidence supporting a control object or link."""

    evidence_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    evidence_type: str
    source_label: str
    source_id: uuid.UUID | None = None
    confidence: ConfidenceScore = ConfidenceScore(1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceArtifactRef(BaseModel):
    """Reference to the original enterprise artefact that produced a control object."""

    artifact_type: str
    artifact_id: str
    document_id: uuid.UUID | None = None
    chunk_id: uuid.UUID | None = None
    clause_ref: str | None = None
    page_number: int | None = None
    offset_start: int | None = None
    offset_end: int | None = None


class ControlProvenance(BaseModel):
    """Provenance metadata tracking how a control object was produced."""

    created_by: str
    creation_method: DeterminismLevel
    source_artifacts: list[SourceArtifactRef] = Field(default_factory=list)
    domain_pack: str | None = None
    rule_ids: list[str] = Field(default_factory=list)
    model_id: str | None = None
    model_version: str | None = None
    extraction_confidence: ConfidenceScore = ConfidenceScore(1.0)
    derivation_chain: list[uuid.UUID] = Field(default_factory=list)


class AuditContext(BaseModel):
    """Audit context attached to every control object mutation."""

    actor: str
    action: str
    reason: str | None = None
    timestamp: datetime
    correlation_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def deterministic_hash(data: dict[str, Any]) -> str:
    """Produce a deterministic hash for reproducible decision trails."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()
