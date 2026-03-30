"""Reporting service business logic."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import AuditEvent, ControlObject, ValidationResult, WorkflowCase
from shared.telemetry.logging import get_logger

logger = get_logger("reporting_service")


class ReportingService:
    """Generates case and management summary reports."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate_case_summary(
        self,
        case_id: uuid.UUID,
        tenant_id: uuid.UUID,
        include_audit_trail: bool = True,
        include_validations: bool = True,
    ) -> dict[str, Any]:
        """Generate a detailed case summary report."""
        # Get workflow case
        wf_result = await self.db.execute(
            select(WorkflowCase).where(
                WorkflowCase.id == case_id,
                WorkflowCase.tenant_id == tenant_id,
            )
        )
        workflow_case = wf_result.scalar_one_or_none()

        content: dict[str, Any] = {
            "case_id": str(case_id),
            "generated_at": datetime.utcnow().isoformat(),
            "report_type": "case_summary",
        }

        if workflow_case:
            content["workflow"] = {
                "type": workflow_case.workflow_type,
                "status": workflow_case.status.value
                if hasattr(workflow_case.status, "value")
                else str(workflow_case.status),
                "verdict": workflow_case.verdict.value
                if workflow_case.verdict and hasattr(workflow_case.verdict, "value")
                else str(workflow_case.verdict)
                if workflow_case.verdict
                else None,
                "started_at": str(workflow_case.started_at) if workflow_case.started_at else None,
                "completed_at": str(workflow_case.completed_at)
                if workflow_case.completed_at
                else None,
            }

        # Get control objects
        co_result = await self.db.execute(
            select(ControlObject).where(ControlObject.tenant_id == tenant_id).limit(100)
        )
        control_objects = co_result.scalars().all()
        content["control_objects"] = [
            {
                "id": str(co.id),
                "type": co.control_type.value
                if hasattr(co.control_type, "value")
                else str(co.control_type),
                "label": co.label,
                "confidence": co.confidence,
                "is_active": co.is_active,
            }
            for co in control_objects
        ]

        # Audit trail
        if include_audit_trail:
            audit_result = await self.db.execute(
                select(AuditEvent)
                .where(
                    AuditEvent.tenant_id == tenant_id,
                    AuditEvent.resource_id == str(case_id),
                )
                .order_by(AuditEvent.created_at)
                .limit(200)
            )
            events = audit_result.scalars().all()
            content["audit_trail"] = [
                {
                    "event_type": e.event_type,
                    "action": e.action,
                    "resource_type": e.resource_type,
                    "timestamp": str(e.created_at),
                }
                for e in events
            ]

        # Validations
        if include_validations:
            val_result = await self.db.execute(
                select(ValidationResult).where(ValidationResult.tenant_id == tenant_id).limit(100)
            )
            validations = val_result.scalars().all()
            case_validations = [
                v for v in validations if (v.metadata_ or {}).get("case_id") == str(case_id)
            ]
            content["validations"] = [
                {
                    "id": str(v.id),
                    "target_type": v.target_type,
                    "target_id": str(v.target_id),
                    "status": v.status.value if hasattr(v.status, "value") else str(v.status),
                    "rules_passed": v.rules_passed,
                    "rules_warned": v.rules_warned,
                    "rules_blocked": v.rules_blocked,
                }
                for v in case_validations
            ]

        return content

    async def generate_management_summary(
        self,
        case_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Generate a high-level management summary."""
        case_summary = await self.generate_case_summary(case_id, tenant_id)

        total_objects = len(case_summary.get("control_objects", []))
        total_validations = len(case_summary.get("validations", []))
        total_events = len(case_summary.get("audit_trail", []))

        workflow = case_summary.get("workflow", {})
        return {
            "case_id": str(case_id),
            "generated_at": datetime.utcnow().isoformat(),
            "report_type": "management_summary",
            "executive_summary": {
                "workflow_type": workflow.get("type", "unknown"),
                "status": workflow.get("status", "unknown"),
                "verdict": workflow.get("verdict"),
                "total_control_objects": total_objects,
                "total_validations": total_validations,
                "total_audit_events": total_events,
            },
            "risk_indicators": self._assess_risk(case_summary),
        }

    @staticmethod
    def _assess_risk(case_summary: dict[str, Any]) -> dict[str, Any]:
        """Assess risk level from case data."""
        validations = case_summary.get("validations", [])
        blocked = sum(1 for v in validations if v.get("status") == "blocked")
        warned = sum(1 for v in validations if v.get("status") == "warned")
        escalated = sum(1 for v in validations if v.get("status") == "escalated")

        if escalated > 0:
            level = "critical"
        elif blocked > 0:
            level = "high"
        elif warned > 0:
            level = "medium"
        else:
            level = "low"

        return {
            "level": level,
            "blocked_count": blocked,
            "warned_count": warned,
            "escalated_count": escalated,
        }

    @staticmethod
    def export_report_data(content: dict[str, Any], fmt: str = "json") -> dict[str, Any]:
        """Export report data in the requested format."""
        if fmt == "text":
            lines: list[str] = []
            lines.append(f"Report: {content.get('report_type', 'unknown')}")
            lines.append(f"Case: {content.get('case_id', 'N/A')}")
            lines.append(f"Generated: {content.get('generated_at', '')}")
            if "executive_summary" in content:
                es = content["executive_summary"]
                lines.append(f"Status: {es.get('status')}, Verdict: {es.get('verdict')}")
            return {"format": "text", "data": "\n".join(lines)}
        return {"format": "json", "data": content}
