from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import UTC, datetime, timezone
from typing import Any

from app.core.graph.domain_types import (
    ControlEdge,
    ControlObject,
    GraphPath,
    GraphTraversalResult,
    RelationshipType,
)

logger = logging.getLogger(__name__)


class GraphIntegrityError(Exception):
    pass


class ControlGraphStore:
    def __init__(self) -> None:
        self._nodes: dict[str, ControlObject] = {}
        self._edges: dict[str, ControlEdge] = {}
        self._outbound: dict[str, list[str]] = defaultdict(list)
        self._inbound: dict[str, list[str]] = defaultdict(list)
        self._plane_index: dict[str, list[str]] = defaultdict(list)
        self._type_index: dict[str, list[str]] = defaultdict(list)

    def add_object(self, obj: ControlObject) -> None:
        if obj.object_id in self._nodes:
            raise GraphIntegrityError(f"Object {obj.object_id} already exists.")
        self._nodes[obj.object_id] = obj
        self._plane_index[obj.operational_plane].append(obj.object_id)
        self._type_index[obj.object_type.value].append(obj.object_id)

    def update_object(self, obj: ControlObject) -> None:
        if obj.object_id not in self._nodes:
            raise GraphIntegrityError(f"Object {obj.object_id} not found.")
        old = self._nodes[obj.object_id]
        if old.operational_plane != obj.operational_plane:
            self._plane_index[old.operational_plane].remove(obj.object_id)
            self._plane_index[obj.operational_plane].append(obj.object_id)
        self._nodes[obj.object_id] = obj

    def get_object(self, object_id: str) -> ControlObject | None:
        return self._nodes.get(object_id)

    def get_objects_by_plane(self, plane: str) -> list[ControlObject]:
        return [self._nodes[oid] for oid in self._plane_index.get(plane, []) if oid in self._nodes]

    def get_objects_by_type(self, object_type: str) -> list[ControlObject]:
        return [
            self._nodes[oid] for oid in self._type_index.get(object_type, []) if oid in self._nodes
        ]

    def get_active_objects(self) -> list[ControlObject]:
        return [obj for obj in self._nodes.values() if obj.is_active()]

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def add_edge(self, edge: ControlEdge) -> None:
        if edge.source_object_id not in self._nodes:
            raise GraphIntegrityError(f"Source object {edge.source_object_id} not found.")
        if edge.target_object_id not in self._nodes:
            raise GraphIntegrityError(f"Target object {edge.target_object_id} not found.")
        if edge.edge_id in self._edges:
            raise GraphIntegrityError(f"Edge {edge.edge_id} already exists.")
        if edge.source_object_id == edge.target_object_id:
            raise GraphIntegrityError("Self-referential edges are not permitted.")
        self._edges[edge.edge_id] = edge
        self._outbound[edge.source_object_id].append(edge.edge_id)
        self._inbound[edge.target_object_id].append(edge.edge_id)

    def get_edge(self, edge_id: str) -> ControlEdge | None:
        return self._edges.get(edge_id)

    def get_outbound_edges(
        self,
        object_id: str,
        relationship_filter: list[RelationshipType] | None = None,
        at_time: datetime | None = None,
    ) -> list[ControlEdge]:
        at_time = at_time or datetime.now(UTC)
        edges = [
            self._edges[eid] for eid in self._outbound.get(object_id, []) if eid in self._edges
        ]
        edges = [e for e in edges if e.is_valid_at(at_time)]
        if relationship_filter:
            edges = [e for e in edges if e.relationship_type in relationship_filter]
        return edges

    def get_inbound_edges(
        self,
        object_id: str,
        relationship_filter: list[RelationshipType] | None = None,
        at_time: datetime | None = None,
    ) -> list[ControlEdge]:
        at_time = at_time or datetime.now(UTC)
        edges = [self._edges[eid] for eid in self._inbound.get(object_id, []) if eid in self._edges]
        edges = [e for e in edges if e.is_valid_at(at_time)]
        if relationship_filter:
            edges = [e for e in edges if e.relationship_type in relationship_filter]
        return edges

    def deactivate_edge(self, edge_id: str) -> None:
        if edge_id not in self._edges:
            raise GraphIntegrityError(f"Edge {edge_id} not found.")
        self._edges[edge_id] = self._edges[edge_id].model_copy(update={"is_active": False})

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def traverse(
        self,
        start_object_id: str,
        direction: str = "outbound",
        max_depth: int = 3,
        relationship_filter: list[RelationshipType] | None = None,
        at_time: datetime | None = None,
    ) -> GraphTraversalResult:
        if start_object_id not in self._nodes:
            raise GraphIntegrityError(f"Start object {start_object_id} not found.")
        at_time = at_time or datetime.now(UTC)
        visited_nodes: set[str] = {start_object_id}
        visited_edges: set[str] = set()
        paths: list[GraphPath] = []
        max_depth_reached = 0
        queue: deque[tuple[str, int, list[str], list[str], int]] = deque()
        queue.append((start_object_id, 0, [start_object_id], [], 0))
        while queue:
            node_id, depth, path_nodes, path_edges, path_weight = queue.popleft()
            if depth >= max_depth:
                max_depth_reached = max(max_depth_reached, depth)
                continue
            edges: list[ControlEdge] = []
            if direction in ("outbound", "both"):
                edges.extend(self.get_outbound_edges(node_id, relationship_filter, at_time))
            if direction in ("inbound", "both"):
                edges.extend(self.get_inbound_edges(node_id, relationship_filter, at_time))
            for edge in edges:
                if edge.edge_id in visited_edges:
                    continue
                visited_edges.add(edge.edge_id)
                next_id = (
                    edge.target_object_id
                    if edge.source_object_id == node_id
                    else edge.source_object_id
                )
                new_weight = path_weight + edge.enforcement_weight
                new_nodes = path_nodes + [next_id]
                new_edges = path_edges + [edge.edge_id]
                paths.append(
                    GraphPath(
                        nodes=new_nodes,
                        edges=new_edges,
                        depth=depth + 1,
                        total_enforcement_weight=new_weight,
                    )
                )
                if next_id not in visited_nodes:
                    visited_nodes.add(next_id)
                    max_depth_reached = max(max_depth_reached, depth + 1)
                    queue.append((next_id, depth + 1, new_nodes, new_edges, new_weight))
        return GraphTraversalResult(
            query_object_id=start_object_id,
            direction=direction,
            max_depth=max_depth,
            relationship_filter=[r.value for r in (relationship_filter or [])],
            discovered_objects=list(visited_nodes - {start_object_id}),
            discovered_edges=list(visited_edges),
            paths=paths,
            traversal_depth_reached=max_depth_reached,
        )

    def find_path_between(
        self, source_id: str, target_id: str, max_depth: int = 5
    ) -> GraphPath | None:
        if source_id not in self._nodes or target_id not in self._nodes:
            return None
        at_time = datetime.now(UTC)
        visited: set[str] = {source_id}
        queue: deque[tuple[str, list[str], list[str], int]] = deque()
        queue.append((source_id, [source_id], [], 0))
        while queue:
            node_id, path_nodes, path_edges, weight = queue.popleft()
            if node_id == target_id:
                return GraphPath(
                    nodes=path_nodes,
                    edges=path_edges,
                    depth=len(path_nodes) - 1,
                    total_enforcement_weight=weight,
                )
            if len(path_nodes) - 1 >= max_depth:
                continue
            for edge in self.get_outbound_edges(node_id, at_time=at_time):
                if edge.target_object_id not in visited:
                    visited.add(edge.target_object_id)
                    queue.append(
                        (
                            edge.target_object_id,
                            path_nodes + [edge.target_object_id],
                            path_edges + [edge.edge_id],
                            weight + edge.enforcement_weight,
                        )
                    )
        return None

    def get_impact_analysis(self, object_id: str, max_depth: int = 3) -> dict[str, Any]:
        if object_id not in self._nodes:
            raise GraphIntegrityError(f"Object {object_id} not found.")
        obj = self._nodes[object_id]
        outbound = self.traverse(object_id, direction="outbound", max_depth=max_depth)
        inbound = self.traverse(object_id, direction="inbound", max_depth=max_depth)
        critical_edges = [
            self._edges[eid]
            for eid in outbound.discovered_edges + inbound.discovered_edges
            if eid in self._edges and self._edges[eid].enforcement_weight >= 60
        ]
        return {
            "object_id": object_id,
            "object_name": obj.name,
            "object_type": obj.object_type.value,
            "operational_plane": obj.operational_plane,
            "downstream_objects": outbound.discovered_objects,
            "upstream_objects": inbound.discovered_objects,
            "total_affected_objects": len(
                set(outbound.discovered_objects + inbound.discovered_objects)
            ),
            "critical_relationships": [
                {
                    "edge_id": e.edge_id,
                    "type": e.relationship_type.value,
                    "source": e.source_object_id,
                    "target": e.target_object_id,
                    "enforcement_weight": e.enforcement_weight,
                }
                for e in critical_edges
            ],
            "max_depth_analysed": max_depth,
        }

    def get_objects_missing_relationship(
        self, object_type: str, required_relationship: RelationshipType
    ) -> list[ControlObject]:
        at_time = datetime.now(UTC)
        missing = []
        for obj in self.get_objects_by_type(object_type):
            if not obj.is_active():
                continue
            if not self.get_outbound_edges(
                obj.object_id, [required_relationship], at_time
            ) and not self.get_inbound_edges(obj.object_id, [required_relationship], at_time):
                missing.append(obj)
        return missing
