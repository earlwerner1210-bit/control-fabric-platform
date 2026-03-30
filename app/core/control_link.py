"""ControlLink — typed edges in the control graph."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.types import (
    LINK_DIRECTIONALITY,
    ConfidenceScore,
    ControlLinkId,
    ControlLinkType,
    ControlObjectId,
    EvidenceRef,
    LinkDirectionality,
    PlaneType,
    new_link_id,
)


class ControlLink(BaseModel):
    """A typed, evidence-bearing edge between two control objects."""

    id: ControlLinkId = Field(default_factory=new_link_id)
    tenant_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source_id: ControlObjectId
    target_id: ControlObjectId
    link_type: ControlLinkType
    directionality: LinkDirectionality = LinkDirectionality.DIRECTED
    source_plane: PlaneType | None = None
    target_plane: PlaneType | None = None
    weight: float = 1.0
    confidence: ConfidenceScore = ConfidenceScore(1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_cross_plane(self) -> bool:
        return (
            self.source_plane is not None
            and self.target_plane is not None
            and self.source_plane != self.target_plane
        )


class ControlLinkCreate(BaseModel):
    """Input for creating a control link."""

    source_id: uuid.UUID
    target_id: uuid.UUID
    link_type: ControlLinkType
    weight: float = 1.0
    confidence: float = 1.0
    evidence: list[EvidenceRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_control_link(
    tenant_id: uuid.UUID,
    create: ControlLinkCreate,
    source_plane: PlaneType | None = None,
    target_plane: PlaneType | None = None,
) -> ControlLink:
    """Factory function to build a validated ControlLink."""
    directionality = LINK_DIRECTIONALITY.get(create.link_type, LinkDirectionality.DIRECTED)
    return ControlLink(
        tenant_id=tenant_id,
        source_id=ControlObjectId(create.source_id),
        target_id=ControlObjectId(create.target_id),
        link_type=create.link_type,
        directionality=directionality,
        source_plane=source_plane,
        target_plane=target_plane,
        weight=create.weight,
        confidence=ConfidenceScore(create.confidence),
        evidence=list(create.evidence),
        metadata=dict(create.metadata),
    )
