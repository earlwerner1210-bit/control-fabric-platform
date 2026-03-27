"""Fabric-native API routes — not generic CRUD wrappers."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.action.types import ActionMode, ActionType
from app.core.control_link import ControlLinkCreate
from app.core.control_object import ControlObjectCreate
from app.core.fabric_service import ControlFabricService
from app.core.types import (
    ControlLinkType,
    ControlObjectId,
    ControlState,
    PlaneType,
)

router = APIRouter(prefix="/fabric", tags=["fabric-core"])


# ── Request / Response schemas ────────────────────────────────────


class CreateObjectRequest(BaseModel):
    tenant_id: uuid.UUID
    object_type: str
    object_kind: str = ""
    plane: str
    domain: str
    label: str
    description: str | None = None
    confidence: float = 1.0
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_keys: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class CreateLinkRequest(BaseModel):
    tenant_id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    link_type: str
    weight: float = 1.0
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReconcileRequest(BaseModel):
    tenant_id: uuid.UUID
    source_plane: str
    target_plane: str
    domain: str


class ProposeActionRequest(BaseModel):
    tenant_id: uuid.UUID
    action_type: str
    target_object_ids: list[uuid.UUID]
    mode: str = "approval_gated"
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class ApproveActionRequest(BaseModel):
    approver: str


class RejectActionRequest(BaseModel):
    reason: str = ""


# ── Service instance (DI in real app) ────────────────────────────

_service: ControlFabricService | None = None


def get_service() -> ControlFabricService:
    global _service
    if _service is None:
        _service = ControlFabricService()
    return _service


def set_service(svc: ControlFabricService) -> None:
    global _service
    _service = svc


# ── Object endpoints ─────────────────────────────────────────────


@router.post("/objects")
def create_object(req: CreateObjectRequest) -> dict[str, Any]:
    svc = get_service()
    try:
        from app.core.types import ControlObjectType

        obj = svc.graph.create_object(
            tenant_id=req.tenant_id,
            create=ControlObjectCreate(
                object_type=ControlObjectType(req.object_type),
                object_kind=req.object_kind,
                plane=PlaneType(req.plane),
                domain=req.domain,
                label=req.label,
                description=req.description,
                confidence=req.confidence,
                payload=req.payload,
                correlation_keys=req.correlation_keys,
                tags=req.tags,
            ),
        )
        return {"id": str(obj.id), "state": obj.state.value, "label": obj.label}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/objects/{object_id}")
def get_object(object_id: uuid.UUID) -> dict[str, Any]:
    svc = get_service()
    obj = svc.graph.get_object(ControlObjectId(object_id))
    if obj is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return obj.model_dump(mode="json")


@router.get("/objects")
def list_objects(
    tenant_id: uuid.UUID,
    plane: str | None = None,
    domain: str | None = None,
    state: str | None = None,
) -> list[dict[str, Any]]:
    svc = get_service()
    objects = svc.graph.list_objects(
        tenant_id=tenant_id,
        plane=PlaneType(plane) if plane else None,
        domain=domain,
        state=ControlState(state) if state else None,
    )
    return [
        {"id": str(o.id), "label": o.label, "state": o.state.value, "plane": o.plane.value}
        for o in objects
    ]


@router.post("/objects/{object_id}/freeze")
def freeze_object(object_id: uuid.UUID) -> dict[str, Any]:
    svc = get_service()
    obj = svc.graph.freeze_object(ControlObjectId(object_id))
    if obj is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return {"id": str(obj.id), "state": obj.state.value}


@router.post("/objects/{object_id}/enrich")
def enrich_object(object_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
    svc = get_service()
    obj = svc.graph.enrich_object(ControlObjectId(object_id), payload)
    if obj is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return {"id": str(obj.id), "state": obj.state.value}


# ── Link endpoints ───────────────────────────────────────────────


@router.post("/links")
def create_link(req: CreateLinkRequest) -> dict[str, Any]:
    svc = get_service()
    try:
        link = svc.graph.create_link(
            tenant_id=req.tenant_id,
            create=ControlLinkCreate(
                source_id=req.source_id,
                target_id=req.target_id,
                link_type=ControlLinkType(req.link_type),
                weight=req.weight,
                confidence=req.confidence,
                metadata=req.metadata,
            ),
        )
        return {
            "id": str(link.id),
            "link_type": link.link_type.value,
            "is_cross_plane": link.is_cross_plane,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/objects/{object_id}/links")
def get_links(
    object_id: uuid.UUID,
    direction: str = "both",
) -> list[dict[str, Any]]:
    svc = get_service()
    links = svc.graph.get_links_for_object(ControlObjectId(object_id), direction)
    return [
        {
            "id": str(l.id),
            "source_id": str(l.source_id),
            "target_id": str(l.target_id),
            "link_type": l.link_type.value,
        }
        for l in links
    ]


@router.get("/objects/{object_id}/neighbours")
def get_neighbours(
    object_id: uuid.UUID,
    direction: str = "both",
) -> list[dict[str, Any]]:
    svc = get_service()
    neighbours = svc.graph.get_neighbours(ControlObjectId(object_id), direction)
    return [{"id": str(n.id), "label": n.label, "plane": n.plane.value} for n in neighbours]


# ── Reconciliation endpoints ─────────────────────────────────────


@router.post("/reconcile")
def reconcile(req: ReconcileRequest) -> dict[str, Any]:
    svc = get_service()
    result = svc.reconcile_planes(
        tenant_id=req.tenant_id,
        source_plane=PlaneType(req.source_plane),
        target_plane=PlaneType(req.target_plane),
        domain=req.domain,
    )
    return {
        "id": str(result.id),
        "status": result.status.value,
        "mismatch_count": result.score.mismatch_count,
        "overall_score": result.score.overall_score,
        "decision_hash": result.decision_hash,
    }


# ── Consistency endpoints ────────────────────────────────────────


@router.get("/consistency/{tenant_id}")
def check_consistency(
    tenant_id: uuid.UUID,
    plane: str | None = None,
) -> dict[str, Any]:
    svc = get_service()
    report = svc.graph.check_consistency(tenant_id, PlaneType(plane) if plane else None)
    return {
        "total_objects": report.total_objects,
        "total_links": report.total_links,
        "is_consistent": report.is_consistent,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "issues": [i.model_dump(mode="json") for i in report.issues],
    }


# ── Action endpoints ─────────────────────────────────────────────


@router.post("/actions/propose")
def propose_action(req: ProposeActionRequest) -> dict[str, Any]:
    svc = get_service()
    try:
        proposal = svc.propose_action(
            tenant_id=req.tenant_id,
            action_type=ActionType(req.action_type),
            target_object_ids=[ControlObjectId(oid) for oid in req.target_object_ids],
            mode=ActionMode(req.mode),
            parameters=req.parameters,
            description=req.description,
        )
        return {
            "id": str(proposal.id),
            "status": proposal.status.value,
            "eligibility": proposal.eligibility.value,
            "decision_hash": proposal.manifest.decision_hash,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/actions/{proposal_id}/approve")
def approve_action(proposal_id: uuid.UUID, req: ApproveActionRequest) -> dict[str, Any]:
    svc = get_service()
    try:
        proposal = svc.action.approve_action(proposal_id, req.approver)
        return {"id": str(proposal.id), "status": proposal.status.value}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/actions/{proposal_id}/reject")
def reject_action(proposal_id: uuid.UUID, req: RejectActionRequest) -> dict[str, Any]:
    svc = get_service()
    try:
        proposal = svc.action.reject_action(proposal_id, req.reason)
        return {"id": str(proposal.id), "status": proposal.status.value}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/actions/{proposal_id}/release")
def release_action(proposal_id: uuid.UUID) -> dict[str, Any]:
    svc = get_service()
    try:
        proposal = svc.action.release_action(proposal_id)
        return {"id": str(proposal.id), "status": proposal.status.value}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
