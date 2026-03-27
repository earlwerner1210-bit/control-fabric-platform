"""Graph consistency audit workflow — full graph health check."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.fabric_service import ControlFabricService
from app.core.types import PlaneType
from app.workflows.fabric_core.activities import check_consistency_activity


class GraphConsistencyAuditWorkflow:
    """Workflow: run consistency checks across all planes, produce report."""

    def __init__(self, service: ControlFabricService) -> None:
        self._service = service

    def run(
        self,
        tenant_id: uuid.UUID,
    ) -> dict[str, Any]:
        # Step 1: Full graph consistency
        full_report = check_consistency_activity(self._service, tenant_id)

        # Step 2: Per-plane consistency
        plane_reports: dict[str, Any] = {}
        for plane in PlaneType:
            plane_report = check_consistency_activity(self._service, tenant_id, plane.value)
            plane_reports[plane.value] = plane_report

        # Step 3: Contradictions
        contradictions = self._service.graph.get_contradictions(tenant_id)

        return {
            "full_report": full_report,
            "plane_reports": plane_reports,
            "contradiction_count": len(contradictions),
            "contradictions": [
                {
                    "source_id": str(c.source_id),
                    "target_id": str(c.target_id),
                }
                for c in contradictions
            ],
        }
