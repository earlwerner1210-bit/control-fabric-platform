"""Case state machine — controls valid transitions and records audit."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.pilot_case import PilotCaseState

# Valid state transitions map
VALID_TRANSITIONS: dict[PilotCaseState, list[PilotCaseState]] = {
    PilotCaseState.CREATED: [
        PilotCaseState.EVIDENCE_READY,
        PilotCaseState.CLOSED,
    ],
    PilotCaseState.EVIDENCE_READY: [
        PilotCaseState.WORKFLOW_EXECUTED,
        PilotCaseState.CLOSED,
    ],
    PilotCaseState.WORKFLOW_EXECUTED: [
        PilotCaseState.VALIDATION_COMPLETED,
        PilotCaseState.CLOSED,
    ],
    PilotCaseState.VALIDATION_COMPLETED: [
        PilotCaseState.UNDER_REVIEW,
        PilotCaseState.APPROVED,
        PilotCaseState.CLOSED,
    ],
    PilotCaseState.UNDER_REVIEW: [
        PilotCaseState.APPROVED,
        PilotCaseState.OVERRIDDEN,
        PilotCaseState.ESCALATED,
        PilotCaseState.CLOSED,
    ],
    PilotCaseState.APPROVED: [
        PilotCaseState.EXPORTED,
        PilotCaseState.CLOSED,
    ],
    PilotCaseState.OVERRIDDEN: [
        PilotCaseState.EXPORTED,
        PilotCaseState.UNDER_REVIEW,
        PilotCaseState.CLOSED,
    ],
    PilotCaseState.ESCALATED: [
        PilotCaseState.UNDER_REVIEW,
        PilotCaseState.APPROVED,
        PilotCaseState.OVERRIDDEN,
        PilotCaseState.CLOSED,
    ],
    PilotCaseState.EXPORTED: [
        PilotCaseState.CLOSED,
    ],
    PilotCaseState.CLOSED: [],
}


class InvalidTransitionError(Exception):
    def __init__(self, from_state: PilotCaseState, to_state: PilotCaseState):
        self.from_state = from_state
        self.to_state = to_state
        valid = VALID_TRANSITIONS.get(from_state, [])
        valid_str = ", ".join(s.value for s in valid) if valid else "none"
        super().__init__(
            f"Invalid transition from '{from_state.value}' to '{to_state.value}'. "
            f"Valid transitions: {valid_str}"
        )


class CaseStateMachineService:
    """Controls pilot case state transitions with validation and audit."""

    def get_valid_transitions(self, current_state: PilotCaseState) -> list[PilotCaseState]:
        return VALID_TRANSITIONS.get(current_state, [])

    def validate_transition(self, from_state: PilotCaseState, to_state: PilotCaseState) -> bool:
        valid = VALID_TRANSITIONS.get(from_state, [])
        return to_state in valid

    def transition(
        self,
        from_state: PilotCaseState,
        to_state: PilotCaseState,
        actor_id: uuid.UUID,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.validate_transition(from_state, to_state):
            raise InvalidTransitionError(from_state, to_state)

        return {
            "id": uuid.uuid4(),
            "from_state": from_state,
            "to_state": to_state,
            "actor_id": actor_id,
            "reason": reason,
            "metadata": metadata or {},
            "transitioned_at": datetime.now(UTC),
        }
