"""
Utilities Field Pack - Readiness rule engine that evaluates whether a
work order is safe and compliant to dispatch given an engineer profile.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.domain_packs.utilities_field.parsers.work_order_parser import WorkOrderParser
from app.domain_packs.utilities_field.schemas.field_schemas import (
    AccreditationType,
    EngineerProfileObject,
    WorkCategory,
    WorkOrderObject,
)

# ---------------------------------------------------------------------------
# Grade ordering (lowest -> highest)
# ---------------------------------------------------------------------------

_GRADE_ORDER: list[str] = ["trainee", "standard", "senior", "principal", "lead"]


def _grade_rank(grade: str) -> int:
    """Return a numeric rank for an engineer grade (higher = more senior)."""
    normalised = grade.strip().lower()
    try:
        return _GRADE_ORDER.index(normalised)
    except ValueError:
        return 0  # unknown grades treated as lowest


# ---------------------------------------------------------------------------
# Safety equipment requirements by work category
# ---------------------------------------------------------------------------

_SAFETY_EQUIPMENT: dict[str, list[str]] = {
    WorkCategory.hv_switching.value: [
        "insulated_gloves",
        "arc_flash_suit",
        "voltage_detector",
        "lock_out_tag_out_kit",
    ],
    WorkCategory.cable_jointing_hv.value: [
        "insulated_gloves",
        "arc_flash_suit",
        "cable_testing_equipment",
        "fire_extinguisher",
    ],
    WorkCategory.cable_jointing_lv.value: [
        "insulated_gloves",
        "cable_testing_equipment",
        "fire_extinguisher",
    ],
    WorkCategory.overhead_line.value: [
        "climbing_harness",
        "hard_hat",
        "insulated_tools",
        "first_aid_kit",
    ],
    WorkCategory.metering.value: [
        "insulated_gloves",
        "multimeter",
        "sealing_kit",
    ],
    WorkCategory.new_connection.value: [
        "insulated_gloves",
        "cable_testing_equipment",
        "ppe_standard",
    ],
    WorkCategory.civils.value: [
        "hard_hat",
        "hi_vis_vest",
        "steel_toe_boots",
        "barriers_and_signs",
    ],
    WorkCategory.reinstatement.value: [
        "hard_hat",
        "hi_vis_vest",
        "steel_toe_boots",
    ],
}


# ---------------------------------------------------------------------------
# Readiness Rule Engine
# ---------------------------------------------------------------------------


class ReadinessRuleEngine:
    """Evaluates dispatch-readiness of a work order against an engineer profile.

    Returns a verdict dict containing:
        - ``verdict``: "ready" | "not_ready"
        - ``blockers``: list of blocking issues
        - ``warnings``: list of non-blocking concerns
        - ``gates``: per-rule results
    """

    def evaluate(
        self,
        work_order: WorkOrderObject,
        engineer_profile: EngineerProfileObject,
    ) -> dict[str, Any]:
        """Run every readiness rule and assemble an overall verdict."""

        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        gates: list[dict[str, Any]] = []

        # 1. Skill match
        skill_req = WorkOrderParser.extract_skill_requirements(work_order.work_category)
        passed, reason = self.check_skill_match(
            required=skill_req.required_skills,
            actual=engineer_profile.skills,
        )
        gates.append({"rule": "skill_match", "passed": passed, "reason": reason})
        if not passed:
            blockers.append({"rule": "skill_match", "reason": reason})

        # 2. Accreditation check
        acc_req = WorkOrderParser.extract_accreditation_requirements(work_order.work_category)
        passed, reason = self.check_accreditation(
            required=acc_req.required_accreditations,
            actual=engineer_profile.accreditations,
        )
        gates.append({"rule": "accreditation", "passed": passed, "reason": reason})
        if not passed:
            blockers.append({"rule": "accreditation", "reason": reason})

        # 3. Grade check
        passed, reason = self.check_grade(
            minimum_grade=skill_req.minimum_grade,
            actual_grade=engineer_profile.grade,
        )
        gates.append({"rule": "grade", "passed": passed, "reason": reason})
        if not passed:
            blockers.append({"rule": "grade", "reason": reason})

        # 4. Permit status
        passed, reason = self.check_permit_status(work_order)
        gates.append({"rule": "permit_status", "passed": passed, "reason": reason})
        if not passed:
            blockers.append({"rule": "permit_status", "reason": reason})

        # 5. Access requirements
        passed, reason = self.check_access_requirements(work_order)
        gates.append({"rule": "access_requirements", "passed": passed, "reason": reason})
        if not passed:
            warnings.append({"rule": "access_requirements", "reason": reason})

        # 6. Crew size
        passed, reason = self.check_crew_size(
            required=skill_req.crew_size,
            available=work_order.crew_size,
        )
        gates.append({"rule": "crew_size", "passed": passed, "reason": reason})
        if not passed:
            blockers.append({"rule": "crew_size", "reason": reason})

        # 7. Safety equipment
        passed, reason = self.check_safety_equipment(work_order.work_category)
        gates.append({"rule": "safety_equipment", "passed": passed, "reason": reason})
        if not passed:
            warnings.append({"rule": "safety_equipment", "reason": reason})

        verdict = "ready" if len(blockers) == 0 else "not_ready"

        return {
            "verdict": verdict,
            "blockers": blockers,
            "warnings": warnings,
            "gates": gates,
        }

    # ------------------------------------------------------------------
    # Individual rule methods
    # ------------------------------------------------------------------

    @staticmethod
    def check_skill_match(
        required: list[str],
        actual: list[str],
    ) -> tuple[bool, str]:
        """Check whether the engineer holds every required skill."""
        actual_set = {s.strip().lower() for s in actual}
        missing = [s for s in required if s.strip().lower() not in actual_set]
        if missing:
            return False, f"Missing required skills: {', '.join(missing)}"
        return True, "All required skills present"

    @staticmethod
    def check_accreditation(
        required: list[AccreditationType | str],
        actual: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        """Check accreditations are held and not expired."""
        held_types: dict[str, dict[str, Any]] = {}
        for acc in actual:
            acc_type = acc.get("type", "")
            if isinstance(acc_type, AccreditationType):
                acc_type = acc_type.value
            held_types[acc_type] = acc

        missing: list[str] = []
        expired: list[str] = []
        today = date.today()

        for req in required:
            req_val = req.value if isinstance(req, AccreditationType) else str(req)
            if req_val not in held_types:
                missing.append(req_val)
                continue
            expiry_raw = held_types[req_val].get("expiry")
            if expiry_raw:
                if isinstance(expiry_raw, str):
                    try:
                        expiry_date = datetime.fromisoformat(expiry_raw).date()
                    except ValueError:
                        continue
                elif isinstance(expiry_raw, (date, datetime)):
                    expiry_date = expiry_raw if isinstance(expiry_raw, date) else expiry_raw.date()
                else:
                    continue
                if expiry_date < today:
                    expired.append(req_val)

        issues: list[str] = []
        if missing:
            issues.append(f"Missing accreditations: {', '.join(missing)}")
        if expired:
            issues.append(f"Expired accreditations: {', '.join(expired)}")
        if issues:
            return False, "; ".join(issues)
        return True, "All accreditations valid"

    @staticmethod
    def check_grade(minimum_grade: str, actual_grade: str) -> tuple[bool, str]:
        """Check the engineer meets the minimum grade requirement."""
        if _grade_rank(actual_grade) < _grade_rank(minimum_grade):
            return False, f"Engineer grade '{actual_grade}' below minimum '{minimum_grade}'"
        return True, f"Grade '{actual_grade}' meets minimum '{minimum_grade}'"

    @staticmethod
    def check_permit_status(work_order: WorkOrderObject) -> tuple[bool, str]:
        """Check whether required permits are referenced in special requirements.

        For HV work categories a permit-to-work reference is mandatory.
        """
        hv_categories = {
            WorkCategory.hv_switching.value,
            WorkCategory.cable_jointing_hv.value,
        }
        wc = work_order.work_category
        if isinstance(wc, WorkCategory):
            wc = wc.value

        if wc in hv_categories:
            reqs_lower = [r.lower() for r in work_order.special_requirements]
            has_permit = any("permit" in r for r in reqs_lower)
            if not has_permit:
                return False, "HV work requires a permit-to-work reference in special_requirements"
        return True, "Permit requirements satisfied"

    @staticmethod
    def check_access_requirements(work_order: WorkOrderObject) -> tuple[bool, str]:
        """Check that location access prerequisites are declared.

        Non-blocking (warning) if location is set but no access notes exist.
        """
        if work_order.location:
            reqs_lower = [r.lower() for r in work_order.special_requirements]
            has_access = any(
                keyword in r for r in reqs_lower for keyword in ("access", "key", "escort", "gate")
            )
            if not has_access:
                return False, "Work has a location but no access arrangements documented"
        return True, "Access requirements satisfied or not applicable"

    @staticmethod
    def check_crew_size(required: int, available: int) -> tuple[bool, str]:
        """Check the available crew meets the minimum size."""
        if available < required:
            return False, f"Crew size {available} below minimum required {required}"
        return True, f"Crew size {available} meets requirement of {required}"

    @staticmethod
    def check_safety_equipment(work_category: str | WorkCategory) -> tuple[bool, str]:
        """Return required safety equipment as an advisory check.

        Since we cannot verify physical possession at dispatch time, this
        rule always passes but returns the list as information.
        """
        wc = work_category.value if isinstance(work_category, WorkCategory) else work_category
        equipment = _SAFETY_EQUIPMENT.get(wc, [])
        if equipment:
            return True, f"Required safety equipment: {', '.join(equipment)}"
        return True, "No specific safety equipment requirements defined"
