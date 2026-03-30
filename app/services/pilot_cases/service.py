"""Pilot case management service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.pilot_case import (
    BusinessImpact,
    CaseSeverity,
    CaseTimelineEntry,
    PilotCaseAssignResponse,
    PilotCaseCreate,
    PilotCaseResponse,
    PilotCaseState,
)
from app.services.state_machine import CaseStateMachineService


class PilotCaseService:
    """Manages pilot case lifecycle."""

    def __init__(self) -> None:
        self._state_machine = CaseStateMachineService()
        self._cases: dict[uuid.UUID, dict[str, Any]] = {}
        self._artifacts: dict[uuid.UUID, list[dict[str, Any]]] = {}
        self._assignments: dict[uuid.UUID, list[dict[str, Any]]] = {}
        self._transitions: dict[uuid.UUID, list[dict[str, Any]]] = {}

    def create_case(
        self,
        tenant_id: uuid.UUID,
        data: PilotCaseCreate,
        creator_id: uuid.UUID,
    ) -> PilotCaseResponse:
        case_id = uuid.uuid4()
        now = datetime.now(UTC)

        case = {
            "id": case_id,
            "tenant_id": tenant_id,
            "title": data.title,
            "description": data.description,
            "workflow_type": data.workflow_type,
            "state": PilotCaseState.CREATED,
            "external_refs": data.external_refs,
            "tags": data.tags,
            "category": data.category,
            "severity": data.severity,
            "business_impact": data.business_impact,
            "assigned_reviewer_id": None,
            "workflow_case_id": None,
            "metadata": data.metadata,
            "created_at": now,
            "updated_at": now,
        }
        self._cases[case_id] = case
        self._artifacts[case_id] = []
        self._assignments[case_id] = []
        self._transitions[case_id] = [
            {
                "timestamp": now,
                "event_type": "case_created",
                "actor_id": creator_id,
                "from_state": None,
                "to_state": PilotCaseState.CREATED.value,
                "details": {"title": data.title, "workflow_type": data.workflow_type},
            }
        ]
        return PilotCaseResponse(**case)

    def get_case(self, case_id: uuid.UUID) -> PilotCaseResponse | None:
        case = self._cases.get(case_id)
        if case is None:
            return None
        return PilotCaseResponse(**case)

    def list_cases(
        self,
        tenant_id: uuid.UUID,
        state: PilotCaseState | None = None,
        workflow_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PilotCaseResponse], int]:
        results = [
            c
            for c in self._cases.values()
            if c["tenant_id"] == tenant_id
            and (state is None or c["state"] == state)
            and (workflow_type is None or c["workflow_type"] == workflow_type)
        ]
        results.sort(key=lambda c: c["created_at"], reverse=True)
        total = len(results)
        start = (page - 1) * page_size
        page_items = results[start : start + page_size]
        return [PilotCaseResponse(**c) for c in page_items], total

    def add_artifact(
        self,
        case_id: uuid.UUID,
        artifact_type: str,
        artifact_id: uuid.UUID,
        label: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if case_id not in self._cases:
            raise ValueError(f"Case {case_id} not found")

        artifact = {
            "id": uuid.uuid4(),
            "pilot_case_id": case_id,
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "label": label,
            "metadata": metadata or {},
            "created_at": datetime.now(UTC),
        }
        self._artifacts[case_id].append(artifact)
        return artifact

    def assign_reviewer(
        self,
        case_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        assigned_by: uuid.UUID,
        notes: str | None = None,
    ) -> PilotCaseAssignResponse:
        case = self._cases.get(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")

        now = datetime.now(UTC)
        assignment = {
            "id": uuid.uuid4(),
            "pilot_case_id": case_id,
            "reviewer_id": reviewer_id,
            "assigned_by": assigned_by,
            "notes": notes,
            "assigned_at": now,
        }
        self._assignments[case_id].append(assignment)
        case["assigned_reviewer_id"] = reviewer_id
        case["updated_at"] = now

        self._transitions.setdefault(case_id, []).append(
            {
                "timestamp": now,
                "event_type": "reviewer_assigned",
                "actor_id": assigned_by,
                "from_state": None,
                "to_state": None,
                "details": {"reviewer_id": str(reviewer_id), "notes": notes},
            }
        )

        return PilotCaseAssignResponse(**assignment)

    def get_timeline(self, case_id: uuid.UUID) -> list[CaseTimelineEntry]:
        entries = self._transitions.get(case_id, [])
        return [CaseTimelineEntry(**e) for e in entries]

    def transition_state(
        self,
        case_id: uuid.UUID,
        target_state: PilotCaseState,
        actor_id: uuid.UUID,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        case = self._cases.get(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")

        current = case["state"]
        result = self._state_machine.transition(current, target_state, actor_id, reason, metadata)

        now = datetime.now(UTC)
        case["state"] = target_state
        case["updated_at"] = now

        self._transitions.setdefault(case_id, []).append(
            {
                "timestamp": now,
                "event_type": "state_transition",
                "actor_id": actor_id,
                "from_state": current.value if isinstance(current, PilotCaseState) else current,
                "to_state": target_state.value,
                "details": {"reason": reason, **(metadata or {})},
            }
        )

        return result

    def link_workflow_case(self, case_id: uuid.UUID, workflow_case_id: uuid.UUID) -> None:
        case = self._cases.get(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        case["workflow_case_id"] = workflow_case_id
        case["updated_at"] = datetime.now(UTC)
