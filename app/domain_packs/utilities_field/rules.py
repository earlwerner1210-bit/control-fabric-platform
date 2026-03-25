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
