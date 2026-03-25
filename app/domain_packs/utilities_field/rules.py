"""Utilities Field business rules – readiness, safety, skill matching."""

from __future__ import annotations

from datetime import datetime

from app.domain_packs.utilities_field.schemas import (
    CompletionEvidence,
    CompletionEvidenceType,
    ComplianceBlocker,
    CrewRequirement,
    EngineerProfile,
    ParsedWorkOrder,
    ReadinessDecision,
    ReadinessStatus,
    SkillFitAnalysis,
    SPENReadinessGate,
    SPENWorkCategory,
    UKAccreditation,
)
from app.schemas.validation import RuleResult


class ReadinessRuleEngine:
    """Determine whether a field dispatch is ready."""

    def evaluate(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> ReadinessDecision:
        missing: list[str] = []
        blockers: list[ComplianceBlocker] = []

        # Skill fit analysis
        skill_fit = SkillMatchEngine().evaluate_fit(work_order, engineer)
        if not skill_fit.fit:
            for ms in skill_fit.missing_skills:
                missing.append(f"Missing skill: {ms}")
                blockers.append(ComplianceBlocker(
                    blocker_type="skill",
                    description=f"Engineer missing required skill: {ms}",
                    severity="error",
                    resolution=f"Assign engineer with {ms} qualification",
                ))

        # Permit checks
        for permit in work_order.required_permits:
            if permit.required and not permit.obtained:
                missing.append(f"Missing permit: {permit.permit_type.value}")
                blockers.append(ComplianceBlocker(
                    blocker_type="permit",
                    description=f"Required permit not obtained: {permit.permit_type.value}",
                    severity="error",
                    resolution=f"Obtain {permit.permit_type.value} permit before dispatch",
                ))

        # Safety rules
        safety_results = SafetyRuleEngine().evaluate(work_order, engineer)
        for sr in safety_results:
            if not sr.passed:
                blockers.append(ComplianceBlocker(
                    blocker_type="safety",
                    description=sr.message,
                    severity=sr.severity,
                    resolution="Ensure safety requirements are met",
                ))
                missing.append(sr.message)

        # Accreditation checks
        accred_results = self._check_accreditations(work_order, engineer)
        for ar in accred_results:
            if not ar.passed:
                blockers.append(ComplianceBlocker(
                    blocker_type="accreditation",
                    description=ar.message,
                    severity=ar.severity,
                ))
                missing.append(ar.message)

        # Determine status
        has_errors = any(b.severity == "error" for b in blockers)
        has_warnings = any(b.severity == "warning" for b in blockers)

        if has_errors:
            status = ReadinessStatus.blocked
            recommendation = "Resolve blocking issues before dispatch"
        elif has_warnings:
            status = ReadinessStatus.conditional
            recommendation = "Dispatch with caution – review warnings"
        else:
            status = ReadinessStatus.ready
            recommendation = "Clear to dispatch"

        return ReadinessDecision(
            status=status,
            missing_prerequisites=missing,
            skill_fit=skill_fit,
            blockers=blockers,
            recommendation=recommendation,
        )

    def _check_accreditations(
        self, work_order: ParsedWorkOrder, engineer: EngineerProfile
    ) -> list[RuleResult]:
        results: list[RuleResult] = []
        # Check if engineer has valid accreditations for the work type
        required_accreds = self._get_required_accreditations(work_order)
        engineer_accreds = {a.name.lower() for a in engineer.accreditations if a.is_valid}

        for required in required_accreds:
            has_it = required.lower() in engineer_accreds
            results.append(RuleResult(
                rule_name=f"accreditation_{required}",
                passed=has_it,
                message=f"Has {required}" if has_it else f"Missing accreditation: {required}",
                severity="error" if not has_it else "info",
            ))
        return results

    def _get_required_accreditations(self, work_order: ParsedWorkOrder) -> list[str]:
        accreds: list[str] = []
        wo_type = work_order.work_order_type.value
        if wo_type in ("installation", "repair"):
            accreds.append("general_competency")
        for permit in work_order.required_permits:
            if permit.permit_type.value == "confined_space":
                accreds.append("confined_space_certification")
            if permit.permit_type.value == "hot_works":
                accreds.append("hot_works_certification")
        return accreds


class SafetyRuleEngine:
    """Evaluate safety prerequisite rules."""

    def evaluate(self, work_order: ParsedWorkOrder, engineer: EngineerProfile) -> list[RuleResult]:
        results: list[RuleResult] = []

        for permit in work_order.required_permits:
            pt = permit.permit_type.value

            if pt == "confined_space":
                has_cert = any(
                    "confined" in a.name.lower() for a in engineer.accreditations if a.is_valid
                )
                results.append(RuleResult(
                    rule_name="confined_space_certified",
                    passed=has_cert,
                    message="Confined space certified" if has_cert else "Missing confined space certification",
                    severity="error" if not has_cert else "info",
                ))

            if pt == "height_works":
                has_cert = any(
                    "height" in a.name.lower() or "working at height" in a.name.lower()
                    for a in engineer.accreditations if a.is_valid
                )
                results.append(RuleResult(
                    rule_name="height_works_certified",
                    passed=has_cert,
                    message="Height works certified" if has_cert else "Missing height works certification",
                    severity="error" if not has_cert else "info",
                ))

            if pt == "hot_works":
                has_cert = any(
                    "hot work" in a.name.lower() for a in engineer.accreditations if a.is_valid
                )
                results.append(RuleResult(
                    rule_name="hot_works_certified",
                    passed=has_cert,
                    message="Hot works certified" if has_cert else "Missing hot works certification",
                    severity="error" if not has_cert else "info",
                ))

        # Gas safety check for gas-related skills
        needs_gas = any(s.category.value == "gas" for s in work_order.required_skills)
        if needs_gas:
            has_gas = any(
                "gas safe" in a.name.lower() for a in engineer.accreditations if a.is_valid
            )
            results.append(RuleResult(
                rule_name="gas_safe_registered",
                passed=has_gas,
                message="Gas Safe registered" if has_gas else "Missing Gas Safe registration",
                severity="error" if not has_gas else "info",
            ))

        return results


class SkillMatchEngine:
    """Evaluate skill fit between work order requirements and engineer profile."""

    def evaluate_fit(
        self, work_order: ParsedWorkOrder, engineer: EngineerProfile
    ) -> SkillFitAnalysis:
        required = {s.skill_name.lower() for s in work_order.required_skills}
        available = {s.skill_name.lower() for s in engineer.skills}

        matching = required & available
        missing = required - available

        # Check for expiring accreditations
        expiring: list[str] = []
        for accred in engineer.accreditations:
            if accred.valid_to:
                try:
                    exp_date = datetime.fromisoformat(accred.valid_to)
                    days_left = (exp_date - datetime.now()).days
                    if 0 < days_left < 30:
                        expiring.append(f"{accred.name} (expires in {days_left} days)")
                except ValueError:
                    pass

        return SkillFitAnalysis(
            fit=len(missing) == 0,
            matching_skills=sorted(matching),
            missing_skills=sorted(missing),
            expiring_soon=expiring,
        )


# ---------------------------------------------------------------------------
# SPEN / UK Utility Managed Services rules
# ---------------------------------------------------------------------------

# Maps each SPEN work category to the UK accreditations required
_WORK_CATEGORY_ACCREDITATION_MAP: dict[str, list[UKAccreditation]] = {
    SPENWorkCategory.hv_switching: [
        UKAccreditation.hv_authorized_person,
        UKAccreditation.ecs_card,
        UKAccreditation.first_aid_at_work,
    ],
    SPENWorkCategory.lv_fault_repair: [
        UKAccreditation.lv_authorized_person,
        UKAccreditation.ecs_card,
        UKAccreditation.eighteen_edition,
    ],
    SPENWorkCategory.cable_jointing: [
        UKAccreditation.cable_jointer_approved,
        UKAccreditation.cscs_card,
        UKAccreditation.cat_and_genny,
    ],
    SPENWorkCategory.overhead_lines: [
        UKAccreditation.working_at_height,
        UKAccreditation.ipaf_mewp,
        UKAccreditation.ecs_card,
    ],
    SPENWorkCategory.substation_maintenance: [
        UKAccreditation.hv_authorized_person,
        UKAccreditation.ecs_card,
        UKAccreditation.confined_space_entry,
    ],
    SPENWorkCategory.metering_installation: [
        UKAccreditation.eighteen_edition,
        UKAccreditation.ecs_card,
    ],
    SPENWorkCategory.metering_exchange: [
        UKAccreditation.eighteen_edition,
        UKAccreditation.ecs_card,
    ],
    SPENWorkCategory.new_connection: [
        UKAccreditation.lv_authorized_person,
        UKAccreditation.ecs_card,
        UKAccreditation.eighteen_edition,
        UKAccreditation.cat_and_genny,
    ],
    SPENWorkCategory.service_alteration: [
        UKAccreditation.lv_authorized_person,
        UKAccreditation.ecs_card,
        UKAccreditation.eighteen_edition,
    ],
    SPENWorkCategory.civils_excavation: [
        UKAccreditation.cscs_card,
        UKAccreditation.cat_and_genny,
        UKAccreditation.nrswa_operative,
    ],
    SPENWorkCategory.reinstatement: [
        UKAccreditation.cscs_card,
        UKAccreditation.nrswa_operative,
    ],
    SPENWorkCategory.tree_cutting: [
        UKAccreditation.cscs_card,
        UKAccreditation.working_at_height,
    ],
    SPENWorkCategory.pole_erection: [
        UKAccreditation.working_at_height,
        UKAccreditation.cscs_card,
        UKAccreditation.cat_and_genny,
    ],
    SPENWorkCategory.cable_laying: [
        UKAccreditation.cscs_card,
        UKAccreditation.cat_and_genny,
        UKAccreditation.nrswa_operative,
    ],
    SPENWorkCategory.transformer_installation: [
        UKAccreditation.hv_authorized_person,
        UKAccreditation.ecs_card,
        UKAccreditation.first_aid_at_work,
    ],
}

# Work categories that require a minimum 2-person crew
_TWO_PERSON_CREW_CATEGORIES: set[str] = {
    SPENWorkCategory.hv_switching,
    SPENWorkCategory.overhead_lines,
    SPENWorkCategory.substation_maintenance,
    SPENWorkCategory.pole_erection,
    SPENWorkCategory.transformer_installation,
}

# Work categories that require street works (NRSWA) permits
_STREET_WORKS_CATEGORIES: set[str] = {
    SPENWorkCategory.civils_excavation,
    SPENWorkCategory.reinstatement,
    SPENWorkCategory.cable_laying,
    SPENWorkCategory.new_connection,
}

# Work categories that require approved design/scheme
_DESIGN_APPROVAL_CATEGORIES: set[str] = {
    SPENWorkCategory.new_connection,
    SPENWorkCategory.service_alteration,
}

# Work categories that require customer outage notification
_OUTAGE_NOTIFICATION_CATEGORIES: set[str] = {
    SPENWorkCategory.hv_switching,
    SPENWorkCategory.transformer_installation,
    SPENWorkCategory.substation_maintenance,
}

# Crew requirements per work category
_CREW_REQUIREMENTS: dict[str, CrewRequirement] = {
    SPENWorkCategory.hv_switching: CrewRequirement(
        minimum_crew_size=2,
        requires_supervisor=True,
        requires_hv_authorized=True,
        special_roles=["safety_observer"],
    ),
    SPENWorkCategory.overhead_lines: CrewRequirement(
        minimum_crew_size=2,
        requires_supervisor=False,
        special_roles=["banksman"],
    ),
    SPENWorkCategory.substation_maintenance: CrewRequirement(
        minimum_crew_size=2,
        requires_hv_authorized=True,
        special_roles=["safety_observer"],
    ),
    SPENWorkCategory.pole_erection: CrewRequirement(
        minimum_crew_size=2,
        special_roles=["banksman"],
    ),
    SPENWorkCategory.transformer_installation: CrewRequirement(
        minimum_crew_size=2,
        requires_supervisor=True,
        requires_hv_authorized=True,
        special_roles=["crane_operator"],
    ),
    SPENWorkCategory.cable_jointing: CrewRequirement(
        minimum_crew_size=1,
        requires_cable_jointer=True,
    ),
}

# Completion evidence requirements per category grouping
_COMPLETION_EVIDENCE_REQUIREMENTS: dict[str, list[CompletionEvidenceType]] = {
    "_all": [
        CompletionEvidenceType.after_photo,
        CompletionEvidenceType.risk_assessment_completed,
    ],
    "_hv": [
        CompletionEvidenceType.test_certificate,
        CompletionEvidenceType.safety_documentation,
    ],
    "_cable_jointing": [
        CompletionEvidenceType.test_certificate,
        CompletionEvidenceType.as_built_drawing,
    ],
    "_civils": [
        CompletionEvidenceType.reinstatement_record,
        CompletionEvidenceType.before_photo,
    ],
    "_metering": [
        CompletionEvidenceType.test_certificate,
        CompletionEvidenceType.customer_sign_off,
    ],
    "_new_connection": [
        CompletionEvidenceType.as_built_drawing,
        CompletionEvidenceType.test_certificate,
        CompletionEvidenceType.customer_sign_off,
    ],
}

# Categories that belong to each evidence group
_HV_CATEGORIES: set[str] = {
    SPENWorkCategory.hv_switching,
    SPENWorkCategory.substation_maintenance,
    SPENWorkCategory.transformer_installation,
}
_CIVILS_CATEGORIES: set[str] = {
    SPENWorkCategory.civils_excavation,
    SPENWorkCategory.reinstatement,
}
_METERING_CATEGORIES: set[str] = {
    SPENWorkCategory.metering_installation,
    SPENWorkCategory.metering_exchange,
}


class SPENReadinessEngine:
    """Evaluate SPEN-specific readiness for UK utility field dispatch."""

    def evaluate(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
        work_category: str,
        gates: list[SPENReadinessGate] | None = None,
        crew_size: int = 0,
    ) -> ReadinessDecision:
        """Run all SPEN readiness checks and return an aggregate decision.

        Checks performed:
        1. Accreditation check — engineer holds all required UK accreditations
        2. Crew size check — certain categories require 2-person crew
        3. Permit check — NRSWA, confined space, hot works permits
        4. Design approval check — new connections / service alterations
        5. Customer notification check — planned outage notification
        6. Materials check — materials on-van or pre-staged
        7. Traffic management check — street works TM plan
        8. Gate check — all SPENReadinessGates satisfied
        """
        effective_gates = gates if gates is not None else []
        missing: list[str] = []
        blockers: list[ComplianceBlocker] = []

        # 1. Accreditation check
        accred_results = self._accreditation_check(engineer, work_category)
        for ar in accred_results:
            if not ar.passed:
                missing.append(ar.message)
                blockers.append(ComplianceBlocker(
                    blocker_type="accreditation",
                    description=ar.message,
                    severity=ar.severity,
                    resolution=f"Engineer must obtain {ar.rule_name.replace('spen_accred_', '')} accreditation",
                ))

        # 2. Crew size check
        crew_results = self._crew_size_check(work_category, crew_size)
        for cr in crew_results:
            if not cr.passed:
                missing.append(cr.message)
                blockers.append(ComplianceBlocker(
                    blocker_type="safety",
                    description=cr.message,
                    severity=cr.severity,
                    resolution="Assign additional crew members before dispatch",
                ))

        # 3. Permit check
        permit_results = self._permit_check(work_order, work_category)
        for pr in permit_results:
            if not pr.passed:
                missing.append(pr.message)
                blockers.append(ComplianceBlocker(
                    blocker_type="permit",
                    description=pr.message,
                    severity=pr.severity,
                    resolution="Obtain required permit before dispatch",
                ))

        # 4. Design approval check
        design_results = self._design_approval_check(work_order, work_category)
        for dr in design_results:
            if not dr.passed:
                missing.append(dr.message)
                blockers.append(ComplianceBlocker(
                    blocker_type="access",
                    description=dr.message,
                    severity=dr.severity,
                    resolution="Obtain approved scheme design before dispatch",
                ))

        # 5. Customer notification check
        notif_results = self._customer_notification_check(work_order, work_category)
        for nr in notif_results:
            if not nr.passed:
                missing.append(nr.message)
                blockers.append(ComplianceBlocker(
                    blocker_type="safety",
                    description=nr.message,
                    severity=nr.severity,
                    resolution="Send customer planned outage notification",
                ))

        # 6. Materials check
        mat_results = self._materials_check(work_order)
        for mr in mat_results:
            if not mr.passed:
                missing.append(mr.message)
                blockers.append(ComplianceBlocker(
                    blocker_type="safety",
                    description=mr.message,
                    severity=mr.severity,
                    resolution="Ensure all materials are on-van or pre-staged at site",
                ))

        # 7. Traffic management check
        tm_results = self._traffic_management_check(work_order, work_category)
        for tr in tm_results:
            if not tr.passed:
                missing.append(tr.message)
                blockers.append(ComplianceBlocker(
                    blocker_type="permit",
                    description=tr.message,
                    severity=tr.severity,
                    resolution="Submit traffic management plan for approval",
                ))

        # 8. Gate check
        gate_results = self._gate_check(effective_gates)
        for gr in gate_results:
            if not gr.passed:
                missing.append(gr.message)
                blockers.append(ComplianceBlocker(
                    blocker_type="safety",
                    description=gr.message,
                    severity=gr.severity,
                    resolution="Satisfy readiness gate before dispatch",
                ))

        # Determine status
        has_errors = any(b.severity == "error" for b in blockers)
        has_warnings = any(b.severity == "warning" for b in blockers)

        if has_errors:
            status = ReadinessStatus.blocked
            recommendation = "Resolve blocking issues before SPEN dispatch"
        elif has_warnings:
            status = ReadinessStatus.conditional
            recommendation = "Dispatch with caution — review SPEN warnings"
        else:
            status = ReadinessStatus.ready
            recommendation = "Clear to dispatch for SPEN work"

        return ReadinessDecision(
            status=status,
            missing_prerequisites=missing,
            skill_fit=None,
            blockers=blockers,
            recommendation=recommendation,
        )

    # ----- Individual checks --------------------------------------------------

    def _accreditation_check(self, engineer: EngineerProfile, work_category: str) -> list[RuleResult]:
        """Check engineer holds all required UK accreditations for the work category."""
        results: list[RuleResult] = []
        required = _WORK_CATEGORY_ACCREDITATION_MAP.get(work_category, [])
        engineer_accreds = {a.name.lower() for a in engineer.accreditations if a.is_valid}

        for accred in required:
            has_it = accred.value.lower() in engineer_accreds
            results.append(RuleResult(
                rule_name=f"spen_accred_{accred.value}",
                passed=has_it,
                message=f"Has {accred.value}" if has_it else f"Missing required accreditation: {accred.value}",
                severity="error" if not has_it else "info",
            ))
        return results

    def _crew_size_check(self, work_category: str, crew_size: int = 0) -> list[RuleResult]:
        """Check crew size requirements for the work category.

        Args:
            work_category: SPEN work category.
            crew_size: Actual crew size. 0 means unknown (not checked).
                       A positive value is validated against the minimum.
        """
        results: list[RuleResult] = []
        if work_category in _TWO_PERSON_CREW_CATEGORIES:
            crew_req = _CREW_REQUIREMENTS.get(work_category)
            min_size = crew_req.minimum_crew_size if crew_req else 2

            if crew_size > 0 and crew_size < min_size:
                results.append(RuleResult(
                    rule_name="spen_crew_size",
                    passed=False,
                    message=f"{work_category} requires minimum {min_size}-person crew but only {crew_size} assigned",
                    severity="error",
                ))
            elif crew_size == 0:
                # Crew size unknown — no block, but leave for dispatch to verify
                pass
        return results

    def _permit_check(self, work_order: ParsedWorkOrder, work_category: str) -> list[RuleResult]:
        """Check NRSWA and other permits required for the work category."""
        results: list[RuleResult] = []

        if work_category in _STREET_WORKS_CATEGORIES:
            has_nrswa = any(
                p.permit_type.value == "street_works" and p.obtained
                for p in work_order.required_permits
            )
            results.append(RuleResult(
                rule_name="spen_nrswa_permit",
                passed=has_nrswa,
                message="NRSWA street works permit obtained" if has_nrswa else "Missing NRSWA street works permit for street works category",
                severity="error" if not has_nrswa else "info",
            ))

        # Confined space permit for substation work
        if work_category == SPENWorkCategory.substation_maintenance:
            has_confined = any(
                p.permit_type.value == "confined_space" and p.obtained
                for p in work_order.required_permits
            )
            results.append(RuleResult(
                rule_name="spen_confined_space_permit",
                passed=has_confined,
                message="Confined space permit obtained" if has_confined else "Missing confined space permit for substation maintenance",
                severity="warning" if not has_confined else "info",
            ))

        return results

    def _design_approval_check(self, work_order: ParsedWorkOrder, work_category: str) -> list[RuleResult]:
        """Check that design/scheme has been approved for applicable categories."""
        results: list[RuleResult] = []
        if work_category in _DESIGN_APPROVAL_CATEGORIES:
            # Look for a design approval in dependencies or prerequisites
            has_design = any(
                d.get("type") == "design" and d.get("status") in ("approved", "completed", "resolved")
                for d in work_order.dependencies
            ) or any(
                p.get("type") == "design" and p.get("status") in ("approved", "completed", "resolved")
                for p in work_order.prerequisites
            )
            results.append(RuleResult(
                rule_name="spen_design_approval",
                passed=has_design,
                message="Scheme design approved" if has_design else "Scheme design not approved — required for new connections and service alterations",
                severity="error" if not has_design else "info",
            ))
        return results

    def _customer_notification_check(self, work_order: ParsedWorkOrder, work_category: str) -> list[RuleResult]:
        """Check customer has been notified for planned outage categories."""
        results: list[RuleResult] = []
        if work_category in _OUTAGE_NOTIFICATION_CATEGORIES:
            results.append(RuleResult(
                rule_name="spen_customer_notification",
                passed=work_order.customer_confirmed,
                message="Customer notified of planned outage" if work_order.customer_confirmed else "Customer not notified of planned outage",
                severity="error" if not work_order.customer_confirmed else "info",
            ))
        return results

    def _materials_check(self, work_order: ParsedWorkOrder) -> list[RuleResult]:
        """Check all materials are available (on-van or pre-staged)."""
        results: list[RuleResult] = []
        unavailable = [
            m.get("description", m.get("name", "unknown"))
            for m in work_order.materials_required
            if not m.get("available", True)
        ]
        if unavailable:
            results.append(RuleResult(
                rule_name="spen_materials_available",
                passed=False,
                message=f"Materials not on-van or pre-staged: {', '.join(unavailable)}",
                severity="error",
            ))
        return results

    def _traffic_management_check(self, work_order: ParsedWorkOrder, work_category: str) -> list[RuleResult]:
        """Check traffic management plan exists for street works categories."""
        results: list[RuleResult] = []
        if work_category in _STREET_WORKS_CATEGORIES:
            # Check for traffic management in special instructions or prerequisites
            has_tm = (
                "traffic management" in work_order.special_instructions.lower()
                or any(
                    "traffic" in str(p.get("description", "")).lower()
                    for p in work_order.prerequisites
                )
            )
            results.append(RuleResult(
                rule_name="spen_traffic_management",
                passed=has_tm,
                message="Traffic management plan in place" if has_tm else "Missing traffic management plan for street works",
                severity="warning" if not has_tm else "info",
            ))
        return results

    def _gate_check(self, gates: list[SPENReadinessGate]) -> list[RuleResult]:
        """Check all readiness gates are satisfied."""
        results: list[RuleResult] = []
        for gate in gates:
            if gate.required and not gate.satisfied:
                results.append(RuleResult(
                    rule_name=f"spen_gate_{gate.gate_name}",
                    passed=False,
                    message=f"Readiness gate not satisfied: {gate.gate_name} — {gate.description}" if gate.description else f"Readiness gate not satisfied: {gate.gate_name}",
                    severity="error" if gate.blocking else "warning",
                ))
        return results


class CompletionValidator:
    """Validate completion evidence for SPEN work categories."""

    def validate_completion(
        self,
        work_category: str,
        evidence: list[CompletionEvidence],
    ) -> list[RuleResult]:
        """Check required evidence has been provided for the given work category.

        Required evidence per category:
        - All categories: after_photo, risk_assessment_completed
        - HV work: test_certificate, safety_documentation
        - Cable jointing: test_certificate, as_built_drawing
        - Civils/reinstatement: reinstatement_record, before_photo
        - Metering: test_certificate, customer_sign_off
        - New connections: as_built_drawing, test_certificate, customer_sign_off
        """
        results: list[RuleResult] = []
        provided_types = {e.evidence_type for e in evidence if e.provided}

        # Build the full set of required evidence types for this category
        required: set[CompletionEvidenceType] = set()

        # All categories require baseline evidence
        for et in _COMPLETION_EVIDENCE_REQUIREMENTS["_all"]:
            required.add(et)

        # Category-specific evidence
        if work_category in _HV_CATEGORIES:
            for et in _COMPLETION_EVIDENCE_REQUIREMENTS["_hv"]:
                required.add(et)

        if work_category == SPENWorkCategory.cable_jointing:
            for et in _COMPLETION_EVIDENCE_REQUIREMENTS["_cable_jointing"]:
                required.add(et)

        if work_category in _CIVILS_CATEGORIES:
            for et in _COMPLETION_EVIDENCE_REQUIREMENTS["_civils"]:
                required.add(et)

        if work_category in _METERING_CATEGORIES:
            for et in _COMPLETION_EVIDENCE_REQUIREMENTS["_metering"]:
                required.add(et)

        if work_category == SPENWorkCategory.new_connection:
            for et in _COMPLETION_EVIDENCE_REQUIREMENTS["_new_connection"]:
                required.add(et)

        # Check each required evidence type
        for req_type in sorted(required, key=lambda x: x.value):
            has_it = req_type in provided_types
            results.append(RuleResult(
                rule_name=f"spen_evidence_{req_type.value}",
                passed=has_it,
                message=f"Evidence provided: {req_type.value}" if has_it else f"Missing completion evidence: {req_type.value}",
                severity="error" if not has_it else "info",
            ))

        return results
