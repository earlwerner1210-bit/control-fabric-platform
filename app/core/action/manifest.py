"""Action manifest builder — constructs reproducible action manifests."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.action.types import ActionManifest, ActionType
from app.core.control_object import ControlObject
from app.core.types import ControlObjectId, EvidenceRef


def build_manifest(
    tenant_id: uuid.UUID,
    action_type: ActionType,
    objects: list[ControlObject],
    parameters: dict[str, Any] | None = None,
    validation_result_id: uuid.UUID | None = None,
    reasoning_result_id: uuid.UUID | None = None,
    reconciliation_result_id: uuid.UUID | None = None,
) -> ActionManifest:
    """Build an action manifest from objects, collecting all evidence."""
    all_evidence: list[EvidenceRef] = []
    target_ids: list[ControlObjectId] = []

    for obj in objects:
        target_ids.append(obj.id)
        all_evidence.extend(obj.evidence)

    manifest = ActionManifest(
        tenant_id=tenant_id,
        action_type=action_type,
        target_object_ids=target_ids,
        evidence_refs=all_evidence,
        validation_result_id=validation_result_id,
        reasoning_result_id=reasoning_result_id,
        reconciliation_result_id=reconciliation_result_id,
        parameters=parameters or {},
    )
    manifest.compute_hash()
    return manifest
