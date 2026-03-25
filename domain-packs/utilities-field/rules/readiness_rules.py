"""Readiness rule engine for evaluating field work order dispatch readiness.

Evaluates whether a work order can be dispatched by checking engineer skills,
accreditations, permits, access clearance, safety equipment, and time windows.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from ..schemas.field_schemas import (
    ComplianceBlocker,
    EngineerProfile,
    ParsedWorkOrder,
    PermitRequirement,
    ReadinessDecision,
    SkillFitAnalysis,
)
from ..taxonomy.field_taxonomy import ReadinessStatus, SkillCategory
from .skill_rules import SkillMatchEngine


class ReadinessRuleEngine:
    """Evaluates whether a work order is ready for field dispatch.

    Checks skills, accreditations, permits, access clearance, safety
    equipment, and scheduling constraints.
    """

    def __init__(self) -> None:
        self._skill_engine = SkillMatchEngine()

    def evaluate(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
        permits: list[PermitRequirement] | None = None,
    ) -> ReadinessDecision:
        """Run all readiness checks and produce a dispatch decision.

        Args:
            work_order: The work order to evaluate.
            engineer: The engineer being considered for dispatch.
            permits: Optional list of permits already obtained.

        Returns:
            ReadinessDecision with status, blockers, skill fit, and recommendation.
        """
        permits = permits or work_order.required_permits
        blockers: list[ComplianceBlocker] = []
        missing_prereqs: list[str] = []

        # 1. Skill fit
        skill_fit = self._has_required_skills(work_order, engineer)

        # 2. Accreditations
        accred_blockers = self._has_valid_accreditations(work_order, engineer)
        blockers.extend(accred_blockers)

        # 3. Permits
        permit_blockers = self._has_permits(work_order, permits)
        blockers.extend(permit_blockers)

        # 4. Access clearance
        access_blockers = self._has_access_clearance(work_order, engineer)
        blockers.extend(access_blockers)

        # 5. Safety equipment
        safety_blockers = self._has_safety_equipment(work_order)
        blockers.extend(safety_blockers)

        # 6. Time window
        time_blockers = self._meets_time_window(work_order, engineer)
        blockers.extend(time_blockers)

        # Collect missing prerequisites
        for blocker in blockers:
            missing_prereqs.append(blocker.description)
        if skill_fit.missing_skills:
            missing_prereqs.extend(
                f"Missing skill: {s}" for s in skill_fit.missing_skills
            )

        # Determine status
        critical_blockers = [b for b in blockers if b.severity == "blocking"]
        warning_blockers = [b for b in blockers if b.severity == "warning"]
        has_skill_gap = skill_fit.overall_fit < 0.5

        if critical_blockers or has_skill_gap:
            if any(b.category == "safety" for b in critical_blockers):
                status = ReadinessStatus.escalate
            else:
                status = ReadinessStatus.blocked
        elif warning_blockers or skill_fit.missing_skills:
            status = ReadinessStatus.conditional
        else:
            status = ReadinessStatus.ready

        # Build recommendation
        recommendation = self._build_recommendation(
            status, work_order, engineer, skill_fit, blockers
        )

        confidence = skill_fit.overall_fit * (1.0 - 0.15 * len(critical_blockers))
        confidence = max(0.0, min(1.0, confidence))

        return ReadinessDecision(
            status=status,
            missing_prerequisites=missing_prereqs,
            skill_fit=skill_fit,
            blockers=blockers,
            recommendation=recommendation,
            confidence=round(confidence, 2),
        )

    def _has_required_skills(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> SkillFitAnalysis:
        """Check skill fit using the SkillMatchEngine."""
        return self._skill_engine.evaluate_fit(
            required_skills=work_order.required_skills,
            engineer=engineer,
        )

    def _has_valid_accreditations(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> list[ComplianceBlocker]:
        """Check that required accreditations are present and valid."""
        blockers: list[ComplianceBlocker] = []
        today = date.today()

        # Determine which accreditations are needed based on skills
        required_categories = set(work_order.required_skills)
        categories_needing_cert = {
            c for c in required_categories if c.requires_certification
        }

        if not categories_needing_cert:
            return blockers

        engineer_accred_categories: set[SkillCategory] = set()
        for accred in engineer.accreditations:
            # Check expiry
            if accred.expiry_date and accred.expiry_date < today:
                blockers.append(
                    ComplianceBlocker(
                        category="accreditation",
                        description=f"Accreditation '{accred.name}' expired on {accred.expiry_date.isoformat()}.",
                        severity="blocking",
                        resolution_action=f"Renew '{accred.name}' accreditation before dispatch.",
                    )
                )
                continue
            engineer_accred_categories.update(accred.categories)

        missing = categories_needing_cert - engineer_accred_categories
        for cat in missing:
            blockers.append(
                ComplianceBlocker(
                    category="accreditation",
                    description=f"No valid accreditation covering '{cat.value}' skill category.",
                    severity="blocking",
                    resolution_action=f"Obtain {cat.value} accreditation or assign a certified engineer.",
                )
            )

        return blockers

    def _has_permits(
        self,
        work_order: ParsedWorkOrder,
        permits: list[PermitRequirement],
    ) -> list[ComplianceBlocker]:
        """Check that all required permits are approved and valid."""
        blockers: list[ComplianceBlocker] = []
        today = date.today()

        for permit in permits:
            if permit.status == "approved":
                # Check validity dates
                if permit.valid_to and permit.valid_to < today:
                    blockers.append(
                        ComplianceBlocker(
                            category="permit",
                            description=f"{permit.permit_type.value} permit expired on {permit.valid_to.isoformat()}.",
                            severity="blocking",
                            resolution_action=f"Renew {permit.permit_type.value} permit.",
                        )
                    )
                if permit.valid_from and permit.valid_from > today:
                    blockers.append(
                        ComplianceBlocker(
                            category="permit",
                            description=f"{permit.permit_type.value} permit not yet valid (starts {permit.valid_from.isoformat()}).",
                            severity="warning",
                        )
                    )
            elif permit.status in ("pending", "rejected", "expired"):
                blockers.append(
                    ComplianceBlocker(
                        category="permit",
                        description=f"{permit.permit_type.value} permit status is '{permit.status}'.",
                        severity="blocking",
                        resolution_action=f"Obtain approved {permit.permit_type.value} permit before dispatch.",
                        estimated_resolution_hours=24.0 if permit.status == "pending" else 48.0,
                    )
                )

        return blockers

    def _has_access_clearance(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> list[ComplianceBlocker]:
        """Check building/site access requirements."""
        blockers: list[ComplianceBlocker] = []

        # Check for building access permits
        building_permits = [
            p for p in work_order.required_permits
            if p.permit_type.value == "building_access"
        ]
        for permit in building_permits:
            if permit.status != "approved":
                blockers.append(
                    ComplianceBlocker(
                        category="access",
                        description="Building access clearance not confirmed.",
                        severity="blocking",
                        resolution_action="Contact building management to arrange access.",
                        estimated_resolution_hours=4.0,
                    )
                )

        return blockers

    def _has_safety_equipment(
        self,
        work_order: ParsedWorkOrder,
    ) -> list[ComplianceBlocker]:
        """Check that required safety equipment is listed for hazardous jobs."""
        blockers: list[ComplianceBlocker] = []

        for job in work_order.jobs:
            if job.hazards and not job.safety_equipment:
                blockers.append(
                    ComplianceBlocker(
                        category="safety",
                        description=(
                            f"Job '{job.description[:80]}' has identified hazards "
                            f"({', '.join(job.hazards)}) but no safety equipment specified."
                        ),
                        severity="blocking",
                        resolution_action="Specify required PPE and safety equipment for all hazardous tasks.",
                    )
                )

        return blockers

    def _meets_time_window(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> list[ComplianceBlocker]:
        """Check scheduling and availability constraints."""
        blockers: list[ComplianceBlocker] = []

        if not engineer.available:
            blockers.append(
                ComplianceBlocker(
                    category="schedule",
                    description=f"Engineer '{engineer.name}' is not currently available.",
                    severity="blocking",
                    resolution_action="Assign an available engineer or wait for availability.",
                )
            )

        if engineer.current_assignment:
            blockers.append(
                ComplianceBlocker(
                    category="schedule",
                    description=(
                        f"Engineer '{engineer.name}' is currently assigned to "
                        f"'{engineer.current_assignment}'."
                    ),
                    severity="warning",
                    resolution_action="Check if current assignment can be completed before this dispatch.",
                )
            )

        if not work_order.scheduled_date:
            blockers.append(
                ComplianceBlocker(
                    category="schedule",
                    description="No scheduled date set for this work order.",
                    severity="warning",
                    resolution_action="Set a scheduled date before dispatch.",
                )
            )

        return blockers

    def _build_recommendation(
        self,
        status: ReadinessStatus,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
        skill_fit: SkillFitAnalysis,
        blockers: list[ComplianceBlocker],
    ) -> str:
        """Build a human-readable dispatch recommendation."""
        if status == ReadinessStatus.ready:
            return (
                f"Work order '{work_order.title}' is ready for dispatch to "
                f"{engineer.name}. Skill fit: {skill_fit.overall_fit:.0%}. "
                f"No blockers identified."
            )
        elif status == ReadinessStatus.conditional:
            warnings = [b.description for b in blockers if b.severity == "warning"]
            return (
                f"Work order '{work_order.title}' can be conditionally dispatched to "
                f"{engineer.name}. Skill fit: {skill_fit.overall_fit:.0%}. "
                f"Warnings: {'; '.join(warnings)}."
            )
        elif status == ReadinessStatus.escalate:
            return (
                f"Work order '{work_order.title}' requires escalation before dispatch. "
                f"Safety concerns identified. Do not dispatch until resolved."
            )
        else:  # blocked
            critical = [b.description for b in blockers if b.severity == "blocking"]
            return (
                f"Work order '{work_order.title}' is BLOCKED for dispatch. "
                f"Resolve the following before dispatching: {'; '.join(critical)}."
            )
