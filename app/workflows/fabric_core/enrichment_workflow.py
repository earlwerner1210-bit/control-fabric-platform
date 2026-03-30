"""Object enrichment workflow — enrich objects, attach evidence, link."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.control_link import ControlLinkCreate
from app.core.fabric_service import ControlFabricService
from app.core.types import (
    ControlLinkType,
    ControlObjectId,
    EvidenceRef,
)
from app.workflows.fabric_core.activities import create_link_activity


class ObjectEnrichmentWorkflow:
    """Workflow: enrich objects with payload, attach evidence, create links."""

    def __init__(self, service: ControlFabricService) -> None:
        self._service = service

    def run(
        self,
        tenant_id: uuid.UUID,
        object_id: uuid.UUID,
        payload_updates: dict[str, Any],
        evidence: list[dict[str, Any]] | None = None,
        link_targets: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        # Step 1: Enrich object
        obj = self._service.graph.enrich_object(ControlObjectId(object_id), payload_updates)
        if obj is None:
            return {"status": "error", "message": "Object not found"}

        # Step 2: Attach evidence
        evidence_count = 0
        if evidence:
            for ev in evidence:
                ref = EvidenceRef(
                    evidence_type=ev.get("evidence_type", "document"),
                    source_label=ev.get("source_label", "unknown"),
                )
                obj.attach_evidence(ref)
                evidence_count += 1
            self._service.graph.repository.store_object(obj)

        # Step 3: Create links
        links_created: list[dict[str, Any]] = []
        if link_targets:
            for lt in link_targets:
                link_result = create_link_activity(
                    self._service,
                    tenant_id,
                    object_id,
                    uuid.UUID(lt["target_id"]),
                    lt.get("link_type", "correlates_with"),
                )
                links_created.append(link_result)

        return {
            "status": "enriched",
            "object_id": str(obj.id),
            "state": obj.state.value,
            "evidence_attached": evidence_count,
            "links_created": len(links_created),
        }
