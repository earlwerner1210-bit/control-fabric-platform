"""Graph service — the primary interface for graph operations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.control_link import ControlLink, ControlLinkCreate, build_control_link
from app.core.control_object import (
    ControlObject,
    ControlObjectCreate,
    build_control_object,
    supersede_object,
)
from app.core.errors import DuplicateLinkError, InvalidLinkError
from app.core.graph.consistency import ConsistencyReport, GraphConsistencyChecker
from app.core.graph.policy import GraphPolicyEngine
from app.core.graph.repository import GraphRepository, InMemoryGraphRepository
from app.core.registry import FabricRegistry
from app.core.types import (
    AuditContext,
    ControlLinkType,
    ControlObjectId,
    ControlState,
    PlaneType,
)


class GraphService:
    """Primary service for all graph operations on the control fabric."""

    def __init__(
        self,
        repository: GraphRepository | None = None,
        registry: FabricRegistry | None = None,
        policy_engine: GraphPolicyEngine | None = None,
        consistency_checker: GraphConsistencyChecker | None = None,
    ) -> None:
        self._repo = repository or InMemoryGraphRepository()
        self._registry = registry or FabricRegistry()
        self._policy = policy_engine or GraphPolicyEngine(self._registry)
        self._checker = consistency_checker or GraphConsistencyChecker()

    @property
    def repository(self) -> GraphRepository:
        return self._repo

    @property
    def registry(self) -> FabricRegistry:
        return self._registry

    # ── Object Operations ──────────────────────────────────────

    def create_object(
        self,
        tenant_id: uuid.UUID,
        create: ControlObjectCreate,
        actor: str = "system",
        auto_activate: bool = True,
    ) -> ControlObject:
        obj = build_control_object(tenant_id, create, actor)
        if auto_activate:
            obj.activate(
                AuditContext(
                    actor=actor,
                    action="activated",
                    timestamp=datetime.now(UTC),
                )
            )
        self._repo.store_object(obj)
        return obj

    def get_object(self, object_id: ControlObjectId) -> ControlObject | None:
        return self._repo.get_object(object_id)

    def list_objects(
        self,
        tenant_id: uuid.UUID,
        plane: PlaneType | None = None,
        domain: str | None = None,
        object_kind: str | None = None,
        state: ControlState | None = None,
    ) -> list[ControlObject]:
        return self._repo.list_objects(tenant_id, plane, domain, object_kind, state)

    def enrich_object(
        self,
        object_id: ControlObjectId,
        payload_update: dict[str, Any],
        actor: str = "system",
    ) -> ControlObject | None:
        obj = self._repo.get_object(object_id)
        if obj is None:
            return None
        obj.enrich(
            payload_update,
            AuditContext(
                actor=actor,
                action="enriched",
                timestamp=datetime.now(UTC),
            ),
        )
        self._repo.store_object(obj)
        return obj

    def freeze_object(
        self,
        object_id: ControlObjectId,
        actor: str = "system",
    ) -> ControlObject | None:
        obj = self._repo.get_object(object_id)
        if obj is None:
            return None
        obj.freeze(
            AuditContext(
                actor=actor,
                action="frozen",
                timestamp=datetime.now(UTC),
            )
        )
        self._repo.store_object(obj)
        return obj

    def supersede_object(
        self,
        object_id: ControlObjectId,
        update: ControlObjectCreate,
        actor: str = "system",
    ) -> ControlObject | None:
        original = self._repo.get_object(object_id)
        if original is None:
            return None
        new_obj = supersede_object(original, update, actor)
        new_obj.activate(
            AuditContext(
                actor=actor,
                action="activated",
                timestamp=datetime.now(UTC),
            )
        )
        self._repo.store_object(original)
        self._repo.store_object(new_obj)
        link = build_control_link(
            original.tenant_id,
            ControlLinkCreate(
                source_id=new_obj.id,
                target_id=original.id,
                link_type=ControlLinkType.SUPERCEDES,
            ),
            source_plane=new_obj.plane,
            target_plane=original.plane,
        )
        self._repo.store_link(link)
        return new_obj

    def transition_object(
        self,
        object_id: ControlObjectId,
        new_state: ControlState,
        actor: str = "system",
        reason: str | None = None,
    ) -> ControlObject | None:
        obj = self._repo.get_object(object_id)
        if obj is None:
            return None
        obj.transition_state(
            new_state,
            AuditContext(
                actor=actor,
                action=f"transitioned_to_{new_state.value}",
                reason=reason,
                timestamp=datetime.now(UTC),
            ),
        )
        self._repo.store_object(obj)
        return obj

    # ── Link Operations ────────────────────────────────────────

    def create_link(
        self,
        tenant_id: uuid.UUID,
        create: ControlLinkCreate,
    ) -> ControlLink:
        source = self._repo.get_object(ControlObjectId(create.source_id))
        target = self._repo.get_object(ControlObjectId(create.target_id))
        if source is None:
            raise InvalidLinkError(f"Source object {create.source_id} not found")
        if target is None:
            raise InvalidLinkError(f"Target object {create.target_id} not found")

        self._policy.enforce_link(create, source, target)

        link = build_control_link(
            tenant_id,
            create,
            source_plane=source.plane,
            target_plane=target.plane,
        )
        self._repo.store_link(link)
        return link

    def get_links_for_object(
        self,
        object_id: ControlObjectId,
        direction: str = "both",
        link_type: ControlLinkType | None = None,
    ) -> list[ControlLink]:
        return self._repo.get_links_for_object(object_id, direction, link_type)

    def get_neighbours(
        self,
        object_id: ControlObjectId,
        direction: str = "both",
        link_type: ControlLinkType | None = None,
    ) -> list[ControlObject]:
        return self._repo.get_neighbours(object_id, direction, link_type)

    # ── Graph Queries ──────────────────────────────────────────

    def find_path(
        self,
        source_id: ControlObjectId,
        target_id: ControlObjectId,
        max_depth: int = 10,
    ) -> list[ControlObjectId] | None:
        return self._repo.find_path(source_id, target_id, max_depth)

    def get_graph_slice(
        self,
        root_ids: list[ControlObjectId],
        max_depth: int = 3,
        allowed_planes: list[PlaneType] | None = None,
        allowed_link_types: list[ControlLinkType] | None = None,
    ) -> tuple[list[ControlObject], list[ControlLink]]:
        return self._repo.get_graph_slice(root_ids, max_depth, allowed_planes, allowed_link_types)

    def get_contradictions(self, tenant_id: uuid.UUID) -> list[ControlLink]:
        all_links = self._repo.get_all_links(tenant_id)
        return [l for l in all_links if l.link_type == ControlLinkType.CONTRADICTS]

    # ── Consistency ────────────────────────────────────────────

    def check_consistency(
        self,
        tenant_id: uuid.UUID,
        plane: PlaneType | None = None,
    ) -> ConsistencyReport:
        objects = self._repo.list_objects(tenant_id, plane=plane)
        links = self._repo.get_all_links(tenant_id)
        if plane:
            obj_ids = {o.id for o in objects}
            links = [l for l in links if l.source_id in obj_ids or l.target_id in obj_ids]
        return self._checker.check(objects, links)
