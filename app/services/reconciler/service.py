"""Reconciler service – cross-plane consistency, contradiction, and leakage detection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import ControlObject, ControlObjectType

logger = get_logger("reconciler")


@dataclass
class ReconciliationFinding:
    finding_type: str  # contradiction, missing_prerequisite, leakage, inconsistency
    severity: str  # info, warning, error, critical
    description: str
    source_object_ids: list[uuid.UUID] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class ReconciliationResult:
    findings: list[ReconciliationFinding] = field(default_factory=list)
    has_contradictions: bool = False
    has_missing_prerequisites: bool = False
    has_leakage: bool = False
    recommendations: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not (self.has_contradictions or self.has_missing_prerequisites or self.has_leakage)


class ReconcilerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def reconcile(
        self,
        tenant_id: uuid.UUID,
        control_object_ids: list[uuid.UUID],
    ) -> ReconciliationResult:
        """Run cross-plane reconciliation on a set of control objects."""
        result = await self.db.execute(
            select(ControlObject).where(
                ControlObject.id.in_(control_object_ids),
                ControlObject.tenant_id == tenant_id,
            )
        )
        objects = list(result.scalars().all())
        result_out = ReconciliationResult()

        # Group by type
        by_type: dict[str, list[ControlObject]] = {}
        for obj in objects:
            by_type.setdefault(obj.control_type.value, []).append(obj)

        # Check for contradictions
        contradiction_findings = self._detect_contradictions(by_type)
        result_out.findings.extend(contradiction_findings)
        result_out.has_contradictions = len(contradiction_findings) > 0

        # Check for missing prerequisites
        missing = self._detect_missing_prerequisites(by_type)
        result_out.findings.extend(missing)
        result_out.has_missing_prerequisites = len(missing) > 0

        # Check for leakage
        leakage = self._detect_leakage(by_type)
        result_out.findings.extend(leakage)
        result_out.has_leakage = len(leakage) > 0

        # Build recommendations
        for finding in result_out.findings:
            if finding.recommendation:
                result_out.recommendations.append(finding.recommendation)

        logger.info(
            "reconciliation_complete",
            object_count=len(objects),
            finding_count=len(result_out.findings),
        )
        return result_out

    def _detect_contradictions(
        self, by_type: dict[str, list[ControlObject]]
    ) -> list[ReconciliationFinding]:
        findings: list[ReconciliationFinding] = []

        # Check for conflicting penalty conditions and obligations
        penalties = by_type.get("penalty_condition", [])
        obligations = by_type.get("obligation", [])
        for penalty in penalties:
            p_section = penalty.payload.get("section", "")
            for obligation in obligations:
                o_section = obligation.payload.get("section", "")
                # Simplified: flag if penalty references same section
                if p_section and o_section and p_section == o_section:
                    findings.append(
                        ReconciliationFinding(
                            finding_type="contradiction",
                            severity="warning",
                            description=f"Penalty {penalty.label} references same section as {obligation.label}",
                            source_object_ids=[penalty.id, obligation.id],
                            recommendation="Review penalty and obligation for consistency",
                        )
                    )
        return findings

    def _detect_missing_prerequisites(
        self, by_type: dict[str, list[ControlObject]]
    ) -> list[ReconciliationFinding]:
        findings: list[ReconciliationFinding] = []

        # Check dispatch preconditions vs skill requirements
        preconditions = by_type.get("dispatch_precondition", [])
        skills = by_type.get("skill_requirement", [])
        readiness = by_type.get("readiness_check", [])

        if preconditions and not skills:
            findings.append(
                ReconciliationFinding(
                    finding_type="missing_prerequisite",
                    severity="error",
                    description="Dispatch preconditions exist but no skill requirements defined",
                    source_object_ids=[p.id for p in preconditions],
                    recommendation="Add skill requirements for dispatch readiness",
                )
            )

        return findings

    def _detect_leakage(
        self, by_type: dict[str, list[ControlObject]]
    ) -> list[ReconciliationFinding]:
        findings: list[ReconciliationFinding] = []

        billable_events = by_type.get("billable_event", [])
        obligations = by_type.get("obligation", [])

        # Check if obligations have matching billable events
        if obligations and not billable_events:
            findings.append(
                ReconciliationFinding(
                    finding_type="leakage",
                    severity="warning",
                    description="Obligations exist without corresponding billable events – potential revenue leakage",
                    source_object_ids=[o.id for o in obligations],
                    recommendation="Verify billable event coverage for all obligations",
                )
            )

        # Check for leakage triggers
        triggers = by_type.get("leakage_trigger", [])
        for trigger in triggers:
            findings.append(
                ReconciliationFinding(
                    finding_type="leakage",
                    severity="error",
                    description=f"Leakage trigger active: {trigger.label}",
                    source_object_ids=[trigger.id],
                    recommendation=trigger.payload.get("recommendation", "Investigate leakage trigger"),
                )
            )

        return findings
