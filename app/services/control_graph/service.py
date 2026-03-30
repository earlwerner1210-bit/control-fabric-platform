"""Control Graph Service — snapshots, slicing, traversal, analytics."""

from __future__ import annotations

import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any

from app.schemas.control_fabric import ControlLinkType, ControlPlane
from app.schemas.control_graph import (
    GraphAnalytics,
    GraphEdgeData,
    GraphNodeData,
    GraphSlicePolicy,
    GraphSliceRequest,
    GraphSliceResponse,
    GraphSnapshotCreate,
    GraphSnapshotResponse,
    GraphSnapshotStatus,
    GraphTraversalResult,
)
from app.services.control_fabric.service import ControlFabricService


class ControlGraphService:
    """Builds graph snapshots and slices from the control fabric."""

    def __init__(self, fabric_service: ControlFabricService) -> None:
        self._fabric = fabric_service
        self._snapshots: dict[uuid.UUID, dict[str, Any]] = {}
        self._snapshot_nodes: dict[uuid.UUID, list[dict[str, Any]]] = {}
        self._snapshot_edges: dict[uuid.UUID, list[dict[str, Any]]] = {}
        self._slices: dict[uuid.UUID, dict[str, Any]] = {}

    # ── Snapshot ───────────────────────────────────────────────

    def create_snapshot(
        self,
        create: GraphSnapshotCreate,
    ) -> GraphSnapshotResponse:
        snap_id = uuid.uuid4()
        now = datetime.now(UTC)

        objects, _ = self._fabric.query_objects(create.tenant_id)

        if create.scope_planes:
            objects = [o for o in objects if o.plane in create.scope_planes]
        if create.scope_domains:
            objects = [o for o in objects if o.domain in create.scope_domains]

        obj_ids = {o.id for o in objects}

        nodes = []
        for obj in objects:
            nodes.append(
                {
                    "object_id": obj.id,
                    "control_type": obj.control_type,
                    "plane": obj.plane,
                    "domain": obj.domain,
                    "label": obj.label,
                    "confidence": obj.confidence,
                    "status": obj.status.value if hasattr(obj.status, "value") else str(obj.status),
                    "tags": obj.tags,
                    "depth": 0,
                }
            )

        edges = []
        all_links: list[Any] = []
        for oid in obj_ids:
            links = self._fabric.get_links_for_object(oid, direction="outgoing")
            for link in links:
                if link.target_id in obj_ids:
                    edges.append(
                        {
                            "link_id": link.id,
                            "source_id": link.source_id,
                            "target_id": link.target_id,
                            "link_type": link.link_type,
                            "weight": link.weight,
                        }
                    )
                    all_links.append(link)

        snap = {
            "id": snap_id,
            "tenant_id": create.tenant_id,
            "label": create.label,
            "status": GraphSnapshotStatus.READY,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "scope_planes": [
                p.value if hasattr(p, "value") else str(p) for p in create.scope_planes
            ],
            "scope_domains": create.scope_domains,
            "metadata": create.metadata,
            "created_at": now,
        }
        self._snapshots[snap_id] = snap
        self._snapshot_nodes[snap_id] = nodes
        self._snapshot_edges[snap_id] = edges

        return GraphSnapshotResponse(**snap)

    def get_snapshot(self, snapshot_id: uuid.UUID) -> GraphSnapshotResponse | None:
        snap = self._snapshots.get(snapshot_id)
        return GraphSnapshotResponse(**snap) if snap else None

    def list_snapshots(self, tenant_id: uuid.UUID) -> list[GraphSnapshotResponse]:
        return [
            GraphSnapshotResponse(**s)
            for s in self._snapshots.values()
            if s["tenant_id"] == tenant_id
        ]

    # ── Slicing ────────────────────────────────────────────────

    def slice_graph(
        self,
        tenant_id: uuid.UUID,
        request: GraphSliceRequest,
    ) -> GraphSliceResponse:
        objects = self._fabric._objects
        links = self._fabric._links

        visited: dict[uuid.UUID, int] = {}
        collected_edges: list[GraphEdgeData] = []
        queue: deque[tuple[uuid.UUID, int]] = deque()

        for root_id in request.root_ids:
            if root_id in objects and objects[root_id]["tenant_id"] == tenant_id:
                queue.append((root_id, 0))
                visited[root_id] = 0

        depth_reached = 0
        truncated = False

        while queue:
            current_id, depth = queue.popleft()
            if depth > depth_reached:
                depth_reached = depth

            if len(visited) >= request.max_nodes:
                truncated = True
                break

            for link in links.values():
                neighbor_id = None
                if link["source_id"] == current_id:
                    neighbor_id = link["target_id"]
                elif link["target_id"] == current_id:
                    neighbor_id = link["source_id"]

                if neighbor_id is None:
                    continue

                if request.allowed_link_types:
                    if link["link_type"] not in request.allowed_link_types:
                        continue
                if link["weight"] < request.min_weight:
                    continue

                neighbor = objects.get(neighbor_id)
                if neighbor is None or neighbor["tenant_id"] != tenant_id:
                    continue
                if request.allowed_planes and neighbor["plane"] not in request.allowed_planes:
                    continue

                lt = link["link_type"]
                collected_edges.append(
                    GraphEdgeData(
                        link_id=link["id"],
                        source_id=link["source_id"],
                        target_id=link["target_id"],
                        link_type=lt,
                        weight=link["weight"],
                    )
                )

                if neighbor_id not in visited and depth + 1 <= request.max_depth:
                    visited[neighbor_id] = depth + 1
                    queue.append((neighbor_id, depth + 1))

        nodes = []
        for oid, d in visited.items():
            obj = objects.get(oid)
            if obj:
                nodes.append(
                    GraphNodeData(
                        object_id=oid,
                        control_type=obj["control_type"],
                        plane=obj["plane"],
                        domain=obj["domain"],
                        label=obj["label"],
                        confidence=obj["confidence"],
                        status=obj["status"].value
                        if hasattr(obj["status"], "value")
                        else str(obj["status"]),
                        tags=obj.get("tags", []),
                        depth=d,
                    )
                )

        slice_id = uuid.uuid4()
        result = GraphSliceResponse(
            slice_id=slice_id,
            nodes=nodes,
            edges=collected_edges,
            root_ids=request.root_ids,
            depth_reached=depth_reached,
            policy_used=request.policy,
            truncated=truncated,
        )
        self._slices[slice_id] = {
            "response": result,
            "tenant_id": tenant_id,
            "created_at": datetime.now(UTC),
        }
        return result

    def get_slice(self, slice_id: uuid.UUID) -> GraphSliceResponse | None:
        entry = self._slices.get(slice_id)
        return entry["response"] if entry else None

    # ── Traversal ──────────────────────────────────────────────

    def find_path(
        self,
        tenant_id: uuid.UUID,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        max_depth: int = 10,
    ) -> GraphTraversalResult | None:
        objects = self._fabric._objects
        links = self._fabric._links

        if source_id not in objects or target_id not in objects:
            return None

        queue: deque[tuple[uuid.UUID, list[uuid.UUID], float, list, list]] = deque()
        queue.append((source_id, [source_id], 0.0, [], []))
        visited: set[uuid.UUID] = {source_id}

        while queue:
            current, path, weight, lt_list, planes_list = queue.popleft()

            if current == target_id:
                return GraphTraversalResult(
                    path=path,
                    total_weight=weight,
                    link_types_traversed=lt_list,
                    planes_crossed=list(dict.fromkeys(planes_list)),
                )

            if len(path) > max_depth:
                continue

            for link in links.values():
                neighbor_id = None
                if link["source_id"] == current:
                    neighbor_id = link["target_id"]
                elif link["target_id"] == current:
                    neighbor_id = link["source_id"]

                if neighbor_id is None or neighbor_id in visited:
                    continue

                neighbor = objects.get(neighbor_id)
                if neighbor is None or neighbor["tenant_id"] != tenant_id:
                    continue

                visited.add(neighbor_id)
                plane = (
                    neighbor["plane"].value
                    if hasattr(neighbor["plane"], "value")
                    else str(neighbor["plane"])
                )
                queue.append(
                    (
                        neighbor_id,
                        path + [neighbor_id],
                        weight + link["weight"],
                        lt_list + [link["link_type"]],
                        planes_list + [ControlPlane(plane)],
                    )
                )

        return None

    # ── Analytics ──────────────────────────────────────────────

    def get_analytics(
        self,
        tenant_id: uuid.UUID,
        snapshot_id: uuid.UUID | None = None,
    ) -> GraphAnalytics:
        if snapshot_id and snapshot_id in self._snapshots:
            nodes = self._snapshot_nodes.get(snapshot_id, [])
            edges = self._snapshot_edges.get(snapshot_id, [])
        else:
            objs, _ = self._fabric.query_objects(tenant_id)
            nodes = [{"object_id": o.id, "plane": o.plane, "domain": o.domain} for o in objs]
            edges = []
            obj_ids = {o.id for o in objs}
            for oid in obj_ids:
                for link in self._fabric.get_links_for_object(oid, direction="outgoing"):
                    if link.target_id in obj_ids:
                        edges.append(
                            {
                                "source_id": link.source_id,
                                "target_id": link.target_id,
                                "link_type": link.link_type,
                            }
                        )

        by_plane: dict[str, int] = {}
        for n in nodes:
            p = n["plane"].value if hasattr(n["plane"], "value") else str(n["plane"])
            by_plane[p] = by_plane.get(p, 0) + 1

        by_link_type: dict[str, int] = {}
        cross_plane = 0
        contradiction_count = 0
        for e in edges:
            lt = e["link_type"].value if hasattr(e["link_type"], "value") else str(e["link_type"])
            by_link_type[lt] = by_link_type.get(lt, 0) + 1
            if lt == "contradicts":
                contradiction_count += 1

            src_obj = self._fabric._objects.get(e["source_id"])
            tgt_obj = self._fabric._objects.get(e["target_id"])
            if src_obj and tgt_obj and src_obj["plane"] != tgt_obj["plane"]:
                cross_plane += 1

        node_count = len(nodes)
        edge_count = len(edges)

        degree_sum = 0
        if node_count > 0:
            node_ids = {n["object_id"] if "object_id" in n else n.get("id") for n in nodes}
            for e in edges:
                if e["source_id"] in node_ids:
                    degree_sum += 1
                if e["target_id"] in node_ids:
                    degree_sum += 1
            avg_degree = degree_sum / node_count
        else:
            avg_degree = 0.0

        return GraphAnalytics(
            snapshot_id=snapshot_id or uuid.UUID(int=0),
            node_count=node_count,
            edge_count=edge_count,
            connected_components=1 if node_count > 0 else 0,
            avg_degree=avg_degree,
            max_depth=0,
            cross_plane_edges=cross_plane,
            contradiction_count=contradiction_count,
            by_plane=by_plane,
            by_link_type=by_link_type,
        )
