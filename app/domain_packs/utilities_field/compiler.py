"""Utilities Field compiler — compile work order and engineer data into control objects."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain_packs.utilities_field.schemas import (
    ParsedWorkOrder,
    EngineerProfile,
    SkillRecord,
    PermitRequirement,
    SafetyPreconditionObject,
    MaterialRequirement,
    PreconditionType,
    WorkOrderType,
    SkillCategory,
)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class FieldCompileResult:
    """Container for all compiled control objects."""

    work_order: dict = field(default_factory=dict)
    engineer: dict = field(default_factory=dict)
    skill_requirements: list[dict] = field(default_factory=list)
    permit_requirements: list[dict] = field(default_factory=list)
    safety_preconditions: list[dict] = field(default_factory=list)
    materials: list[dict] = field(default_factory=list)
    schedule: dict = field(default_factory=dict)
    control_object_payloads: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Safety-precondition inference maps
# ---------------------------------------------------------------------------

# Work-order types that always require a risk assessment and method statement.
_RISK_ASSESSMENT_TYPES: set[str] = {
    WorkOrderType.emergency.value,
    WorkOrderType.repair.value,
    WorkOrderType.installation.value,
}

# Permit types that demand additional safety preconditions.
_PERMIT_SAFETY_MAP: dict[str, list[PreconditionType]] = {
    "confined_space": [
        PreconditionType.risk_assessment,
        PreconditionType.method_statement,
        PreconditionType.ppe,
        PreconditionType.toolbox_talk,
    ],
    "hot_works": [
        PreconditionType.risk_assessment,
        PreconditionType.ppe,
        PreconditionType.certification,
    ],
    "height_works": [
        PreconditionType.risk_assessment,
        PreconditionType.ppe,
        PreconditionType.method_statement,
    ],
    "street_works": [
        PreconditionType.risk_assessment,
        PreconditionType.ppe,
    ],
}

# Keywords in work-order descriptions that imply additional preconditions.
_DESCRIPTION_KEYWORD_MAP: dict[str, PreconditionType] = {
    "asbestos": PreconditionType.risk_assessment,
    "excavat": PreconditionType.method_statement,
    "chemical": PreconditionType.ppe,
    "hazardous": PreconditionType.risk_assessment,
    "voltage": PreconditionType.certification,
    "high pressure": PreconditionType.risk_assessment,
    "live": PreconditionType.toolbox_talk,
}

# Human-readable description per precondition type.
_PRECONDITION_DESCRIPTIONS: dict[PreconditionType, str] = {
    PreconditionType.ppe: "Appropriate personal protective equipment must be worn",
    PreconditionType.certification: "Valid certification required for this work scope",
    PreconditionType.risk_assessment: "Documented risk assessment must be completed before work begins",
    PreconditionType.method_statement: "Approved method statement must be available on-site",
    PreconditionType.toolbox_talk: "Toolbox talk must be delivered to all personnel before starting",
}


# ---------------------------------------------------------------------------
# FieldCompiler
# ---------------------------------------------------------------------------


class FieldCompiler:
    """Compile work order and engineer data into control objects."""

    # -- public entry point -------------------------------------------------

    def compile(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> FieldCompileResult:
        """Run the full compilation pipeline and return aggregated result."""

        wo_obj = self.compile_work_order(work_order)
        eng_obj = self.compile_engineer_profile(engineer)
        skill_reqs = self.compile_skill_requirements(work_order)
        permit_reqs = self.compile_permit_requirements(work_order)
        safety = self.compile_safety_preconditions(work_order)
        materials = self.compile_materials(work_order)
        schedule = self.compile_schedule(work_order)

        # Aggregate all payloads for downstream consumers.
        control_objects: list[dict] = []
        control_objects.append({"type": "work_order", "payload": wo_obj})
        control_objects.append({"type": "engineer", "payload": eng_obj})
        for sr in skill_reqs:
            control_objects.append({"type": "skill_requirement", "payload": sr})
        for pr in permit_reqs:
            control_objects.append({"type": "permit_requirement", "payload": pr})
        for sp in safety:
            control_objects.append({"type": "safety_precondition", "payload": sp})
        for mat in materials:
            control_objects.append({"type": "material", "payload": mat})
        control_objects.append({"type": "schedule", "payload": schedule})

        return FieldCompileResult(
            work_order=wo_obj,
            engineer=eng_obj,
            skill_requirements=skill_reqs,
            permit_requirements=permit_reqs,
            safety_preconditions=safety,
            materials=materials,
            schedule=schedule,
            control_object_payloads=control_objects,
        )

    # -- work order ---------------------------------------------------------

    def compile_work_order(self, work_order: ParsedWorkOrder) -> dict:
        """Generate the work-order control object with all metadata."""

        is_high_risk = work_order.work_order_type in (
            WorkOrderType.emergency,
            WorkOrderType.repair,
        ) or work_order.priority in ("urgent", "critical")

        has_dependencies = len(work_order.dependencies) > 0
        has_special_instructions = bool(work_order.special_instructions.strip())

        return {
            "work_order_id": work_order.work_order_id,
            "work_order_type": work_order.work_order_type.value,
            "description": work_order.description,
            "location": work_order.location,
            "site_id": work_order.site_id,
            "customer": work_order.customer,
            "priority": work_order.priority,
            "scheduled_date": work_order.scheduled_date,
            "scheduled_end": work_order.scheduled_end,
            "estimated_duration_hours": work_order.estimated_duration_hours,
            "linked_contract_id": str(work_order.linked_contract_id) if work_order.linked_contract_id else None,
            "customer_confirmed": work_order.customer_confirmed,
            "weather_conditions": work_order.weather_conditions,
            "special_instructions": work_order.special_instructions,
            "is_high_risk": is_high_risk,
            "has_dependencies": has_dependencies,
            "has_special_instructions": has_special_instructions,
            "dependency_count": len(work_order.dependencies),
            "required_skill_count": len(work_order.required_skills),
            "required_permit_count": len(work_order.required_permits),
            "material_count": len(work_order.materials_required),
        }

    # -- engineer profile ---------------------------------------------------

    def compile_engineer_profile(self, engineer: EngineerProfile) -> dict:
        """Generate engineer profile control object with skills and accreditations."""

        skill_categories = list({s.category.value for s in engineer.skills})
        accreditation_names = [a.name for a in engineer.accreditations]
        valid_accreditations = [a.name for a in engineer.accreditations if a.is_valid]
        expired_accreditations = [a.name for a in engineer.accreditations if not a.is_valid]

        return {
            "engineer_id": engineer.engineer_id,
            "name": engineer.name,
            "availability": engineer.availability,
            "location": engineer.location,
            "skills": [
                {
                    "skill_name": s.skill_name,
                    "category": s.category.value,
                    "level": s.level,
                    "expiry_date": s.expiry_date,
                }
                for s in engineer.skills
            ],
            "accreditations": [
                {
                    "name": a.name,
                    "issuing_body": a.issuing_body,
                    "valid_from": a.valid_from,
                    "valid_to": a.valid_to,
                    "is_valid": a.is_valid,
                }
                for a in engineer.accreditations
            ],
            "skill_categories": skill_categories,
            "accreditation_names": accreditation_names,
            "valid_accreditation_count": len(valid_accreditations),
            "expired_accreditation_count": len(expired_accreditations),
            "total_skill_count": len(engineer.skills),
        }

    # -- skill requirements -------------------------------------------------

    def compile_skill_requirements(self, work_order: ParsedWorkOrder) -> list[dict]:
        """Generate skill-requirement control objects linking a WO to its required skills."""

        results: list[dict] = []
        for skill in work_order.required_skills:
            is_specialist = skill.category in (
                SkillCategory.gas,
                SkillCategory.electrical,
                SkillCategory.hvac,
            )
            results.append({
                "work_order_id": work_order.work_order_id,
                "skill_name": skill.skill_name,
                "category": skill.category.value,
                "required_level": skill.level,
                "expiry_date": skill.expiry_date,
                "is_specialist": is_specialist,
            })
        return results

    # -- permit requirements ------------------------------------------------

    def compile_permit_requirements(self, work_order: ParsedWorkOrder) -> list[dict]:
        """Generate permit-requirement control objects."""

        results: list[dict] = []
        for permit in work_order.required_permits:
            is_blocking = permit.required and not permit.obtained
            results.append({
                "work_order_id": work_order.work_order_id,
                "permit_type": permit.permit_type.value,
                "description": permit.description,
                "required": permit.required,
                "obtained": permit.obtained,
                "reference": permit.reference,
                "is_blocking": is_blocking,
            })
        return results

    # -- safety preconditions -----------------------------------------------

    def compile_safety_preconditions(self, work_order: ParsedWorkOrder) -> list[dict]:
        """Infer and compile safety preconditions based on work type, permits, and description."""

        precondition_types: set[PreconditionType] = set()

        # 1. Work-order type driven preconditions.
        if work_order.work_order_type.value in _RISK_ASSESSMENT_TYPES:
            precondition_types.add(PreconditionType.risk_assessment)
            precondition_types.add(PreconditionType.method_statement)

        # All work orders require basic PPE.
        precondition_types.add(PreconditionType.ppe)

        # 2. Permit driven preconditions.
        for permit in work_order.required_permits:
            permit_key = permit.permit_type.value
            if permit_key in _PERMIT_SAFETY_MAP:
                for pt in _PERMIT_SAFETY_MAP[permit_key]:
                    precondition_types.add(pt)

        # 3. Description keyword driven preconditions.
        description_lower = work_order.description.lower()
        for keyword, precondition_type in _DESCRIPTION_KEYWORD_MAP.items():
            if keyword in description_lower:
                precondition_types.add(precondition_type)

        # 4. Emergency work always requires a toolbox talk.
        if work_order.work_order_type == WorkOrderType.emergency:
            precondition_types.add(PreconditionType.toolbox_talk)

        # 5. Gas-related skills require certification precondition.
        if any(s.category == SkillCategory.gas for s in work_order.required_skills):
            precondition_types.add(PreconditionType.certification)

        # Build the control objects.
        results: list[dict] = []
        for pt in sorted(precondition_types, key=lambda p: p.value):
            results.append({
                "work_order_id": work_order.work_order_id,
                "precondition_type": pt.value,
                "description": _PRECONDITION_DESCRIPTIONS.get(pt, pt.value),
                "required": True,
                "verified": False,
                "verified_by": "",
                "verified_at": "",
            })
        return results

    # -- materials ----------------------------------------------------------

    def compile_materials(self, work_order: ParsedWorkOrder) -> list[dict]:
        """Generate material-requirement control objects."""

        results: list[dict] = []
        for idx, mat_raw in enumerate(work_order.materials_required):
            # materials_required is list[dict] on the schema, so we normalise
            # flexibly while ensuring every control object has consistent keys.
            results.append({
                "work_order_id": work_order.work_order_id,
                "material_index": idx,
                "material_id": mat_raw.get("material_id", ""),
                "description": mat_raw.get("description", ""),
                "quantity": mat_raw.get("quantity", 1.0),
                "unit": mat_raw.get("unit", "each"),
                "available": mat_raw.get("available", True),
                "alternative": mat_raw.get("alternative", ""),
            })
        return results

    # -- schedule -----------------------------------------------------------

    def compile_schedule(self, work_order: ParsedWorkOrder) -> dict:
        """Generate schedule / time-constraint control object."""

        has_window = bool(work_order.scheduled_date and work_order.scheduled_end)
        is_overdue = False  # Determined downstream with current time comparison.

        return {
            "work_order_id": work_order.work_order_id,
            "scheduled_start": work_order.scheduled_date,
            "scheduled_end": work_order.scheduled_end,
            "estimated_duration_hours": work_order.estimated_duration_hours,
            "priority": work_order.priority,
            "has_defined_window": has_window,
            "is_overdue": is_overdue,
            "dependency_count": len(work_order.dependencies),
            "dependencies": work_order.dependencies,
        }
