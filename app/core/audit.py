"""Fabric audit hooks — control-fabric-native audit integration.

Extends the existing InMemoryAuditService pattern with typed fabric events.
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.types import (
    ControlLinkId,
    ControlLinkType,
    ControlObjectId,
    ControlState,
    PlaneType,
)


class FabricAuditEventType(str, enum.Enum):
    CONTROL_OBJECT_CREATED = "fabric.control_object.created"
    CONTROL_OBJECT_ACTIVATED = "fabric.control_object.activated"
    CONTROL_OBJECT_ENRICHED = "fabric.control_object.enriched"
    CONTROL_OBJECT_FROZEN = "fabric.control_object.frozen"
    CONTROL_OBJECT_SUPERSEDED = "fabric.control_object.superseded"
    CONTROL_OBJECT_DEPRECATED = "fabric.control_object.deprecated"
    CONTROL_OBJECT_RECONCILED = "fabric.control_object.reconciled"
    CONTROL_OBJECT_DISPUTED = "fabric.control_object.disputed"
    CONTROL_OBJECT_ACTIONED = "fabric.control_object.actioned"
    CONTROL_LINK_CREATED = "fabric.control_link.created"
    CONTROL_LINK_REMOVED = "fabric.control_link.removed"
    GRAPH_CONSISTENCY_CHECKED = "fabric.graph.consistency_checked"
    GRAPH_SLICE_EXTRACTED = "fabric.graph.slice_extracted"
    DOMAIN_PACK_REGISTERED = "fabric.domain_pack.registered"


class FabricAuditEvent(BaseModel):
    """A typed audit event from the control fabric."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: FabricAuditEventType
    tenant_id: uuid.UUID | None = None
    actor: str = "system"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    control_object_id: ControlObjectId | None = None
    control_link_id: ControlLinkId | None = None
    plane: PlaneType | None = None
    domain: str | None = None
    previous_state: ControlState | None = None
    new_state: ControlState | None = None
    link_type: ControlLinkType | None = None
    source_object_id: ControlObjectId | None = None
    target_object_id: ControlObjectId | None = None
    detail: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


FabricAuditListener = Callable[[FabricAuditEvent], None]


class FabricAuditHook:
    """Audit hook manager for fabric events.

    Allows listeners to subscribe to fabric audit events.
    Integrates with the existing InMemoryAuditService pattern.
    """

    def __init__(self) -> None:
        self._listeners: list[FabricAuditListener] = []
        self._events: list[FabricAuditEvent] = []

    def add_listener(self, listener: FabricAuditListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: FabricAuditListener) -> None:
        self._listeners = [l for l in self._listeners if l is not listener]

    @property
    def events(self) -> list[FabricAuditEvent]:
        return list(self._events)

    def emit(self, event: FabricAuditEvent) -> None:
        self._events.append(event)
        for listener in self._listeners:
            listener(event)

    def control_object_created(
        self,
        object_id: ControlObjectId,
        tenant_id: uuid.UUID,
        plane: PlaneType,
        domain: str,
        actor: str = "system",
    ) -> None:
        self.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.CONTROL_OBJECT_CREATED,
                tenant_id=tenant_id,
                actor=actor,
                control_object_id=object_id,
                plane=plane,
                domain=domain,
                new_state=ControlState.DRAFT,
                detail=f"Control object created in {plane.value}/{domain}",
            )
        )

    def control_object_state_changed(
        self,
        object_id: ControlObjectId,
        tenant_id: uuid.UUID,
        previous_state: ControlState,
        new_state: ControlState,
        actor: str = "system",
    ) -> None:
        state_to_event = {
            ControlState.ACTIVE: FabricAuditEventType.CONTROL_OBJECT_ACTIVATED,
            ControlState.ENRICHED: FabricAuditEventType.CONTROL_OBJECT_ENRICHED,
            ControlState.FROZEN: FabricAuditEventType.CONTROL_OBJECT_FROZEN,
            ControlState.SUPERSEDED: FabricAuditEventType.CONTROL_OBJECT_SUPERSEDED,
            ControlState.DEPRECATED: FabricAuditEventType.CONTROL_OBJECT_DEPRECATED,
            ControlState.RECONCILED: FabricAuditEventType.CONTROL_OBJECT_RECONCILED,
            ControlState.DISPUTED: FabricAuditEventType.CONTROL_OBJECT_DISPUTED,
            ControlState.ACTIONED: FabricAuditEventType.CONTROL_OBJECT_ACTIONED,
        }
        event_type = state_to_event.get(new_state, FabricAuditEventType.CONTROL_OBJECT_ACTIVATED)
        self.emit(
            FabricAuditEvent(
                event_type=event_type,
                tenant_id=tenant_id,
                actor=actor,
                control_object_id=object_id,
                previous_state=previous_state,
                new_state=new_state,
                detail=f"State: {previous_state.value} → {new_state.value}",
            )
        )

    def control_object_superseded(
        self,
        original_id: ControlObjectId,
        new_id: ControlObjectId,
        tenant_id: uuid.UUID,
        actor: str = "system",
    ) -> None:
        self.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.CONTROL_OBJECT_SUPERSEDED,
                tenant_id=tenant_id,
                actor=actor,
                control_object_id=original_id,
                previous_state=ControlState.ACTIVE,
                new_state=ControlState.SUPERSEDED,
                detail=f"Superseded by {new_id}",
                metadata={"new_version_id": str(new_id)},
            )
        )

    def control_object_deprecated(
        self,
        object_id: ControlObjectId,
        tenant_id: uuid.UUID,
        actor: str = "system",
    ) -> None:
        self.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.CONTROL_OBJECT_DEPRECATED,
                tenant_id=tenant_id,
                actor=actor,
                control_object_id=object_id,
                new_state=ControlState.DEPRECATED,
                detail="Control object deprecated",
            )
        )

    def control_object_frozen(
        self,
        object_id: ControlObjectId,
        tenant_id: uuid.UUID,
        actor: str = "system",
    ) -> None:
        self.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.CONTROL_OBJECT_FROZEN,
                tenant_id=tenant_id,
                actor=actor,
                control_object_id=object_id,
                new_state=ControlState.FROZEN,
                detail="Control object frozen for validation",
            )
        )

    def control_object_reconciled(
        self,
        object_id: ControlObjectId,
        tenant_id: uuid.UUID,
        actor: str = "system",
    ) -> None:
        self.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.CONTROL_OBJECT_RECONCILED,
                tenant_id=tenant_id,
                actor=actor,
                control_object_id=object_id,
                new_state=ControlState.RECONCILED,
                detail="Control object reconciled",
            )
        )

    def control_object_disputed(
        self,
        object_id: ControlObjectId,
        tenant_id: uuid.UUID,
        actor: str = "system",
    ) -> None:
        self.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.CONTROL_OBJECT_DISPUTED,
                tenant_id=tenant_id,
                actor=actor,
                control_object_id=object_id,
                new_state=ControlState.DISPUTED,
                detail="Control object disputed",
            )
        )

    def control_link_created(
        self,
        link_id: ControlLinkId,
        tenant_id: uuid.UUID,
        source_id: ControlObjectId,
        target_id: ControlObjectId,
        link_type: ControlLinkType,
        is_cross_plane: bool = False,
        actor: str = "system",
    ) -> None:
        self.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.CONTROL_LINK_CREATED,
                tenant_id=tenant_id,
                actor=actor,
                control_link_id=link_id,
                source_object_id=source_id,
                target_object_id=target_id,
                link_type=link_type,
                detail=f"Link {link_type.value}: {source_id} → {target_id}"
                + (" [cross-plane]" if is_cross_plane else ""),
            )
        )

    def graph_consistency_checked(
        self,
        tenant_id: uuid.UUID,
        is_consistent: bool,
        error_count: int = 0,
        warning_count: int = 0,
        actor: str = "system",
    ) -> None:
        self.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.GRAPH_CONSISTENCY_CHECKED,
                tenant_id=tenant_id,
                actor=actor,
                detail=f"Consistency: {'pass' if is_consistent else 'fail'} "
                f"(errors={error_count}, warnings={warning_count})",
                metadata={
                    "is_consistent": is_consistent,
                    "error_count": error_count,
                    "warning_count": warning_count,
                },
            )
        )

    def domain_pack_registered(
        self,
        domain: str,
        kind_count: int,
        actor: str = "system",
    ) -> None:
        self.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.DOMAIN_PACK_REGISTERED,
                actor=actor,
                domain=domain,
                detail=f"Domain pack '{domain}' registered with {kind_count} kinds",
                metadata={"kind_count": kind_count},
            )
        )

    def get_events_for_object(self, object_id: ControlObjectId) -> list[FabricAuditEvent]:
        return [e for e in self._events if e.control_object_id == object_id]

    def get_events_by_type(self, event_type: FabricAuditEventType) -> list[FabricAuditEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def count(self, event_type: FabricAuditEventType | None = None) -> int:
        if event_type:
            return sum(1 for e in self._events if e.event_type == event_type)
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()
