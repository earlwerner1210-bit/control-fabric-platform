"""Utilities Field compiler -- compile field operations artefacts into control objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain_packs.utilities_field.schemas import (
    EngineerProfile,
    ParsedWorkOrder,
    PermitRequirement,
    PreconditionType,
    SafetyPreconditionObject,
    SkillCategory,
    WorkOrderType,
)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class FieldCompileResult:
    """Aggregate result of the field compilation pipeline."""

    dispatch_preconditions: list[dict] = field(default_factory=list)
    skill_requirements: list[dict] = field(default_factory=list)
    safety_preconditions: list[dict] = field(default_factory=list)
    readiness_checks: list[dict] = field(default_factory=list)
    leakage_triggers: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Safety-precondition inference maps
# ---------------------------------------------------------------------------

_RISK_ASSESSMENT_TYPES: set[str] = {
    WorkOrderType.emergency.value,
    WorkOrderType.repair.value,
    WorkOrderType.installation.value,
}

_PERMIT_SAFETY_MAP: dict[str, list[dict]] = {
    "confined_space": [
        {"precondition_type": "risk_assessment", "description": "Confined space risk assessment completed and signed", "category": "confined_space"},
        {"precondition_type": "method_statement", "description": "Confined space method statement approved", "category": "confined_space"},
        {"precondition_type": "ppe", "description": "Gas monitor and rescue harness required", "category": "confined_space"},
        {"precondition_type": "toolbox_talk", "description": "Confined space toolbox talk delivered", "category": "confined_space"},
        {"precondition_type": "certification", "description": "Confined space entry certification valid", "category": "confined_space"},
    ],
    "hot_works": [
        {"precondition_type": "risk_assessment", "description": "Hot works fire risk assessment completed", "category": "hot_works"},
        {"precondition_type": "ppe", "description": "Fire-resistant PPE and fire extinguisher on site", "category": "hot_works"},
        {"precondition_type": "certification", "description": "Hot works certification valid", "category": "hot_works"},
    ],
    "height_works": [
        {"precondition_type": "risk_assessment", "description": "Working at height risk assessment completed", "category": "height_works"},
        {"precondition_type": "ppe", "description": "Full body harness and lanyard required", "category": "height_works"},
        {"precondition_type": "method_statement", "description": "Working at height method statement approved", "category": "height_works"},
        {"precondition_type": "certification", "description": "Working at height certification valid", "category": "height_works"},
    ],
    "street_works": [
        {"precondition_type": "risk_assessment", "description": "Traffic management risk assessment completed", "category": "street_works"},
        {"precondition_type": "ppe", "description": "High-visibility clothing and traffic cones", "category": "street_works"},
    ],
}

_DESCRIPTION_KEYWORD_MAP: dict[str, str] = {
    "asbestos": "risk_assessment",
    "excavat": "method_statement",
    "chemical": "ppe",
    "hazardous": "risk_assessment",
    "voltage": "certification",
    "high pressure": "risk_assessment",
    "live": "toolbox_talk",
}

_PRECONDITION_DESCRIPTIONS: dict[str, str] = {
    "ppe": "Appropriate personal protective equipment must be worn",
    "certification": "Valid certification required for this work scope",
    "risk_assessment": "Documented risk assessment must be completed before work begins",
    "method_statement": "Approved method statement must be available on-site",
    "toolbox_talk": "Toolbox talk must be delivered to all personnel before starting",
}


class FieldCompiler:
    """Compile field operations artefacts into control objects."""

    # ------------------------------------------------------------------
    # Top-level pipeline
    # ------------------------------------------------------------------

    def compile(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
        permits: list[PermitRequirement] | None = None,
        field_history: list[dict] | None = None,
    ) -> FieldCompileResult:
        """Full compilation pipeline."""
        effective_permits = permits if permits is not None else []
        dispatch_preconds = self.compile_dispatch_preconditions(work_order, effective_permits)
        skill_reqs = self.compile_skill_requirements(work_order)
        safety_preconds = self.compile_safety_preconditions(work_order)
        readiness = self.compile_readiness_checks(work_order, engineer, effective_permits)
        leakage = self.compile_field_leakage_triggers(work_order, field_history or [])

        summary = self.build_compile_summary(
            dispatch_preconds, skill_reqs, safety_preconds, readiness, leakage,
            work_order, engineer,
        )

        return FieldCompileResult(
            dispatch_preconditions=dispatch_preconds,
            skill_requirements=skill_reqs,
            safety_preconditions=safety_preconds,
            readiness_checks=readiness,
            leakage_triggers=leakage,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Dispatch preconditions
    # ------------------------------------------------------------------

    def compile_dispatch_preconditions(
        self,
        work_order: ParsedWorkOrder,
        permits: list[PermitRequirement],
    ) -> list[dict]:
        """Generate dispatch precondition control objects."""
        preconds: list[dict] = []

        # Permit preconditions
        obtained_types = {p.permit_type for p in permits if p.obtained}
        for req in work_order.required_permits:
            if req.required:
                met = req.permit_type in obtained_types or req.obtained
                preconds.append({
                    "control_type": "permit_precondition",
                    "permit_type": req.permit_type.value,
                    "description": req.description or f"Permit: {req.permit_type.value}",
                    "met": met,
                    "blocking": not met,
                    "resolution": "" if met else f"Obtain {req.permit_type.value} permit before dispatch",
                })

        # Dependency preconditions
        for dep in work_order.dependencies:
            resolved = dep.get("status", "pending") in ("completed", "resolved", "approved")
            preconds.append({
                "control_type": "dependency_precondition",
                "dependency_id": dep.get("id", dep.get("work_order_id", "")),
                "description": dep.get("description", "Prerequisite dependency"),
                "met": resolved,
                "blocking": dep.get("blocking", True) and not resolved,
                "resolution": "" if resolved else "Complete prerequisite before dispatch",
            })

        # Customer confirmation
        preconds.append({
            "control_type": "customer_confirmation",
            "description": "Customer has confirmed access for scheduled time",
            "met": work_order.customer_confirmed,
            "blocking": not work_order.customer_confirmed,
            "resolution": "" if work_order.customer_confirmed else "Confirm customer availability before dispatch",
        })

        # Schedule validity
        schedule_valid = True
        schedule_issue = ""
        if work_order.scheduled_date:
            try:
                sched = datetime.fromisoformat(work_order.scheduled_date)
                if sched < datetime.now():
                    schedule_valid = False
                    schedule_issue = "Scheduled date is in the past"
            except (ValueError, TypeError):
                schedule_valid = False
                schedule_issue = "Invalid scheduled date format"

        preconds.append({
            "control_type": "schedule_validity",
            "description": "Scheduled date is valid and in the future",
            "met": schedule_valid,
            "blocking": not schedule_valid,
            "resolution": schedule_issue,
        })

        # Material availability
        unavailable_materials = [
            m for m in work_order.materials_required
            if not m.get("available", True)
        ]
        materials_met = len(unavailable_materials) == 0
        preconds.append({
            "control_type": "materials_available",
            "description": "All required materials are available",
            "met": materials_met,
            "blocking": not materials_met,
            "resolution": "" if materials_met else f"{len(unavailable_materials)} material(s) unavailable",
        })

        # Weather conditions
        weather_ok = True
        if work_order.weather_conditions:
            weather_lower = work_order.weather_conditions.lower()
            if any(w in weather_lower for w in ("storm", "severe", "hurricane", "tornado", "blizzard", "flooding")):
                weather_ok = False
        preconds.append({
            "control_type": "weather_conditions",
            "description": "Weather conditions are safe for field work",
            "met": weather_ok,
            "blocking": not weather_ok,
            "resolution": "" if weather_ok else f"Unsafe weather: {work_order.weather_conditions}",
        })

        return preconds

    # ------------------------------------------------------------------
    # Skill requirements
    # ------------------------------------------------------------------

    def compile_skill_requirements(self, work_order: ParsedWorkOrder) -> list[dict]:
        """Generate skill requirement control objects from work order."""
        reqs: list[dict] = []

        for skill in work_order.required_skills:
            is_specialist = skill.category in (
                SkillCategory.gas,
                SkillCategory.electrical,
                SkillCategory.hvac,
            )
            reqs.append({
                "control_type": "skill_requirement",
                "work_order_id": work_order.work_order_id,
                "skill_name": skill.skill_name,
                "category": skill.category.value,
                "minimum_level": skill.level,
                "expiry_date": skill.expiry_date,
                "is_specialist": is_specialist,
                "critical": skill.category.value in ("gas", "electrical"),
            })

        # Implied skills from permit types
        implied_skills: dict[str, str] = {
            "confined_space": "confined_space_entry",
            "hot_works": "hot_works_competency",
            "height_works": "working_at_height",
        }
        for permit in work_order.required_permits:
            pt = permit.permit_type.value
            if pt in implied_skills:
                reqs.append({
                    "control_type": "implied_skill_requirement",
                    "work_order_id": work_order.work_order_id,
                    "skill_name": implied_skills[pt],
                    "source": f"Implied by {pt} permit",
                    "critical": True,
                })

        return reqs

    # ------------------------------------------------------------------
    # Safety preconditions
    # ------------------------------------------------------------------

    def compile_safety_preconditions(self, work_order: ParsedWorkOrder) -> list[dict]:
        """Infer and compile safety preconditions based on work type, permits, and description."""
        safety: list[dict] = []

        # Standard PPE always required
        safety.append({
            "control_type": "safety_precondition",
            "work_order_id": work_order.work_order_id,
            "precondition_type": "ppe",
            "description": "Standard PPE: hard hat, safety boots, hi-vis vest, gloves",
            "required": True,
            "category": "standard",
        })

        # Work-order type driven preconditions
        if work_order.work_order_type.value in _RISK_ASSESSMENT_TYPES:
            safety.append({
                "control_type": "safety_precondition",
                "work_order_id": work_order.work_order_id,
                "precondition_type": "risk_assessment",
                "description": _PRECONDITION_DESCRIPTIONS["risk_assessment"],
                "required": True,
                "category": "work_type",
            })
            safety.append({
                "control_type": "safety_precondition",
                "work_order_id": work_order.work_order_id,
                "precondition_type": "method_statement",
                "description": _PRECONDITION_DESCRIPTIONS["method_statement"],
                "required": True,
                "category": "work_type",
            })

        # Permit driven safety requirements
        for permit in work_order.required_permits:
            pt = permit.permit_type.value
            if pt in _PERMIT_SAFETY_MAP:
                for item in _PERMIT_SAFETY_MAP[pt]:
                    safety.append({
                        "control_type": "safety_precondition",
                        "work_order_id": work_order.work_order_id,
                        "required": True,
                        **item,
                    })

        # Description keyword driven preconditions
        desc_lower = work_order.description.lower()
        for keyword, ptype in _DESCRIPTION_KEYWORD_MAP.items():
            if keyword in desc_lower:
                safety.append({
                    "control_type": "safety_precondition",
                    "work_order_id": work_order.work_order_id,
                    "precondition_type": ptype,
                    "description": f"{_PRECONDITION_DESCRIPTIONS.get(ptype, ptype)} (triggered by keyword: {keyword})",
                    "required": True,
                    "category": "description_keyword",
                })

        # Emergency work always requires a toolbox talk
        if work_order.work_order_type == WorkOrderType.emergency:
            safety.append({
                "control_type": "safety_precondition",
                "work_order_id": work_order.work_order_id,
                "precondition_type": "toolbox_talk",
                "description": "Emergency work toolbox talk required for all on-site personnel",
                "required": True,
                "category": "emergency",
            })

        # Gas work safety
        has_gas = any(s.category == SkillCategory.gas for s in work_order.required_skills)
        if has_gas:
            safety.append({
                "control_type": "safety_precondition",
                "work_order_id": work_order.work_order_id,
                "precondition_type": "certification",
                "description": "Gas Safe registration valid and current",
                "required": True,
                "category": "gas",
            })
            safety.append({
                "control_type": "safety_precondition",
                "work_order_id": work_order.work_order_id,
                "precondition_type": "ppe",
                "description": "Gas leak detection equipment required",
                "required": True,
                "category": "gas",
            })

        # Electrical work safety
        has_elec = any(s.category == SkillCategory.electrical for s in work_order.required_skills)
        if has_elec:
            safety.append({
                "control_type": "safety_precondition",
                "work_order_id": work_order.work_order_id,
                "precondition_type": "ppe",
                "description": "Insulated tools and voltage tester required",
                "required": True,
                "category": "electrical",
            })

        return safety

    # ------------------------------------------------------------------
    # Readiness checks
    # ------------------------------------------------------------------

    def compile_readiness_checks(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
        permits: list[PermitRequirement],
    ) -> list[dict]:
        """Generate readiness check control objects."""
        checks: list[dict] = []

        # Engineer availability
        checks.append({
            "check": "engineer_availability",
            "passed": engineer.availability == "available",
            "detail": f"Engineer status: {engineer.availability}",
            "severity": "error" if engineer.availability != "available" else "info",
        })

        # Skill coverage
        required_skills = {s.skill_name.lower() for s in work_order.required_skills}
        available_skills = {s.skill_name.lower() for s in engineer.skills}
        missing = required_skills - available_skills
        checks.append({
            "check": "skill_coverage",
            "passed": len(missing) == 0,
            "detail": f"Missing skills: {', '.join(sorted(missing))}" if missing else "All required skills matched",
            "severity": "error" if missing else "info",
        })

        # Permit coverage
        obtained_types = {p.permit_type for p in permits if p.obtained}
        missing_permits = [
            p.permit_type.value for p in work_order.required_permits
            if p.required and p.permit_type not in obtained_types and not p.obtained
        ]
        checks.append({
            "check": "permit_coverage",
            "passed": len(missing_permits) == 0,
            "detail": f"Missing permits: {', '.join(missing_permits)}" if missing_permits else "All permits obtained",
            "severity": "error" if missing_permits else "info",
        })

        # Accreditation validity
        now = datetime.now()
        expired_accreds: list[str] = []
        expiring_accreds: list[str] = []
        for accred in engineer.accreditations:
            if not accred.is_valid:
                expired_accreds.append(accred.name)
            elif accred.valid_to:
                try:
                    exp = datetime.fromisoformat(accred.valid_to)
                    days_left = (exp - now).days
                    if days_left < 0:
                        expired_accreds.append(accred.name)
                    elif days_left < 30:
                        expiring_accreds.append(f"{accred.name} ({days_left}d)")
                except (ValueError, TypeError):
                    pass

        checks.append({
            "check": "accreditation_validity",
            "passed": len(expired_accreds) == 0,
            "detail": f"Expired: {', '.join(expired_accreds)}" if expired_accreds else "All accreditations valid",
            "severity": "error" if expired_accreds else "info",
            "warnings": expiring_accreds,
        })

        # Material availability
        unavailable = [
            m.get("description", m.get("name", "unknown"))
            for m in work_order.materials_required
            if not m.get("available", True)
        ]
        checks.append({
            "check": "materials_available",
            "passed": len(unavailable) == 0,
            "detail": f"Unavailable: {', '.join(unavailable)}" if unavailable else "All materials available",
            "severity": "error" if unavailable else "info",
        })

        # Customer confirmation
        checks.append({
            "check": "customer_confirmed",
            "passed": work_order.customer_confirmed,
            "detail": "Customer confirmed" if work_order.customer_confirmed else "Customer not yet confirmed",
            "severity": "warning" if not work_order.customer_confirmed else "info",
        })

        # Weather conditions
        weather_ok = True
        weather_detail = "No adverse weather conditions"
        if work_order.weather_conditions:
            wc = work_order.weather_conditions.lower()
            if any(w in wc for w in ("storm", "severe", "hurricane", "tornado", "blizzard", "flooding")):
                weather_ok = False
                weather_detail = f"Adverse weather: {work_order.weather_conditions}"
            elif any(w in wc for w in ("rain", "wind", "snow", "ice")):
                weather_detail = f"Weather advisory: {work_order.weather_conditions}"
        checks.append({
            "check": "weather_conditions",
            "passed": weather_ok,
            "detail": weather_detail,
            "severity": "error" if not weather_ok else "info",
        })

        # Dependencies complete
        incomplete_deps = [
            d for d in work_order.dependencies
            if d.get("status", "pending") not in ("completed", "resolved", "approved")
            and d.get("blocking", True)
        ]
        checks.append({
            "check": "dependencies_complete",
            "passed": len(incomplete_deps) == 0,
            "detail": f"{len(incomplete_deps)} blocking dependency/ies incomplete" if incomplete_deps else "All dependencies resolved",
            "severity": "error" if incomplete_deps else "info",
        })

        return checks

    # ------------------------------------------------------------------
    # Leakage triggers
    # ------------------------------------------------------------------

    def compile_field_leakage_triggers(
        self,
        work_order: ParsedWorkOrder,
        field_history: list[dict],
    ) -> list[dict]:
        """Detect cost leakage from field operations (rework, repeat visits, idle time)."""
        triggers: list[dict] = []

        if not field_history:
            return triggers

        visit_count = len(field_history)

        # Repeat visit leakage
        if visit_count >= 2:
            estimated_cost = visit_count * 120.0
            triggers.append({
                "trigger_type": "repeat_visits",
                "description": f"{visit_count} visits to same site for work order {work_order.work_order_id}",
                "visit_count": visit_count,
                "estimated_leakage_gbp": estimated_cost,
                "severity": "high" if visit_count >= 3 else "medium",
                "recommendation": "Root cause analysis required; consider senior engineer assignment",
            })

        # Rework leakage
        rework_count = sum(
            1 for h in field_history
            if h.get("exception_type") == "rework" or h.get("outcome") == "rework"
        )
        if rework_count > 0:
            triggers.append({
                "trigger_type": "rework",
                "description": f"{rework_count} rework event(s) recorded",
                "count": rework_count,
                "estimated_leakage_gbp": rework_count * 150.0,
                "severity": "high",
                "recommendation": "Review quality control procedures and first-time-fix rate",
            })

        # No-access leakage
        no_access_count = sum(
            1 for h in field_history
            if h.get("outcome") == "no_access" or h.get("exception_type") == "no_access"
        )
        if no_access_count > 0:
            triggers.append({
                "trigger_type": "no_access",
                "description": f"{no_access_count} no-access event(s) -- wasted dispatch",
                "count": no_access_count,
                "estimated_leakage_gbp": no_access_count * 80.0,
                "severity": "medium",
                "recommendation": "Implement mandatory customer confirmation 24h before dispatch",
            })

        # Idle time leakage
        for h in field_history:
            actual = h.get("actual_duration_hours")
            estimated = h.get("estimated_duration_hours") or work_order.estimated_duration_hours
            if actual and estimated and actual > estimated * 1.5:
                idle_hours = actual - estimated
                triggers.append({
                    "trigger_type": "idle_time",
                    "description": f"Visit took {actual}h vs estimated {estimated}h ({idle_hours:.1f}h over)",
                    "idle_hours": idle_hours,
                    "estimated_leakage_gbp": idle_hours * 45.0,
                    "severity": "medium" if idle_hours < 3 else "high",
                    "recommendation": "Review work order scoping accuracy and engineer productivity",
                })

        # Wrong materials leakage
        material_issues = sum(
            1 for h in field_history
            if h.get("exception_type") in ("wrong_materials", "missing_materials")
        )
        if material_issues > 0:
            triggers.append({
                "trigger_type": "material_waste",
                "description": f"{material_issues} material issue(s) causing delays or return visits",
                "count": material_issues,
                "estimated_leakage_gbp": material_issues * 100.0,
                "severity": "medium",
                "recommendation": "Validate material list against work order specification before dispatch",
            })

        # Skill gap leakage
        skill_gap_count = sum(
            1 for h in field_history
            if h.get("exception_type") == "skill_gap"
        )
        if skill_gap_count > 0:
            triggers.append({
                "trigger_type": "skill_gap_dispatch",
                "description": f"{skill_gap_count} dispatch(es) where engineer lacked required skills",
                "count": skill_gap_count,
                "estimated_leakage_gbp": skill_gap_count * 150.0,
                "severity": "high",
                "recommendation": "Enforce skill-fit validation in dispatch workflow",
            })

        return triggers

    # ------------------------------------------------------------------
    # Summary builder
    # ------------------------------------------------------------------

    def build_compile_summary(
        self,
        dispatch_preconds: list[dict],
        skill_reqs: list[dict],
        safety_preconds: list[dict],
        readiness_checks: list[dict],
        leakage_triggers: list[dict],
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> dict:
        """Build a human-readable summary of the compile result."""
        blocking_preconds = [p for p in dispatch_preconds if p.get("blocking")]
        failed_checks = [c for c in readiness_checks if not c.get("passed")]
        total_leakage = sum(t.get("estimated_leakage_gbp", 0) for t in leakage_triggers)
        high_sev_leakage = [t for t in leakage_triggers if t.get("severity") == "high"]

        all_clear = len(blocking_preconds) == 0 and len(failed_checks) == 0

        return {
            "work_order_id": work_order.work_order_id,
            "engineer_id": engineer.engineer_id,
            "engineer_name": engineer.name,
            "dispatch_ready": all_clear,
            "total_preconditions": len(dispatch_preconds),
            "blocking_preconditions": len(blocking_preconds),
            "blocking_details": [p.get("description", "") for p in blocking_preconds],
            "total_skill_requirements": len(skill_reqs),
            "critical_skill_requirements": sum(1 for r in skill_reqs if r.get("critical")),
            "total_safety_preconditions": len(safety_preconds),
            "readiness_checks_total": len(readiness_checks),
            "readiness_checks_passed": sum(1 for c in readiness_checks if c.get("passed")),
            "readiness_checks_failed": len(failed_checks),
            "failed_check_details": [c.get("detail", "") for c in failed_checks],
            "leakage_triggers_count": len(leakage_triggers),
            "high_severity_leakage_count": len(high_sev_leakage),
            "estimated_total_leakage_gbp": total_leakage,
            "compiled_at": datetime.now().isoformat(),
        }
