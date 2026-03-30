"""Control Fabric Service — register, link, query, and slice control objects."""

from __future__ import annotations

import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any

from app.schemas.control_fabric import (
    ControlLinkType,
    ControlObjectStatus,
    ControlPlane,
    FabricLinkCreate,
    FabricLinkResponse,
    FabricObjectCreate,
    FabricObjectResponse,
    FabricQueryFilter,
    FabricSliceRequest,
    FabricSliceResponse,
    FabricStats,
)


class ControlFabricService:
    """In-memory control fabric for registering, linking, and querying control objects."""

    def __init__(self) -> None:
        self._objects: dict[uuid.UUID, dict[str, Any]] = {}
        self._links: dict[uuid.UUID, dict[str, Any]] = {}

    # ── Registration ───────────────────────────────────────────

    def register_object(
        self,
        tenant_id: uuid.UUID,
        create: FabricObjectCreate,
    ) -> FabricObjectResponse:
        obj_id = uuid.uuid4()
        now = datetime.now(UTC)
        obj = {
            "id": obj_id,
            "tenant_id": tenant_id,
            "control_type": create.control_type,
            "plane": create.plane,
            "domain": create.domain,
            "label": create.label,
            "description": create.description,
            "payload": create.payload,
            "source_document_id": create.source_document_id,
            "source_chunk_id": create.source_chunk_id,
            "source_clause_ref": create.source_clause_ref,
            "confidence": create.confidence,
            "status": ControlObjectStatus.ACTIVE,
            "tags": create.tags,
            "metadata": create.metadata,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        self._objects[obj_id] = obj
        return FabricObjectResponse(**obj)

    def get_object(self, object_id: uuid.UUID) -> FabricObjectResponse | None:
        obj = self._objects.get(object_id)
        if obj is None:
            return None
        return FabricObjectResponse(**obj)

    def update_object_status(
        self,
        object_id: uuid.UUID,
        status: ControlObjectStatus,
    ) -> FabricObjectResponse | None:
        obj = self._objects.get(object_id)
        if obj is None:
            return None
        obj["status"] = status
        obj["updated_at"] = datetime.now(UTC)
        obj["version"] += 1
        return FabricObjectResponse(**obj)

    def retire_object(self, object_id: uuid.UUID) -> FabricObjectResponse | None:
        return self.update_object_status(object_id, ControlObjectStatus.RETIRED)

    # ── Linking ────────────────────────────────────────────────

    def link_objects(
        self,
        tenant_id: uuid.UUID,
        create: FabricLinkCreate,
    ) -> FabricLinkResponse:
        link_id = uuid.uuid4()
        now = datetime.now(UTC)
        link = {
            "id": link_id,
            "source_id": create.source_id,
            "target_id": create.target_id,
            "link_type": create.link_type,
            "weight": create.weight,
            "evidence_refs": create.evidence_refs,
            "metadata": create.metadata,
            "tenant_id": tenant_id,
            "created_at": now,
        }
        self._links[link_id] = link
        return FabricLinkResponse(**link)

    def get_links_for_object(
        self,
        object_id: uuid.UUID,
        direction: str = "both",
    ) -> list[FabricLinkResponse]:
        results = []
        for link in self._links.values():
            if (
                direction in ("outgoing", "both")
                and link["source_id"] == object_id
                or direction in ("incoming", "both")
                and link["target_id"] == object_id
            ):
                results.append(FabricLinkResponse(**link))
        return results

    def get_contradictions(
        self,
        tenant_id: uuid.UUID,
    ) -> list[FabricLinkResponse]:
        return [
            FabricLinkResponse(**l)
            for l in self._links.values()
            if l["tenant_id"] == tenant_id and l["link_type"] == ControlLinkType.CONTRADICTS
        ]

    # ── Query ──────────────────────────────────────────────────

    def query_objects(
        self,
        tenant_id: uuid.UUID,
        filter: FabricQueryFilter | None = None,
    ) -> tuple[list[FabricObjectResponse], int]:
        results = [o for o in self._objects.values() if o["tenant_id"] == tenant_id]

        if filter:
            if filter.planes:
                results = [o for o in results if o["plane"] in filter.planes]
            if filter.domains:
                results = [o for o in results if o["domain"] in filter.domains]
            if filter.control_types:
                results = [o for o in results if o["control_type"] in filter.control_types]
            if filter.statuses:
                results = [o for o in results if o["status"] in filter.statuses]
            if filter.tags:
                results = [o for o in results if set(filter.tags) & set(o["tags"])]
            if filter.min_confidence > 0:
                results = [o for o in results if o["confidence"] >= filter.min_confidence]
            if filter.source_document_id:
                results = [
                    o for o in results if o["source_document_id"] == filter.source_document_id
                ]

        total = len(results)
        if filter:
            start = (filter.page - 1) * filter.page_size
            results = results[start : start + filter.page_size]

        return [FabricObjectResponse(**o) for o in results], total

    def get_objects_by_plane(
        self,
        tenant_id: uuid.UUID,
        plane: ControlPlane,
    ) -> list[FabricObjectResponse]:
        return [
            FabricObjectResponse(**o)
            for o in self._objects.values()
            if o["tenant_id"] == tenant_id and o["plane"] == plane
        ]

    # ── Graph Slice ────────────────────────────────────────────

    def build_slice(
        self,
        tenant_id: uuid.UUID,
        request: FabricSliceRequest,
    ) -> FabricSliceResponse:
        visited_ids: set[uuid.UUID] = set()
        collected_links: list[dict[str, Any]] = []
        max_depth = request.max_depth
        depth_reached = 0

        queue: deque[tuple[uuid.UUID, int]] = deque()
        for root_id in request.root_ids:
            if root_id in self._objects:
                queue.append((root_id, 0))
                visited_ids.add(root_id)

        while queue:
            current_id, depth = queue.popleft()
            if depth > depth_reached:
                depth_reached = depth

            for link in self._links.values():
                neighbor_id = None
                if link["source_id"] == current_id:
                    neighbor_id = link["target_id"]
                elif link["target_id"] == current_id:
                    neighbor_id = link["source_id"]

                if neighbor_id is None:
                    continue

                if request.link_types and link["link_type"] not in request.link_types:
                    continue

                neighbor = self._objects.get(neighbor_id)
                if neighbor is None:
                    continue
                if neighbor["tenant_id"] != tenant_id:
                    continue
                if request.planes and neighbor["plane"] not in request.planes:
                    continue
                if request.domains and neighbor["domain"] not in request.domains:
                    continue
                if (
                    not request.include_retired
                    and neighbor["status"] == ControlObjectStatus.RETIRED
                ):
                    continue

                collected_links.append(link)

                if neighbor_id not in visited_ids and depth + 1 <= max_depth:
                    visited_ids.add(neighbor_id)
                    queue.append((neighbor_id, depth + 1))

        objects = [
            FabricObjectResponse(**self._objects[oid])
            for oid in visited_ids
            if oid in self._objects
        ]
        links = [FabricLinkResponse(**l) for l in collected_links]

        return FabricSliceResponse(
            objects=objects,
            links=links,
            root_ids=request.root_ids,
            total_objects=len(objects),
            total_links=len(links),
            depth_reached=depth_reached,
        )

    # ── Stats ──────────────────────────────────────────────────

    def get_stats(self, tenant_id: uuid.UUID) -> FabricStats:
        objs = [o for o in self._objects.values() if o["tenant_id"] == tenant_id]
        links = [l for l in self._links.values() if l["tenant_id"] == tenant_id]

        by_plane: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for o in objs:
            p = o["plane"].value if hasattr(o["plane"], "value") else str(o["plane"])
            by_plane[p] = by_plane.get(p, 0) + 1
            by_domain[o["domain"]] = by_domain.get(o["domain"], 0) + 1
            by_type[o["control_type"]] = by_type.get(o["control_type"], 0) + 1

        by_link: dict[str, int] = {}
        for l in links:
            lt = l["link_type"].value if hasattr(l["link_type"], "value") else str(l["link_type"])
            by_link[lt] = by_link.get(lt, 0) + 1

        return FabricStats(
            total_objects=len(objs),
            total_links=len(links),
            objects_by_plane=by_plane,
            objects_by_domain=by_domain,
            objects_by_type=by_type,
            links_by_type=by_link,
        )
