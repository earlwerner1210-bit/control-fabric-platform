"""API routes for Control Fabric — object registration, linking, querying, slicing."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.control_fabric import (
    FabricLinkCreate,
    FabricLinkResponse,
    FabricObjectCreate,
    FabricObjectResponse,
    FabricQueryFilter,
    FabricSliceRequest,
    FabricSliceResponse,
    FabricStats,
)

router = APIRouter(prefix="/control-fabric", tags=["control-fabric"])


@router.post("/objects", response_model=FabricObjectResponse, status_code=201)
def register_object(
    tenant_id: uuid.UUID,
    create: FabricObjectCreate,
) -> FabricObjectResponse:
    from app.services.control_fabric import ControlFabricService

    svc = ControlFabricService()
    return svc.register_object(tenant_id, create)


@router.get("/objects/{object_id}", response_model=FabricObjectResponse)
def get_object(object_id: uuid.UUID) -> FabricObjectResponse:
    from app.services.control_fabric import ControlFabricService

    svc = ControlFabricService()
    result = svc.get_object(object_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return result


@router.post("/objects/query", response_model=dict)
def query_objects(
    tenant_id: uuid.UUID,
    filter: FabricQueryFilter | None = None,
) -> dict:
    from app.services.control_fabric import ControlFabricService

    svc = ControlFabricService()
    objects, total = svc.query_objects(tenant_id, filter)
    return {"items": objects, "total": total}


@router.post("/links", response_model=FabricLinkResponse, status_code=201)
def create_link(
    tenant_id: uuid.UUID,
    create: FabricLinkCreate,
) -> FabricLinkResponse:
    from app.services.control_fabric import ControlFabricService

    svc = ControlFabricService()
    return svc.link_objects(tenant_id, create)


@router.post("/slice", response_model=FabricSliceResponse)
def build_slice(
    tenant_id: uuid.UUID,
    request: FabricSliceRequest,
) -> FabricSliceResponse:
    from app.services.control_fabric import ControlFabricService

    svc = ControlFabricService()
    return svc.build_slice(tenant_id, request)


@router.get("/stats", response_model=FabricStats)
def get_stats(tenant_id: uuid.UUID) -> FabricStats:
    from app.services.control_fabric import ControlFabricService

    svc = ControlFabricService()
    return svc.get_stats(tenant_id)
