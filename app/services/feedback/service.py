"""Feedback capture service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.feedback import (
    FeedbackCategory,
    FeedbackEntryCreate,
    FeedbackEntryResponse,
    FeedbackSummary,
)


class FeedbackService:
    """Captures and aggregates feedback for pilot improvement."""

    def __init__(self) -> None:
        self._entries: dict[uuid.UUID, list[dict[str, Any]]] = {}
        self._all_entries: list[dict[str, Any]] = []

    def submit_feedback(
        self,
        pilot_case_id: uuid.UUID,
        submitted_by: uuid.UUID,
        data: FeedbackEntryCreate,
    ) -> FeedbackEntryResponse:
        entry = {
            "id": uuid.uuid4(),
            "pilot_case_id": pilot_case_id,
            "submitted_by": submitted_by,
            "category": data.category,
            "severity": data.severity,
            "title": data.title,
            "description": data.description,
            "affected_component": data.affected_component,
            "suggested_improvement": data.suggested_improvement,
            "tags": data.tags,
            "metadata": data.metadata,
            "created_at": datetime.now(UTC),
        }
        self._entries.setdefault(pilot_case_id, []).append(entry)
        self._all_entries.append(entry)
        return FeedbackEntryResponse(**entry)

    def get_case_feedback(
        self,
        pilot_case_id: uuid.UUID,
    ) -> list[FeedbackEntryResponse]:
        return [FeedbackEntryResponse(**e) for e in self._entries.get(pilot_case_id, [])]

    def get_summary(
        self,
        tenant_id: uuid.UUID | None = None,
    ) -> FeedbackSummary:
        entries = self._all_entries

        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_component: dict[str, int] = {}

        for e in entries:
            cat = e["category"]
            cat_str = cat.value if isinstance(cat, FeedbackCategory) else str(cat)
            by_category[cat_str] = by_category.get(cat_str, 0) + 1

            sev = e["severity"]
            sev_str = sev.value if hasattr(sev, "value") else str(sev)
            by_severity[sev_str] = by_severity.get(sev_str, 0) + 1

            comp = e.get("affected_component")
            if comp:
                by_component[comp] = by_component.get(comp, 0) + 1

        # Top issues by severity (critical/high first)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        sorted_entries = sorted(
            entries,
            key=lambda e: severity_order.get(
                e["severity"].value if hasattr(e["severity"], "value") else str(e["severity"]),
                5,
            ),
        )
        top = [FeedbackEntryResponse(**e) for e in sorted_entries[:10]]

        return FeedbackSummary(
            total_entries=len(entries),
            by_category=by_category,
            by_severity=by_severity,
            by_component=by_component,
            top_issues=top,
        )
