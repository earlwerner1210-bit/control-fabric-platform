"""
Utilities Field Pack - Parsers for work orders, engineer profiles,
skill requirements, and accreditation requirements.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from app.domain_packs.utilities_field.schemas.field_schemas import (
    AccreditationRequirementObject,
    AccreditationType,
    DispatchStatus,
    EngineerProfileObject,
    SkillRequirementObject,
    WorkCategory,
    WorkOrderObject,
)


# ---------------------------------------------------------------------------
# Skill / accreditation requirement mappings
# ---------------------------------------------------------------------------

_SKILL_REQUIREMENTS: dict[str, dict[str, Any]] = {
    WorkCategory.hv_switching.value: {
        "required_skills": ["hv_switching", "safety_isolation", "permit_management"],
        "minimum_grade": "senior",
        "crew_size": 2,
    },
    WorkCategory.cable_jointing_hv.value: {
        "required_skills": ["hv_jointing", "cable_termination", "hv_testing"],
        "minimum_grade": "senior",
        "crew_size": 2,
    },
    WorkCategory.cable_jointing_lv.value: {
        "required_skills": ["lv_jointing", "cable_termination", "lv_testing"],
        "minimum_grade": "standard",
        "crew_size": 2,
    },
    WorkCategory.overhead_line.value: {
        "required_skills": ["overhead_line_work", "climbing", "stringing"],
        "minimum_grade": "senior",
        "crew_size": 3,
    },
    WorkCategory.metering.value: {
        "required_skills": ["meter_installation", "ct_metering", "commissioning"],
        "minimum_grade": "standard",
        "crew_size": 1,
    },
    WorkCategory.new_connection.value: {
        "required_skills": ["connection_design", "cable_laying", "testing"],
        "minimum_grade": "standard",
        "crew_size": 2,
    },
    WorkCategory.civils.value: {
        "required_skills": ["excavation", "duct_laying", "reinstatement_basic"],
        "minimum_grade": "standard",
        "crew_size": 3,
    },
    WorkCategory.reinstatement.value: {
        "required_skills": ["reinstatement", "surface_finishing", "compliance_check"],
        "minimum_grade": "standard",
        "crew_size": 2,
    },
}


_ACCREDITATION_REQUIREMENTS: dict[str, dict[str, Any]] = {
    WorkCategory.hv_switching.value: {
        "required_accreditations": [
            AccreditationType.ecs_card,
            AccreditationType.first_aid,
        ],
        "validity_check_required": True,
    },
    WorkCategory.cable_jointing_hv.value: {
        "required_accreditations": [
            AccreditationType.ecs_card,
            AccreditationType.jib_grading,
            AccreditationType.first_aid,
        ],
        "validity_check_required": True,
    },
    WorkCategory.cable_jointing_lv.value: {
        "required_accreditations": [
            AccreditationType.ecs_card,
            AccreditationType.jib_grading,
        ],
        "validity_check_required": True,
    },
    WorkCategory.overhead_line.value: {
        "required_accreditations": [
            AccreditationType.ecs_card,
            AccreditationType.first_aid,
        ],
        "validity_check_required": True,
    },
    WorkCategory.metering.value: {
        "required_accreditations": [
            AccreditationType.ecs_card,
            AccreditationType.eighteenth_edition,
        ],
        "validity_check_required": True,
    },
    WorkCategory.new_connection.value: {
        "required_accreditations": [
            AccreditationType.ecs_card,
            AccreditationType.eighteenth_edition,
            AccreditationType.nrswa,
        ],
        "validity_check_required": True,
    },
    WorkCategory.civils.value: {
        "required_accreditations": [
            AccreditationType.cscs,
            AccreditationType.nrswa,
        ],
        "validity_check_required": True,
    },
    WorkCategory.reinstatement.value: {
        "required_accreditations": [
            AccreditationType.cscs,
            AccreditationType.nrswa,
        ],
        "validity_check_required": False,
    },
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class WorkOrderParser:
    """Parses raw payloads into validated utilities-field domain objects."""

    # -- Work order parsing --------------------------------------------------

    @staticmethod
    def parse_work_order(payload: dict[str, Any]) -> WorkOrderObject:
        """Parse a raw dict into a validated WorkOrderObject.

        Handles date coercion and enum normalisation so that upstream callers
        can pass loosely-typed data (e.g. from JSON APIs).
        """
        scheduled_raw = payload.get("scheduled_date")
        scheduled: Optional[date] = None
        if isinstance(scheduled_raw, date):
            scheduled = scheduled_raw
        elif isinstance(scheduled_raw, datetime):
            scheduled = scheduled_raw.date()
        elif isinstance(scheduled_raw, str) and scheduled_raw:
            try:
                scheduled = datetime.fromisoformat(scheduled_raw).date()
            except ValueError:
                scheduled = None

        work_category_raw = payload.get("work_category", "")
        try:
            work_category = WorkCategory(work_category_raw)
        except ValueError:
            work_category = WorkCategory.civils  # safe fallback

        status_raw = payload.get("status", "pending")
        try:
            status = DispatchStatus(status_raw)
        except ValueError:
            status = DispatchStatus.pending

        billing_gates = WorkOrderParser.extract_billing_gates(payload)
        completion_evidence = WorkOrderParser.extract_completion_evidence(payload)

        return WorkOrderObject(
            work_order_id=str(payload.get("work_order_id", payload.get("id", ""))),
            contract_ref=payload.get("contract_ref"),
            description=payload.get("description", ""),
            work_category=work_category,
            scheduled_date=scheduled,
            location=payload.get("location"),
            crew_size=int(payload.get("crew_size", 1)),
            special_requirements=payload.get("special_requirements", []),
            status=status,
            completion_evidence=completion_evidence,
            billing_gates=billing_gates,
        )

    @staticmethod
    def extract_billing_gates(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract billing-gate entries from the payload.

        Accepts either a top-level ``billing_gates`` list or a nested
        ``billing`` -> ``gates`` structure.
        """
        gates: list[dict[str, Any]] = []
        if "billing_gates" in payload and isinstance(payload["billing_gates"], list):
            for g in payload["billing_gates"]:
                gates.append({
                    "gate_id": g.get("gate_id", g.get("id", "")),
                    "name": g.get("name", ""),
                    "status": g.get("status", "pending"),
                    "amount": g.get("amount"),
                    "evidence_ref": g.get("evidence_ref"),
                })
        elif "billing" in payload and isinstance(payload["billing"], dict):
            for g in payload["billing"].get("gates", []):
                gates.append({
                    "gate_id": g.get("gate_id", g.get("id", "")),
                    "name": g.get("name", ""),
                    "status": g.get("status", "pending"),
                    "amount": g.get("amount"),
                    "evidence_ref": g.get("evidence_ref"),
                })
        return gates

    @staticmethod
    def extract_completion_evidence(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract completion-evidence items from the payload."""
        evidence: list[dict[str, Any]] = []
        raw = payload.get("completion_evidence", payload.get("evidence", []))
        if not isinstance(raw, list):
            return evidence
        for item in raw:
            if isinstance(item, dict):
                evidence.append({
                    "type": item.get("type", "unknown"),
                    "ref": item.get("ref", item.get("reference", "")),
                    "timestamp": item.get("timestamp"),
                    "description": item.get("description", ""),
                })
            elif isinstance(item, str):
                evidence.append({"type": "reference", "ref": item, "timestamp": None, "description": ""})
        return evidence

    # -- Engineer profile parsing --------------------------------------------

    @staticmethod
    def parse_engineer_profile(payload: dict[str, Any]) -> EngineerProfileObject:
        """Parse a raw dict into an EngineerProfileObject."""
        accreditations: list[dict[str, Any]] = []
        for acc in payload.get("accreditations", []):
            if isinstance(acc, dict):
                accreditations.append({
                    "type": acc.get("type", ""),
                    "expiry": acc.get("expiry"),
                    "issuing_body": acc.get("issuing_body", ""),
                    "card_number": acc.get("card_number", ""),
                })
            elif isinstance(acc, str):
                accreditations.append({"type": acc, "expiry": None, "issuing_body": "", "card_number": ""})

        return EngineerProfileObject(
            engineer_id=str(payload.get("engineer_id", payload.get("id", ""))),
            name=payload.get("name", ""),
            grade=payload.get("grade", "standard"),
            accreditations=accreditations,
            skills=payload.get("skills", []),
            availability_status=payload.get("availability_status", "available"),
        )

    # -- Requirement extraction ----------------------------------------------

    @staticmethod
    def extract_skill_requirements(work_category: str) -> SkillRequirementObject:
        """Return the skill requirements for a given work category.

        Falls back to a minimal default if the category is not mapped.
        """
        try:
            wc = WorkCategory(work_category)
        except ValueError:
            return SkillRequirementObject(
                work_category=WorkCategory.civils,
                required_skills=[],
                minimum_grade="standard",
                crew_size=1,
            )

        mapping = _SKILL_REQUIREMENTS.get(wc.value, {})
        return SkillRequirementObject(
            work_category=wc,
            required_skills=mapping.get("required_skills", []),
            minimum_grade=mapping.get("minimum_grade", "standard"),
            crew_size=mapping.get("crew_size", 1),
        )

    @staticmethod
    def extract_accreditation_requirements(work_category: str) -> AccreditationRequirementObject:
        """Return the accreditation requirements for a given work category."""
        try:
            wc = WorkCategory(work_category)
        except ValueError:
            return AccreditationRequirementObject(
                work_category=WorkCategory.civils,
                required_accreditations=[],
                validity_check_required=False,
            )

        mapping = _ACCREDITATION_REQUIREMENTS.get(wc.value, {})
        return AccreditationRequirementObject(
            work_category=wc,
            required_accreditations=mapping.get("required_accreditations", []),
            validity_check_required=mapping.get("validity_check_required", True),
        )
