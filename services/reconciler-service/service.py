"""Reconciler service business logic."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import ControlObject
from shared.telemetry.logging import get_logger

logger = get_logger("reconciler_service")


class ReconcilerService:
    """Reconciles control objects to detect contradictions, leakage, and missing items."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def reconcile_objects(
        self,
        case_id: uuid.UUID,
        object_ids: list[uuid.UUID],
        tenant_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Main reconciliation entry point."""
        result = await self.db.execute(
            select(ControlObject).where(
                ControlObject.id.in_(object_ids),
                ControlObject.tenant_id == tenant_id,
            )
        )
        objects = list(result.scalars().all())
        if not objects:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No control objects found"
            )

        contradictions = self.detect_contradictions(objects)
        leakage = self.detect_leakage(objects)
        missing = self.detect_missing_prerequisites(objects)
        recommendations = self.assemble_recommendations(contradictions, leakage, missing)

        logger.info(
            "Reconciled case %s: %d objects, %d contradictions, %d leakage items",
            case_id,
            len(objects),
            len(contradictions),
            len(leakage),
        )

        return {
            "case_id": case_id,
            "objects_reconciled": len(objects),
            "contradictions": contradictions,
            "leakage_items": leakage,
            "missing_prerequisites": missing,
            "recommendations": recommendations,
            "status": "completed",
        }

    @staticmethod
    def detect_contradictions(objects: list[ControlObject]) -> list[dict[str, Any]]:
        """Detect contradictions between control objects."""
        contradictions: list[dict[str, Any]] = []
        for i in range(len(objects)):
            for j in range(i + 1, len(objects)):
                a, b = objects[i], objects[j]
                # Check for conflicting payloads on same source document
                if (
                    a.source_document_id
                    and a.source_document_id == b.source_document_id
                    and a.control_type == b.control_type
                    and a.payload != b.payload
                ):
                    contradictions.append(
                        {
                            "object_a_id": a.id,
                            "object_b_id": b.id,
                            "field": "payload",
                            "value_a": str(a.payload)[:200],
                            "value_b": str(b.payload)[:200],
                            "severity": "warning",
                        }
                    )
        return contradictions

    @staticmethod
    def detect_leakage(objects: list[ControlObject]) -> list[dict[str, Any]]:
        """Detect potential revenue or cost leakage."""
        leakage: list[dict[str, Any]] = []
        for obj in objects:
            payload = obj.payload or {}
            if obj.control_type and obj.control_type.value == "billable_event":
                if not payload.get("rate") and not payload.get("amount"):
                    leakage.append(
                        {
                            "object_id": obj.id,
                            "description": f"Billable event '{obj.label}' has no rate or amount defined",
                            "estimated_amount": None,
                        }
                    )
            if obj.control_type and obj.control_type.value == "leakage_trigger":
                leakage.append(
                    {
                        "object_id": obj.id,
                        "description": f"Leakage trigger detected: {obj.label}",
                        "estimated_amount": payload.get("estimated_amount"),
                    }
                )
        return leakage

    @staticmethod
    def detect_missing_prerequisites(objects: list[ControlObject]) -> list[str]:
        """Detect missing prerequisite control objects."""
        missing: list[str] = []
        has_types = {obj.control_type.value for obj in objects if obj.control_type}

        required_pairs = {
            "dispatch_precondition": "readiness_check",
            "billable_event": "obligation",
            "penalty_condition": "obligation",
        }
        for trigger, prereq in required_pairs.items():
            if trigger in has_types and prereq not in has_types:
                missing.append(f"'{trigger}' present but prerequisite '{prereq}' is missing")

        return missing

    @staticmethod
    def assemble_recommendations(
        contradictions: list[dict], leakage: list[dict], missing: list[str]
    ) -> list[dict[str, str]]:
        """Build actionable recommendations from findings."""
        recs: list[dict[str, str]] = []
        if contradictions:
            recs.append(
                {
                    "action": "Review contradicting control objects",
                    "reason": f"{len(contradictions)} contradiction(s) found between objects",
                    "priority": "high",
                }
            )
        if leakage:
            recs.append(
                {
                    "action": "Investigate potential leakage",
                    "reason": f"{len(leakage)} leakage item(s) detected",
                    "priority": "high",
                }
            )
        if missing:
            recs.append(
                {
                    "action": "Add missing prerequisite objects",
                    "reason": "; ".join(missing),
                    "priority": "medium",
                }
            )
        if not recs:
            recs.append(
                {
                    "action": "No issues found",
                    "reason": "All reconciliation checks passed",
                    "priority": "low",
                }
            )
        return recs
