"""Audit service -- immutable event log for all platform actions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _AuditStore:
    """In-memory audit event store (replaced by DB in production)."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._model_runs: list[dict[str, Any]] = []

    def save_event(self, event: dict[str, Any]) -> None:
        self._events.append(event)

    def save_model_run(self, run: dict[str, Any]) -> None:
        self._model_runs.append(run)

    def get_timeline(self, case_id: UUID) -> list[dict[str, Any]]:
        return [
            e
            for e in self._events
            if e.get("resource_id") == case_id or e.get("case_id") == case_id
        ]


class AuditService:
    """Records every significant action in the platform for compliance and debugging."""

    def __init__(self) -> None:
        self._store = _AuditStore()

    def log_event(
        self,
        tenant_id: UUID,
        event_type: str,
        actor_id: UUID | None,
        resource_type: str,
        resource_id: UUID,
        payload: dict[str, Any] | None = None,
        case_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Record a generic audit event."""
        event: dict[str, Any] = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            "event_type": event_type,
            "actor_id": actor_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "payload": payload or {},
            "case_id": case_id,
            "created_at": _now(),
        }
        self._store.save_event(event)
        logger.info(
            "audit.event: type=%s resource=%s/%s actor=%s",
            event_type,
            resource_type,
            resource_id,
            actor_id,
        )
        return event

    def log_workflow_event(
        self,
        case_id: UUID,
        event_type: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convenience wrapper to log an event scoped to a workflow case."""
        event: dict[str, Any] = {
            "id": uuid4(),
            "tenant_id": None,
            "event_type": event_type,
            "actor_id": None,
            "resource_type": "workflow_case",
            "resource_id": case_id,
            "case_id": case_id,
            "payload": details or {},
            "created_at": _now(),
        }
        self._store.save_event(event)
        logger.info("audit.workflow_event: case=%s type=%s", case_id, event_type)
        return event

    def log_model_run(
        self,
        case_id: UUID | None,
        provider: str,
        model: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
    ) -> dict[str, Any]:
        """Record an LLM inference call for cost tracking and audit."""
        run: dict[str, Any] = {
            "id": uuid4(),
            "case_id": case_id,
            "provider": provider,
            "model": model,
            "operation": operation,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "created_at": _now(),
        }
        self._store.save_model_run(run)
        logger.info(
            "audit.model_run: provider=%s model=%s tokens=%d+%d latency=%.1fms",
            provider,
            model,
            input_tokens,
            output_tokens,
            latency_ms,
        )
        return run

    def get_timeline(self, case_id: UUID) -> list[dict[str, Any]]:
        """Return all audit events associated with a workflow case, ordered by time."""
        events = self._store.get_timeline(case_id)
        events.sort(key=lambda e: e["created_at"])
        return events


# Singleton
audit_service = AuditService()
