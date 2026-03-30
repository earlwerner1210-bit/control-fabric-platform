"""Graph repository — abstraction and in-memory implementation."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections import deque
from typing import Any

from app.core.control_link import ControlLink
from app.core.control_object import ControlObject
from app.core.types import (
    ControlLinkId,
    ControlLinkType,
    ControlObjectId,
    ControlState,
    PlaneType,
)


class GraphRepository(ABC):
    """Abstract repository for the control graph."""

    @abstractmethod
    def store_object(self, obj: ControlObject) -> None: ...

    @abstractmethod
    def get_object(self, object_id: ControlObjectId) -> ControlObject | None: ...

    @abstractmethod
    def list_objects(
        self,
        tenant_id: uuid.UUID,
        plane: PlaneType | None = None,
        domain: str | None = None,
        object_kind: str | None = None,
        state: ControlState | None = None,
    ) -> list[ControlObject]: ...

    @abstractmethod
    def store_link(self, link: ControlLink) -> None: ...

    @abstractmethod
    def get_link(self, link_id: ControlLinkId) -> ControlLink | None: ...

    @abstractmethod
    def get_links_for_object(
        self,
        object_id: ControlObjectId,
        direction: str = "both",
        link_type: ControlLinkType | None = None,
    ) -> list[ControlLink]: ...

    @abstractmethod
    def get_all_links(self, tenant_id: uuid.UUID) -> list[ControlLink]: ...

    @abstractmethod
    def get_neighbours(
        self,
        object_id: ControlObjectId,
        direction: str = "both",
        link_type: ControlLinkType | None = None,
    ) -> list[ControlObject]: ...

    @abstractmethod
    def find_path(
        self,
        source_id: ControlObjectId,
        target_id: ControlObjectId,
        max_depth: int = 10,
    ) -> list[ControlObjectId] | None: ...

    @abstractmethod
    def get_graph_slice(
        self,
        root_ids: list[ControlObjectId],
        max_depth: int = 3,
        allowed_planes: list[PlaneType] | None = None,
        allowed_link_types: list[ControlLinkType] | None = None,
    ) -> tuple[list[ControlObject], list[ControlLink]]: ...


class InMemoryGraphRepository(GraphRepository):
    """In-memory graph repository for testing and development."""

    def __init__(self) -> None:
        self._objects: dict[ControlObjectId, ControlObject] = {}
        self._links: dict[ControlLinkId, ControlLink] = {}

    def store_object(self, obj: ControlObject) -> None:
        self._objects[obj.id] = obj

    def get_object(self, object_id: ControlObjectId) -> ControlObject | None:
        return self._objects.get(object_id)

    def list_objects(
        self,
        tenant_id: uuid.UUID,
        plane: PlaneType | None = None,
        domain: str | None = None,
        object_kind: str | None = None,
        state: ControlState | None = None,
    ) -> list[ControlObject]:
        results = [o for o in self._objects.values() if o.tenant_id == tenant_id]
        if plane:
            results = [o for o in results if o.plane == plane]
        if domain:
            results = [o for o in results if o.domain == domain]
        if object_kind:
            results = [o for o in results if o.object_kind == object_kind]
        if state:
            results = [o for o in results if o.state == state]
        return results

    def store_link(self, link: ControlLink) -> None:
        self._links[link.id] = link

    def get_link(self, link_id: ControlLinkId) -> ControlLink | None:
        return self._links.get(link_id)

    def get_links_for_object(
        self,
        object_id: ControlObjectId,
        direction: str = "both",
        link_type: ControlLinkType | None = None,
    ) -> list[ControlLink]:
        results = []
        for link in self._links.values():
            match = False
            if direction in ("outgoing", "both") and link.source_id == object_id:
                match = True
            if direction in ("incoming", "both") and link.target_id == object_id:
                match = True
            if match:
                if link_type is None or link.link_type == link_type:
                    results.append(link)
        return results

    def get_all_links(self, tenant_id: uuid.UUID) -> list[ControlLink]:
        return [l for l in self._links.values() if l.tenant_id == tenant_id]

    def get_neighbours(
        self,
        object_id: ControlObjectId,
        direction: str = "both",
        link_type: ControlLinkType | None = None,
    ) -> list[ControlObject]:
        links = self.get_links_for_object(object_id, direction, link_type)
        neighbour_ids: set[ControlObjectId] = set()
        for link in links:
            if link.source_id == object_id:
                neighbour_ids.add(link.target_id)
            if link.target_id == object_id:
                neighbour_ids.add(link.source_id)
        return [self._objects[nid] for nid in neighbour_ids if nid in self._objects]

    def find_path(
        self,
        source_id: ControlObjectId,
        target_id: ControlObjectId,
        max_depth: int = 10,
    ) -> list[ControlObjectId] | None:
        if source_id not in self._objects or target_id not in self._objects:
            return None
        queue: deque[tuple[ControlObjectId, list[ControlObjectId]]] = deque()
        queue.append((source_id, [source_id]))
        visited: set[ControlObjectId] = {source_id}
        while queue:
            current, path = queue.popleft()
            if current == target_id:
                return path
            if len(path) > max_depth:
                continue
            for link in self._links.values():
                neighbor = None
                if link.source_id == current:
                    neighbor = link.target_id
                elif link.target_id == current:
                    neighbor = link.source_id
                if neighbor and neighbor not in visited and neighbor in self._objects:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return None

    def get_graph_slice(
        self,
        root_ids: list[ControlObjectId],
        max_depth: int = 3,
        allowed_planes: list[PlaneType] | None = None,
        allowed_link_types: list[ControlLinkType] | None = None,
    ) -> tuple[list[ControlObject], list[ControlLink]]:
        visited: set[ControlObjectId] = set()
        collected_links: list[ControlLink] = []
        queue: deque[tuple[ControlObjectId, int]] = deque()

        for rid in root_ids:
            if rid in self._objects:
                queue.append((rid, 0))
                visited.add(rid)

        while queue:
            current_id, depth = queue.popleft()
            for link in self._links.values():
                neighbor_id = None
                if link.source_id == current_id:
                    neighbor_id = link.target_id
                elif link.target_id == current_id:
                    neighbor_id = link.source_id
                if neighbor_id is None:
                    continue
                if allowed_link_types and link.link_type not in allowed_link_types:
                    continue
                neighbor = self._objects.get(neighbor_id)
                if neighbor is None:
                    continue
                if allowed_planes and neighbor.plane not in allowed_planes:
                    continue
                collected_links.append(link)
                if neighbor_id not in visited and depth + 1 <= max_depth:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, depth + 1))

        objects = [self._objects[oid] for oid in visited if oid in self._objects]
        return objects, collected_links
