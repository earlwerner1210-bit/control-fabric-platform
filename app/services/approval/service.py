"""Approval, override, and escalation service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.approval import (
    ApprovalRequest,
    ApprovalResponse,
    EscalationRequest,
    EscalationResponse,
    OverrideRequest,
    OverrideResponse,
)
from app.schemas.pilot_case import PilotCaseState
from app.services.pilot_cases import PilotCaseService
from app.services.state_machine import CaseStateMachineService


class ApprovalService:
    """Handles approval, override, and escalation for pilot cases."""

    def __init__(self, case_service: PilotCaseService) -> None:
        self._case_service = case_service
        self._state_machine = CaseStateMachineService()
        self._approvals: dict[uuid.UUID, list[dict[str, Any]]] = {}
        self._overrides: dict[uuid.UUID, list[dict[str, Any]]] = {}
        self._escalations: dict[uuid.UUID, list[dict[str, Any]]] = {}

    def approve(
        self,
        pilot_case_id: uuid.UUID,
        actor_id: uuid.UUID,
        data: ApprovalRequest,
    ) -> ApprovalResponse:
        self._case_service.transition_state(
            pilot_case_id,
            PilotCaseState.APPROVED,
            actor_id,
            reason=data.reasoning,
        )

        approval = {
            "id": uuid.uuid4(),
            "pilot_case_id": pilot_case_id,
            "approved_by": actor_id,
            "reasoning": data.reasoning,
            "business_impact_notes": data.business_impact_notes,
            "metadata": data.metadata,
            "created_at": datetime.now(UTC),
        }
        self._approvals.setdefault(pilot_case_id, []).append(approval)
        return ApprovalResponse(**approval)

    def override(
        self,
        pilot_case_id: uuid.UUID,
        actor_id: uuid.UUID,
        data: OverrideRequest,
    ) -> OverrideResponse:
        self._case_service.transition_state(
            pilot_case_id,
            PilotCaseState.OVERRIDDEN,
            actor_id,
            reason=f"{data.override_reason.value}: {data.override_detail}",
        )

        override = {
            "id": uuid.uuid4(),
            "pilot_case_id": pilot_case_id,
            "overridden_by": actor_id,
            "override_reason": data.override_reason,
            "override_detail": data.override_detail,
            "corrected_outcome": data.corrected_outcome,
            "business_impact_notes": data.business_impact_notes,
            "metadata": data.metadata,
            "created_at": datetime.now(UTC),
        }
        self._overrides.setdefault(pilot_case_id, []).append(override)
        return OverrideResponse(**override)

    def escalate(
        self,
        pilot_case_id: uuid.UUID,
        actor_id: uuid.UUID,
        data: EscalationRequest,
    ) -> EscalationResponse:
        self._case_service.transition_state(
            pilot_case_id,
            PilotCaseState.ESCALATED,
            actor_id,
            reason=data.escalation_reason,
        )

        escalation = {
            "id": uuid.uuid4(),
            "pilot_case_id": pilot_case_id,
            "escalated_by": actor_id,
            "escalation_route": data.escalation_route,
            "escalation_reason": data.escalation_reason,
            "urgency": data.urgency,
            "metadata": data.metadata,
            "created_at": datetime.now(UTC),
        }
        self._escalations.setdefault(pilot_case_id, []).append(escalation)
        return EscalationResponse(**escalation)

    def get_approvals(self, pilot_case_id: uuid.UUID) -> list[ApprovalResponse]:
        return [ApprovalResponse(**a) for a in self._approvals.get(pilot_case_id, [])]

    def get_overrides(self, pilot_case_id: uuid.UUID) -> list[OverrideResponse]:
        return [OverrideResponse(**o) for o in self._overrides.get(pilot_case_id, [])]

    def get_escalations(self, pilot_case_id: uuid.UUID) -> list[EscalationResponse]:
        return [EscalationResponse(**e) for e in self._escalations.get(pilot_case_id, [])]
