"""Shared activities for fabric-native workflows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.action.types import ActionMode, ActionType
from app.core.control_link import ControlLinkCreate
from app.core.control_object import ControlObjectCreate
from app.core.fabric_service import ControlFabricService
from app.core.types import (
    AuditContext,
    ControlLinkType,
    ControlObjectId,
    ControlObjectType,
    ControlState,
    EvidenceRef,
    PlaneType,
)


def create_control_object_activity(
    service: ControlFabricService,
    tenant_id: uuid.UUID,
    object_type: str,
    plane: str,
    domain: str,
    label: str,
    payload: dict[str, Any] | None = None,
    object_kind: str = "",
) -> dict[str, Any]:
    obj = service.graph.create_object(
        tenant_id=tenant_id,
        create=ControlObjectCreate(
            object_type=ControlObjectType(object_type),
            object_kind=object_kind,
            plane=PlaneType(plane),
            domain=domain,
            label=label,
            payload=payload or {},
        ),
    )
    return {"object_id": str(obj.id), "state": obj.state.value}


def create_link_activity(
    service: ControlFabricService,
    tenant_id: uuid.UUID,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    link_type: str,
) -> dict[str, Any]:
    link = service.graph.create_link(
        tenant_id=tenant_id,
        create=ControlLinkCreate(
            source_id=source_id,
            target_id=target_id,
            link_type=ControlLinkType(link_type),
        ),
    )
    return {"link_id": str(link.id), "is_cross_plane": link.is_cross_plane}


def freeze_object_activity(
    service: ControlFabricService,
    object_id: uuid.UUID,
) -> dict[str, Any]:
    obj = service.graph.freeze_object(ControlObjectId(object_id))
    if obj is None:
        return {"error": "Object not found"}
    return {"object_id": str(obj.id), "state": obj.state.value}


def reconcile_planes_activity(
    service: ControlFabricService,
    tenant_id: uuid.UUID,
    source_plane: str,
    target_plane: str,
    domain: str,
) -> dict[str, Any]:
    result = service.reconcile_planes(
        tenant_id=tenant_id,
        source_plane=PlaneType(source_plane),
        target_plane=PlaneType(target_plane),
        domain=domain,
    )
    return {
        "result_id": str(result.id),
        "mismatch_count": result.score.mismatch_count,
        "overall_score": result.score.overall_score,
        "decision_hash": result.decision_hash,
    }


def validate_for_action_activity(
    service: ControlFabricService,
    tenant_id: uuid.UUID,
    target_object_ids: list[str],
    action_type: str = "",
) -> dict[str, Any]:
    oids = [ControlObjectId(uuid.UUID(oid)) for oid in target_object_ids]
    result = service.validate_for_action(tenant_id, oids, action_type)
    return {
        "validation_id": str(result.id),
        "outcome": result.outcome.value,
        "passed": result.passed_count,
        "failed": result.failed_count,
        "warnings": result.warning_count,
        "is_actionable": result.is_actionable,
    }


def propose_action_activity(
    service: ControlFabricService,
    tenant_id: uuid.UUID,
    action_type: str,
    target_object_ids: list[str],
    mode: str = "approval_gated",
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    oids = [ControlObjectId(uuid.UUID(oid)) for oid in target_object_ids]
    proposal = service.propose_action(
        tenant_id=tenant_id,
        action_type=ActionType(action_type),
        target_object_ids=oids,
        mode=ActionMode(mode),
        parameters=parameters,
    )
    return {
        "proposal_id": str(proposal.id),
        "status": proposal.status.value,
        "decision_hash": proposal.manifest.decision_hash,
    }


def check_consistency_activity(
    service: ControlFabricService,
    tenant_id: uuid.UUID,
    plane: str | None = None,
) -> dict[str, Any]:
    report = service.graph.check_consistency(tenant_id, PlaneType(plane) if plane else None)
    return {
        "is_consistent": report.is_consistent,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "total_objects": report.total_objects,
        "total_links": report.total_links,
    }
