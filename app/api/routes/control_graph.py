"""API routes for Control Graph — snapshots, slicing, analytics."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.control_graph import (
    GraphAnalytics,
    GraphSliceRequest,
    GraphSliceResponse,
    GraphSnapshotCreate,
    GraphSnapshotResponse,
)

router = APIRouter(prefix="/control-graph", tags=["control-graph"])


@router.post("/snapshots", response_model=GraphSnapshotResponse, status_code=201)
def create_snapshot(create: GraphSnapshotCreate) -> GraphSnapshotResponse:
    from app.services.control_fabric import ControlFabricService
    from app.services.control_graph import ControlGraphService

    fabric_svc = ControlFabricService()
    graph_svc = ControlGraphService(fabric_svc)
    return graph_svc.create_snapshot(create)


@router.get("/snapshots/{snapshot_id}", response_model=GraphSnapshotResponse)
def get_snapshot(snapshot_id: uuid.UUID) -> GraphSnapshotResponse:
    from app.services.control_fabric import ControlFabricService
    from app.services.control_graph import ControlGraphService

    fabric_svc = ControlFabricService()
    graph_svc = ControlGraphService(fabric_svc)
    result = graph_svc.get_snapshot(snapshot_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return result


@router.post("/slice", response_model=GraphSliceResponse)
def slice_graph(
    tenant_id: uuid.UUID,
    request: GraphSliceRequest,
) -> GraphSliceResponse:
    from app.services.control_fabric import ControlFabricService
    from app.services.control_graph import ControlGraphService

    fabric_svc = ControlFabricService()
    graph_svc = ControlGraphService(fabric_svc)
    return graph_svc.slice_graph(tenant_id, request)


@router.get("/analytics", response_model=GraphAnalytics)
def get_analytics(
    tenant_id: uuid.UUID,
    snapshot_id: uuid.UUID | None = None,
) -> GraphAnalytics:
    from app.services.control_fabric import ControlFabricService
    from app.services.control_graph import ControlGraphService

    fabric_svc = ControlFabricService()
    graph_svc = ControlGraphService(fabric_svc)
    return graph_svc.get_analytics(tenant_id, snapshot_id)
