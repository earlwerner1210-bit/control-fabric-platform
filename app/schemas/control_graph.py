"""Control Graph schemas — graph snapshots, slicing, traversal."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.control_fabric import ControlLinkType, ControlPlane


class GraphSnapshotStatus(str, enum.Enum):
    BUILDING = "building"
    READY = "ready"
    STALE = "stale"
    ERROR = "error"


class GraphNodeData(BaseModel):
    object_id: uuid.UUID
    control_type: str
    plane: ControlPlane
    domain: str
    label: str
    confidence: float
    status: str
    tags: list[str] = Field(default_factory=list)
    depth: int = 0


class GraphEdgeData(BaseModel):
    link_id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    link_type: ControlLinkType
    weight: float


class GraphSnapshotCreate(BaseModel):
    tenant_id: uuid.UUID
    label: str | None = None
    scope_planes: list[ControlPlane] = Field(default_factory=list)
    scope_domains: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    label: str | None
    status: GraphSnapshotStatus
    node_count: int
    edge_count: int
    scope_planes: list[str]
    scope_domains: list[str]
    metadata: dict[str, Any]
    created_at: datetime


class GraphSlicePolicy(str, enum.Enum):
    BFS = "bfs"
    DFS = "dfs"
    WEIGHTED = "weighted"
    PLANE_BOUNDED = "plane_bounded"


class GraphSliceRequest(BaseModel):
    root_ids: list[uuid.UUID]
    max_depth: int = Field(ge=1, le=10, default=3)
    policy: GraphSlicePolicy = GraphSlicePolicy.BFS
    allowed_planes: list[ControlPlane] = Field(default_factory=list)
    allowed_link_types: list[ControlLinkType] = Field(default_factory=list)
    min_weight: float = 0.0
    max_nodes: int = Field(ge=1, le=500, default=100)
    include_metadata: bool = False


class GraphSliceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slice_id: uuid.UUID
    nodes: list[GraphNodeData]
    edges: list[GraphEdgeData]
    root_ids: list[uuid.UUID]
    depth_reached: int
    policy_used: GraphSlicePolicy
    truncated: bool = False


class GraphTraversalResult(BaseModel):
    path: list[uuid.UUID]
    total_weight: float
    link_types_traversed: list[ControlLinkType]
    planes_crossed: list[ControlPlane]


class GraphAnalytics(BaseModel):
    snapshot_id: uuid.UUID
    node_count: int
    edge_count: int
    connected_components: int
    avg_degree: float
    max_depth: int
    cross_plane_edges: int
    contradiction_count: int
    by_plane: dict[str, int] = Field(default_factory=dict)
    by_link_type: dict[str, int] = Field(default_factory=dict)
