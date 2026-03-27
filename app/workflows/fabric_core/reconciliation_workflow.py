"""Fabric reconciliation workflow — freeze, reconcile, report."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.fabric_service import ControlFabricService
from app.core.types import ControlObjectId, ControlState, PlaneType
from app.workflows.fabric_core.activities import (
    check_consistency_activity,
    freeze_object_activity,
    reconcile_planes_activity,
)


class FabricReconciliationWorkflow:
    """Workflow: freeze eligible objects → run cross-plane reconciliation → consistency check."""

    def __init__(self, service: ControlFabricService) -> None:
        self._service = service

    def run(
        self,
        tenant_id: uuid.UUID,
        source_plane: str,
        target_plane: str,
        domain: str,
    ) -> dict[str, Any]:
        # Step 1: Freeze all active/enriched objects in source plane
        source_objects = self._service.graph.list_objects(
            tenant_id, plane=PlaneType(source_plane), domain=domain
        )
        frozen_ids: list[str] = []
        for obj in source_objects:
            if obj.state in (ControlState.ACTIVE, ControlState.ENRICHED):
                result = freeze_object_activity(self._service, obj.id)
                if "error" not in result:
                    frozen_ids.append(result["object_id"])

        # Step 2: Freeze target plane objects
        target_objects = self._service.graph.list_objects(
            tenant_id, plane=PlaneType(target_plane), domain=domain
        )
        for obj in target_objects:
            if obj.state in (ControlState.ACTIVE, ControlState.ENRICHED):
                result = freeze_object_activity(self._service, obj.id)
                if "error" not in result:
                    frozen_ids.append(result["object_id"])

        # Step 3: Run reconciliation
        recon_result = reconcile_planes_activity(
            self._service, tenant_id, source_plane, target_plane, domain
        )

        # Step 4: Consistency check
        consistency = check_consistency_activity(self._service, tenant_id)

        return {
            "frozen_count": len(frozen_ids),
            "reconciliation": recon_result,
            "consistency": consistency,
        }
