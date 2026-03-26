"""Compiler service -- converts parsed document payloads into control objects."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.schemas.control_objects import ControlObjectTypeEnum

logger = logging.getLogger(__name__)

# Mapping of domain-pack section keys to control-object types
_SECTION_TYPE_MAP: dict[str, ControlObjectTypeEnum] = {
    "obligations": ControlObjectTypeEnum.OBLIGATION,
    "sla_targets": ControlObjectTypeEnum.SLA_TARGET,
    "penalty_clauses": ControlObjectTypeEnum.PENALTY_CLAUSE,
    "rate_card_items": ControlObjectTypeEnum.RATE_CARD_ITEM,
    "billable_events": ControlObjectTypeEnum.BILLABLE_EVENT,
    "work_orders": ControlObjectTypeEnum.WORK_ORDER,
    "incidents": ControlObjectTypeEnum.INCIDENT,
    "resolution_actions": ControlObjectTypeEnum.RESOLUTION_ACTION,
    "approval_gates": ControlObjectTypeEnum.APPROVAL_GATE,
    "evidence": ControlObjectTypeEnum.EVIDENCE,
}


def _now() -> datetime:
    return datetime.now(UTC)


class _ControlObjectStore:
    """In-memory store for control objects (replaced by a real DB repository)."""

    def __init__(self) -> None:
        self._objects: dict[UUID, dict[str, Any]] = {}

    def save(self, obj: dict[str, Any]) -> None:
        self._objects[obj["id"]] = obj

    def get(self, obj_id: UUID) -> dict[str, Any] | None:
        return self._objects.get(obj_id)


class CompilerService:
    """Transforms parsed document payloads into typed control objects."""

    def __init__(self) -> None:
        self._store = _ControlObjectStore()

    def compile_control_objects(
        self,
        tenant_id: UUID,
        parsed_payload: dict[str, Any],
        domain_pack: str,
        source_doc_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Walk *parsed_payload* and emit a control object for each recognised section entry.

        Returns a list of control-object dicts (not yet persisted).
        """
        objects: list[dict[str, Any]] = []
        now = _now()

        for section_key, control_type in _SECTION_TYPE_MAP.items():
            items = parsed_payload.get(section_key, [])
            if not isinstance(items, list):
                continue

            for item in items:
                label = (
                    item.get("label")
                    or item.get("name")
                    or item.get("title")
                    or str(control_type.value)
                )
                obj: dict[str, Any] = {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "control_type": control_type,
                    "domain": domain_pack,
                    "label": label,
                    "description": item.get("description"),
                    "payload": item,
                    "source_document_id": source_doc_id,
                    "source_clause_ref": item.get("clause_ref"),
                    "confidence": item.get("confidence"),
                    "workflow_case_id": None,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
                objects.append(obj)

        logger.info(
            "compiler.compile: tenant=%s domain=%s -> %d objects",
            tenant_id,
            domain_pack,
            len(objects),
        )
        return objects

    def persist_control_objects(
        self,
        tenant_id: UUID,
        objects: list[dict[str, Any]],
        workflow_case_id: UUID | None = None,
    ) -> list[UUID]:
        """Persist a batch of control-object dicts, optionally linking to a workflow case.

        Returns the list of persisted object IDs.
        """
        ids: list[UUID] = []
        for obj in objects:
            if workflow_case_id is not None:
                obj["workflow_case_id"] = workflow_case_id
            self._store.save(obj)
            ids.append(obj["id"])

        logger.info("compiler.persist: %d objects (case=%s)", len(ids), workflow_case_id)
        return ids


# Singleton
compiler_service = CompilerService()
