"""Reporting service – summaries and exports."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import ControlObject, WorkflowCase, ValidationResult, AuditEvent

logger = get_logger("reporting")


class ReportingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate_case_summary(
        self, case_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> dict[str, Any]:
        """Generate a structured summary for a workflow case."""
        case = (await self.db.execute(
            select(WorkflowCase).where(WorkflowCase.id == case_id, WorkflowCase.tenant_id == tenant_id)
        )).scalar_one_or_none()

        if not case:
            return {"error": "Case not found"}

        # Get control objects
        objects = (await self.db.execute(
            select(ControlObject).where(ControlObject.workflow_case_id == case_id)
        )).scalars().all()

        # Get validations
        validations = (await self.db.execute(
            select(ValidationResult).where(ValidationResult.workflow_case_id == case_id)
        )).scalars().all()

        # Get audit trail count
        audit_count = (await self.db.execute(
            select(func.count()).where(AuditEvent.workflow_case_id == case_id)
        )).scalar() or 0

        object_summary: dict[str, int] = {}
        for obj in objects:
            ct = obj.control_type.value
            object_summary[ct] = object_summary.get(ct, 0) + 1

        return {
            "case_id": str(case.id),
            "workflow_type": case.workflow_type,
            "status": case.status.value if hasattr(case.status, 'value') else str(case.status),
            "verdict": case.verdict.value if case.verdict and hasattr(case.verdict, 'value') else str(case.verdict),
            "control_objects": {
                "total": len(list(objects)),
                "by_type": object_summary,
            },
            "validations": [
                {
                    "validator": v.validator_name,
                    "status": v.status.value if hasattr(v.status, 'value') else str(v.status),
                    "summary": v.summary,
                }
                for v in validations
            ],
            "audit_event_count": audit_count,
            "output": case.output_payload,
        }

    async def generate_management_summary(
        self, tenant_id: uuid.UUID
    ) -> dict[str, Any]:
        """Aggregate summary across all cases."""
        cases = (await self.db.execute(
            select(WorkflowCase).where(WorkflowCase.tenant_id == tenant_id)
        )).scalars().all()

        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for case in cases:
            by_type[case.workflow_type] = by_type.get(case.workflow_type, 0) + 1
            status_val = case.status.value if hasattr(case.status, 'value') else str(case.status)
            by_status[status_val] = by_status.get(status_val, 0) + 1

        return {
            "total_cases": len(list(cases)),
            "by_workflow_type": by_type,
            "by_status": by_status,
        }
