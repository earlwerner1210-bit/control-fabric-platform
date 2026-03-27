"""Governed action release workflow — validate, propose, gate, release."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.action.types import ActionMode, ActionType
from app.core.fabric_service import ControlFabricService
from app.core.types import ControlObjectId
from app.workflows.fabric_core.activities import (
    propose_action_activity,
    validate_for_action_activity,
)


class GovernedActionReleaseWorkflow:
    """Workflow: validate → propose → approve/auto → release."""

    def __init__(self, service: ControlFabricService) -> None:
        self._service = service

    def run(
        self,
        tenant_id: uuid.UUID,
        action_type: str,
        target_object_ids: list[str],
        mode: str = "approval_gated",
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Step 1: Validate
        validation = validate_for_action_activity(
            self._service, tenant_id, target_object_ids, action_type
        )

        if not validation["is_actionable"]:
            return {
                "status": "validation_failed",
                "validation": validation,
            }

        # Step 2: Propose action
        proposal = propose_action_activity(
            self._service,
            tenant_id,
            action_type,
            target_object_ids,
            mode,
            parameters,
        )

        # Step 3: Auto-release if mode allows
        if mode == "auto_release":
            proposal_id = uuid.UUID(proposal["proposal_id"])
            released = self._service.action.release_action(proposal_id)
            return {
                "status": "released",
                "proposal": proposal,
                "released_status": released.status.value,
            }

        return {
            "status": "proposed",
            "validation": validation,
            "proposal": proposal,
        }
