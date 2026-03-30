"""Reporting service – summaries and exports."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import AuditEvent, ControlObject, ValidationResult, WorkflowCase

logger = get_logger("reporting")


class ReportingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate_case_summary(
        self, case_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> dict[str, Any]:
        """Generate a structured summary for a workflow case."""
        case = (
            await self.db.execute(
                select(WorkflowCase).where(
                    WorkflowCase.id == case_id, WorkflowCase.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()

        if not case:
            return {"error": "Case not found"}

        # Get control objects
        objects = (
            (
                await self.db.execute(
                    select(ControlObject).where(ControlObject.workflow_case_id == case_id)
                )
            )
            .scalars()
            .all()
        )

        # Get validations
        validations = (
            (
                await self.db.execute(
                    select(ValidationResult).where(ValidationResult.workflow_case_id == case_id)
                )
            )
            .scalars()
            .all()
        )

        # Get audit trail count
        audit_count = (
            await self.db.execute(
                select(func.count()).where(AuditEvent.workflow_case_id == case_id)
            )
        ).scalar() or 0

        object_summary: dict[str, int] = {}
        for obj in objects:
            ct = obj.control_type.value
            object_summary[ct] = object_summary.get(ct, 0) + 1

        return {
            "case_id": str(case.id),
            "workflow_type": case.workflow_type,
            "status": case.status.value if hasattr(case.status, "value") else str(case.status),
            "verdict": case.verdict.value
            if case.verdict and hasattr(case.verdict, "value")
            else str(case.verdict),
            "control_objects": {
                "total": len(list(objects)),
                "by_type": object_summary,
            },
            "validations": [
                {
                    "validator": v.validator_name,
                    "status": v.status.value if hasattr(v.status, "value") else str(v.status),
                    "summary": v.summary,
                }
                for v in validations
            ],
            "audit_event_count": audit_count,
            "output": case.output_payload,
        }

    async def generate_margin_report(
        self, tenant_id: uuid.UUID, case_id: uuid.UUID
    ) -> dict[str, Any]:
        """Generate a structured margin diagnosis report.

        Assembles:
        - Contract summary
        - Billability assessment
        - Leakage triggers with severity
        - Recovery recommendations with estimated values
        - Evidence chain status
        - Validation results
        - Audit timeline
        - Executive summary
        """
        case = (
            await self.db.execute(
                select(WorkflowCase).where(
                    WorkflowCase.id == case_id, WorkflowCase.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()

        if not case:
            return {"error": "Case not found"}

        output = case.output_payload or {}

        # Get control objects
        objects = (
            (
                await self.db.execute(
                    select(ControlObject).where(ControlObject.workflow_case_id == case_id)
                )
            )
            .scalars()
            .all()
        )

        # Get validations
        validations = (
            (
                await self.db.execute(
                    select(ValidationResult).where(ValidationResult.workflow_case_id == case_id)
                )
            )
            .scalars()
            .all()
        )

        # Get audit events
        audit_events = (
            (
                await self.db.execute(
                    select(AuditEvent)
                    .where(AuditEvent.workflow_case_id == case_id)
                    .order_by(AuditEvent.created_at.asc())
                )
            )
            .scalars()
            .all()
        )

        # Build leakage triggers from control objects
        leakage_triggers = []
        for obj in objects:
            if obj.control_type.value == "leakage_trigger":
                leakage_triggers.append(
                    {
                        "id": str(obj.id),
                        "label": obj.label,
                        "severity": obj.payload.get("severity", "unknown")
                        if obj.payload
                        else "unknown",
                        "description": obj.description,
                    }
                )

        # Build validation details
        validation_details = []
        overall_validation_status = "passed"
        for v in validations:
            v_status = v.status.value if hasattr(v.status, "value") else str(v.status)
            validation_details.append(
                {
                    "validator": v.validator_name,
                    "status": v_status,
                    "summary": v.summary,
                    "rule_results": v.rule_results,
                }
            )
            if v_status in ("blocked", "escalated"):
                overall_validation_status = v_status

        # Build audit timeline
        audit_timeline = []
        for event in audit_events:
            payload = event.payload or {}
            audit_timeline.append(
                {
                    "timestamp": event.created_at.isoformat() if event.created_at else None,
                    "event_type": event.event_type,
                    "stage": payload.get("stage", ""),
                    "detail": event.detail or "",
                }
            )

        # Evidence chain status
        evidence_ids = output.get("evidence_object_ids", [])
        evidence_chain_status = "complete" if evidence_ids else "missing"

        return {
            "case_id": str(case.id),
            "workflow_type": case.workflow_type,
            "status": case.status.value if hasattr(case.status, "value") else str(case.status),
            "contract_summary": output.get("contract_summary") or output.get("billability_details"),
            "billability_assessment": {
                "verdict": output.get("verdict", "unknown"),
                "billability_details": output.get("billability_details"),
            },
            "leakage_triggers": leakage_triggers,
            "leakage_drivers": output.get("leakage_drivers", []),
            "recovery_recommendations": output.get("recovery_recommendations", []),
            "penalty_exposure": output.get("penalty_exposure"),
            "evidence_chain_status": evidence_chain_status,
            "evidence_object_ids": evidence_ids,
            "validation_status": overall_validation_status,
            "validation_details": validation_details,
            "audit_timeline": audit_timeline,
            "audit_event_count": len(audit_events),
            "executive_summary": output.get("executive_summary"),
        }

    async def generate_reconciliation_report(
        self, tenant_id: uuid.UUID, case_id: uuid.UUID
    ) -> dict[str, Any]:
        """Generate a cross-pack reconciliation report."""
        case = (
            await self.db.execute(
                select(WorkflowCase).where(
                    WorkflowCase.id == case_id, WorkflowCase.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()

        if not case:
            return {"error": "Case not found"}

        output = case.output_payload or {}

        # Get control objects
        objects = (
            (
                await self.db.execute(
                    select(ControlObject).where(ControlObject.workflow_case_id == case_id)
                )
            )
            .scalars()
            .all()
        )

        # Get validations
        validations = (
            (
                await self.db.execute(
                    select(ValidationResult).where(
                        ValidationResult.workflow_case_id == case_id,
                        ValidationResult.domain == "cross_pack",
                    )
                )
            )
            .scalars()
            .all()
        )

        # Derive reconciliation data from output
        links = output.get("links", [])
        conflicts = output.get("conflicts", [])
        leakage_patterns = output.get("leakage_patterns", [])
        evidence_bundle = output.get("evidence_bundle", [])

        # Evidence chain status
        evidence_chain_status = "complete" if evidence_bundle else "incomplete"

        validation_details = []
        for v in validations:
            validation_details.append(
                {
                    "validator": v.validator_name,
                    "status": v.status.value if hasattr(v.status, "value") else str(v.status),
                    "summary": v.summary,
                }
            )

        return {
            "case_id": str(case.id),
            "workflow_type": case.workflow_type,
            "links_found": len(links),
            "conflicts_found": len(conflicts),
            "leakage_patterns_found": len(leakage_patterns),
            "verdict": output.get("verdict", ""),
            "conflicts": conflicts,
            "leakage_patterns": leakage_patterns,
            "evidence_chain_status": evidence_chain_status,
            "evidence_bundle_count": len(evidence_bundle),
            "control_objects_count": len(list(objects)),
            "validation_details": validation_details,
        }

    async def generate_management_summary(self, tenant_id: uuid.UUID) -> dict[str, Any]:
        """Aggregate summary across all cases."""
        cases = (
            (await self.db.execute(select(WorkflowCase).where(WorkflowCase.tenant_id == tenant_id)))
            .scalars()
            .all()
        )

        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for case in cases:
            by_type[case.workflow_type] = by_type.get(case.workflow_type, 0) + 1
            status_val = case.status.value if hasattr(case.status, "value") else str(case.status)
            by_status[status_val] = by_status.get(status_val, 0) + 1

        return {
            "total_cases": len(list(cases)),
            "by_workflow_type": by_type,
            "by_status": by_status,
        }
