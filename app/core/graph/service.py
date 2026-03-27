"""Graph service — the primary interface for graph operations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.audit import FabricAuditHook
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
    ControlGraphSlice,
    ControlLinkType,
    ControlObjectId,
    ControlObjectLineage,
    ControlState,
    GraphPath,
    GraphTraversalPolicy,
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
        audit_hook: FabricAuditHook | None = None,
    ) -> None:
        self._repo = repository or InMemoryGraphRepository()
        self._registry = registry or FabricRegistry()
        self._policy = policy_engine or GraphPolicyEngine(self._registry)
        self._checker = consistency_checker or GraphConsistencyChecker()
        self._audit = audit_hook or FabricAuditHook()

    @property
    def repository(self) -> GraphRepository:
        return self._repo

    @property
    def registry(self) -> FabricRegistry:
        return self._registry

    @property
    def audit_hook(self) -> FabricAuditHook:
        return self._audit

    # ── Object Operations ──────────────────────────────────────

    def create_object(
        self,
        tenant_id: uuid.UUID,
        create: ControlObjectCreate,
        actor: str = "system",
        auto_activate: bool = True,
    ) -> ControlObject:
        obj = build_control_object(tenant_id, create, actor)
        self._audit.control_object_created(
            object_id=obj.id,
            tenant_id=tenant_id,
            plane=obj.plane,
            domain=obj.domain,
            actor=actor,
        )
        if auto_activate:
            prev_state = obj.state
            obj.activate(
                AuditContext(
                    actor=actor,
                    action="activated",
                    timestamp=datetime.now(UTC),
                )
            )
            self._audit.control_object_state_changed(
                object_id=obj.id,
                tenant_id=tenant_id,
                previous_state=prev_state,
                new_state=obj.state,
                actor=actor,
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
        prev_state = obj.state
        obj.enrich(
            payload_update,
            AuditContext(
                actor=actor,
                action="enriched",
                timestamp=datetime.now(UTC),
            ),
        )
        if obj.state != prev_state:
            self._audit.control_object_state_changed(
                object_id=obj.id,
                tenant_id=obj.tenant_id,
                previous_state=prev_state,
                new_state=obj.state,
                actor=actor,
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
        prev_state = obj.state
        obj.freeze(
            AuditContext(
                actor=actor,
                action="frozen",
                timestamp=datetime.now(UTC),
            )
        )
        self._audit.control_object_frozen(object_id=obj.id, tenant_id=obj.tenant_id, actor=actor)
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
        self._audit.control_object_superseded(
            original_id=original.id,
            new_id=new_obj.id,
            tenant_id=original.tenant_id,
            actor=actor,
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

    def deprecate_object(
        self,
        object_id: ControlObjectId,
        actor: str = "system",
    ) -> ControlObject | None:
        obj = self._repo.get_object(object_id)
        if obj is None:
            return None
        obj.deprecate(
            AuditContext(
                actor=actor,
                action="deprecated",
                timestamp=datetime.now(UTC),
            )
        )
        self._audit.control_object_deprecated(
            object_id=obj.id, tenant_id=obj.tenant_id, actor=actor
        )
        self._repo.store_object(obj)
        return obj

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
        prev_state = obj.state
        obj.transition_state(
            new_state,
            AuditContext(
                actor=actor,
                action=f"transitioned_to_{new_state.value}",
                reason=reason,
                timestamp=datetime.now(UTC),
            ),
        )
        self._audit.control_object_state_changed(
            object_id=obj.id,
            tenant_id=obj.tenant_id,
            previous_state=prev_state,
            new_state=new_state,
            actor=actor,
        )
        self._repo.store_object(obj)
        return obj

    # ── Lineage ─────────────────────────────────────────────────

    def get_lineage(self, object_id: ControlObjectId) -> ControlObjectLineage | None:
        obj = self._repo.get_object(object_id)
        if obj is None:
            return None

        supersedes_links = self._repo.get_links_for_object(
            object_id, direction="outgoing", link_type=ControlLinkType.SUPERCEDES
        )
        superseded_ids = [link.target_id for link in supersedes_links]

        depth = 0
        current = object_id
        derivation_chain: list[uuid.UUID] = []
        while True:
            out_links = self._repo.get_links_for_object(
                current, direction="outgoing", link_type=ControlLinkType.SUPERCEDES
            )
            if not out_links:
                break
            current = out_links[0].target_id
            derivation_chain.append(current)
            depth += 1
            if depth > 50:
                break

        return ControlObjectLineage(
            object_id=object_id,
            derived_from=list(obj.derived_from),
            supersedes=superseded_ids,
            superseded_by=obj.superseded_by,
            derivation_chain=derivation_chain,
            depth=depth,
        )

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
        self._audit.control_link_created(
            link_id=link.id,
            tenant_id=tenant_id,
            source_id=link.source_id,
            target_id=link.target_id,
            link_type=link.link_type,
            is_cross_plane=link.is_cross_plane,
        )
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

    def find_typed_path(
        self,
        source_id: ControlObjectId,
        target_id: ControlObjectId,
        max_depth: int = 10,
    ) -> GraphPath | None:
        node_ids = self._repo.find_path(source_id, target_id, max_depth)
        if node_ids is None:
            return None

        link_ids = []
        planes_traversed: list[PlaneType] = []
        for i in range(len(node_ids) - 1):
            links = self._repo.get_links_for_object(node_ids[i], direction="outgoing")
            for link in links:
                if link.target_id == node_ids[i + 1]:
                    link_ids.append(link.id)
                    break

        for nid in node_ids:
            obj = self._repo.get_object(nid)
            if obj and obj.plane not in planes_traversed:
                planes_traversed.append(obj.plane)

        crosses_planes = len(set(planes_traversed)) > 1

        return GraphPath(
            node_ids=node_ids,
            link_ids=link_ids,
            crosses_planes=crosses_planes,
            planes_traversed=planes_traversed,
        )

    def get_graph_slice(
        self,
        root_ids: list[ControlObjectId],
        max_depth: int = 3,
        allowed_planes: list[PlaneType] | None = None,
        allowed_link_types: list[ControlLinkType] | None = None,
    ) -> tuple[list[ControlObject], list[ControlLink]]:
        return self._repo.get_graph_slice(root_ids, max_depth, allowed_planes, allowed_link_types)

    def get_typed_graph_slice(
        self,
        root_ids: list[ControlObjectId],
        policy: GraphTraversalPolicy | None = None,
    ) -> ControlGraphSlice:
        pol = policy or GraphTraversalPolicy()
        objects, links = self._repo.get_graph_slice(
            root_ids,
            max_depth=pol.max_depth,
            allowed_planes=pol.allowed_planes,
            allowed_link_types=pol.allowed_link_types,
        )
        planes_present = list({o.plane for o in objects})
        return ControlGraphSlice(
            root_ids=root_ids,
            object_ids=[o.id for o in objects],
            link_ids=[l.id for l in links],
            planes_present=planes_present,
            depth_reached=pol.max_depth,
            total_objects=len(objects),
            total_links=len(links),
            is_cross_plane=len(planes_present) > 1,
        )

    def get_contradictions(self, tenant_id: uuid.UUID) -> list[ControlLink]:
        all_links = self._repo.get_all_links(tenant_id)
        return [l for l in all_links if l.link_type == ControlLinkType.CONTRADICTS]

    def get_missing_expected_links(
        self, tenant_id: uuid.UUID
    ) -> list[tuple[ControlObjectId, ControlLinkType]]:
        """Detect objects missing expected link types based on their object type."""
        from app.core.types import ControlObjectType

        objects = self._repo.list_objects(tenant_id)
        links = self._repo.get_all_links(tenant_id)
        missing: list[tuple[ControlObjectId, ControlLinkType]] = []

        for obj in objects:
            if obj.object_type == ControlObjectType.BILLABLE_EVENT:
                has_bills_for = any(
                    l
                    for l in links
                    if l.source_id == obj.id and l.link_type == ControlLinkType.BILLS_FOR
                )
                if not has_bills_for:
                    missing.append((obj.id, ControlLinkType.BILLS_FOR))

            if obj.object_type == ControlObjectType.WORK_ORDER:
                has_fulfills = any(
                    l
                    for l in links
                    if (l.source_id == obj.id or l.target_id == obj.id)
                    and l.link_type == ControlLinkType.FULFILLS
                )
                if not has_fulfills:
                    missing.append((obj.id, ControlLinkType.FULFILLS))

        return missing

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
        report = self._checker.check(objects, links)
        self._audit.graph_consistency_checked(
            tenant_id=tenant_id,
            is_consistent=report.is_consistent,
            error_count=report.error_count,
            warning_count=report.warning_count,
        )
        return report
