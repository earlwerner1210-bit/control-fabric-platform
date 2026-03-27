"""Action Engine Service — evidence-gated candidate action release."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.action_engine import (
    ActionBlockRequest,
    ActionEngineSummary,
    ActionReleaseRequest,
    ActionStatus,
    ActionType,
    CandidateActionCreate,
    CandidateActionResponse,
)
from app.schemas.validation_chain import ValidationChainRequest
from app.services.validation_chain.service import ValidationChainService


class ActionEngineService:
    """Manages candidate actions with evidence gating and validation chain release."""

    def __init__(
        self,
        validation_chain: ValidationChainService | None = None,
    ) -> None:
        self._validation_chain = validation_chain
        self._actions: dict[uuid.UUID, dict[str, Any]] = {}

    def create_candidate(
        self,
        tenant_id: uuid.UUID,
        create: CandidateActionCreate,
    ) -> CandidateActionResponse:
        action_id = uuid.uuid4()
        now = datetime.now(UTC)
        action = {
            "id": action_id,
            "pilot_case_id": create.pilot_case_id,
            "tenant_id": tenant_id,
            "action_type": create.action_type,
            "label": create.label,
            "description": create.description,
            "payload": create.payload,
            "status": ActionStatus.CANDIDATE,
            "evidence_refs": create.evidence_refs,
            "source_object_ids": create.source_object_ids,
            "confidence": create.confidence,
            "priority": create.priority,
            "requires_approval": create.requires_approval,
            "validation_chain_id": None,
            "blocking_reason": None,
            "released_at": None,
            "executed_at": None,
            "metadata": create.metadata,
            "created_at": now,
        }
        self._actions[action_id] = action
        return CandidateActionResponse(**action)

    def get_action(self, action_id: uuid.UUID) -> CandidateActionResponse | None:
        action = self._actions.get(action_id)
        return CandidateActionResponse(**action) if action else None

    def list_actions(
        self,
        pilot_case_id: uuid.UUID,
    ) -> list[CandidateActionResponse]:
        return [
            CandidateActionResponse(**a)
            for a in self._actions.values()
            if a["pilot_case_id"] == pilot_case_id
        ]

    def list_by_status(
        self,
        tenant_id: uuid.UUID,
        status: ActionStatus,
    ) -> list[CandidateActionResponse]:
        return [
            CandidateActionResponse(**a)
            for a in self._actions.values()
            if a["tenant_id"] == tenant_id and a["status"] == status
        ]

    def validate_and_release(
        self,
        action_id: uuid.UUID,
        context: dict[str, Any] | None = None,
    ) -> CandidateActionResponse | None:
        action = self._actions.get(action_id)
        if action is None:
            return None

        action["status"] = ActionStatus.VALIDATING

        if self._validation_chain:
            chain_request = ValidationChainRequest(
                pilot_case_id=action["pilot_case_id"],
                tenant_id=action["tenant_id"],
                candidate_action_id=action_id,
                context=context or {},
            )
            chain_result = self._validation_chain.run_chain(chain_request)
            action["validation_chain_id"] = chain_result.id

            if (
                chain_result.outcome.value == "released"
                or chain_result.outcome.value == "warn_released"
            ):
                action["status"] = ActionStatus.RELEASED
                action["released_at"] = datetime.now(UTC)
            elif chain_result.outcome.value == "blocked":
                action["status"] = ActionStatus.BLOCKED
                action["blocking_reason"] = chain_result.blocking_message
            elif chain_result.outcome.value == "escalated":
                action["status"] = ActionStatus.ESCALATED
        else:
            action["status"] = ActionStatus.RELEASED
            action["released_at"] = datetime.now(UTC)

        return CandidateActionResponse(**action)

    def release(
        self,
        action_id: uuid.UUID,
        request: ActionReleaseRequest,
    ) -> CandidateActionResponse | None:
        action = self._actions.get(action_id)
        if action is None:
            return None

        action["status"] = ActionStatus.RELEASED
        action["released_at"] = datetime.now(UTC)
        return CandidateActionResponse(**action)

    def block(
        self,
        action_id: uuid.UUID,
        request: ActionBlockRequest,
    ) -> CandidateActionResponse | None:
        action = self._actions.get(action_id)
        if action is None:
            return None

        if request.escalate:
            action["status"] = ActionStatus.ESCALATED
        else:
            action["status"] = ActionStatus.BLOCKED
        action["blocking_reason"] = request.blocking_reason
        return CandidateActionResponse(**action)

    def mark_executed(
        self,
        action_id: uuid.UUID,
    ) -> CandidateActionResponse | None:
        action = self._actions.get(action_id)
        if action is None:
            return None

        action["status"] = ActionStatus.EXECUTED
        action["executed_at"] = datetime.now(UTC)
        return CandidateActionResponse(**action)

    def rollback(
        self,
        action_id: uuid.UUID,
    ) -> CandidateActionResponse | None:
        action = self._actions.get(action_id)
        if action is None:
            return None

        action["status"] = ActionStatus.ROLLED_BACK
        return CandidateActionResponse(**action)

    def get_summary(self, tenant_id: uuid.UUID) -> ActionEngineSummary:
        actions = [a for a in self._actions.values() if a["tenant_id"] == tenant_id]

        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        confidences: list[float] = []

        released = 0
        blocked = 0
        escalated = 0
        executed = 0
        rolled_back = 0

        for a in actions:
            at = (
                a["action_type"].value
                if hasattr(a["action_type"], "value")
                else str(a["action_type"])
            )
            by_type[at] = by_type.get(at, 0) + 1
            st = a["status"].value if hasattr(a["status"], "value") else str(a["status"])
            by_status[st] = by_status.get(st, 0) + 1
            confidences.append(a["confidence"])

            if a["status"] == ActionStatus.RELEASED:
                released += 1
            elif a["status"] == ActionStatus.BLOCKED:
                blocked += 1
            elif a["status"] == ActionStatus.ESCALATED:
                escalated += 1
            elif a["status"] == ActionStatus.EXECUTED:
                executed += 1
            elif a["status"] == ActionStatus.ROLLED_BACK:
                rolled_back += 1

        n = len(actions)
        return ActionEngineSummary(
            total_candidates=n,
            released=released,
            blocked=blocked,
            escalated=escalated,
            executed=executed,
            rolled_back=rolled_back,
            release_rate=released / n if n > 0 else 0.0,
            block_rate=blocked / n if n > 0 else 0.0,
            by_type=by_type,
            by_status=by_status,
            avg_confidence=sum(confidences) / len(confidences) if confidences else 0.0,
        )
