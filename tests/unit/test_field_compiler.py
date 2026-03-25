"""Tests for the FieldCompiler from app.domain_packs.utilities_field.compiler."""

from __future__ import annotations

import pytest

from app.domain_packs.utilities_field.compiler import FieldCompiler, FieldCompileResult
from app.domain_packs.utilities_field.schemas import (
    Accreditation,
    EngineerProfile,
    ParsedWorkOrder,
    PermitRequirement,
    PermitType,
    PreconditionType,
    SkillCategory,
    SkillRecord,
    WorkOrderType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def compiler() -> FieldCompiler:
    return FieldCompiler()


@pytest.fixture
def full_work_order() -> ParsedWorkOrder:
    return ParsedWorkOrder(
        work_order_id="WO-100",
        work_order_type=WorkOrderType.repair,
        description="Emergency repair of fiber cabinet at central office",
        location="Building A, Floor 3",
        site_id="SITE-001",
        customer="TelcoCorp",
        scheduled_date="2024-04-15T08:00:00",
        scheduled_end="2024-04-15T16:00:00",
        priority="urgent",
        estimated_duration_hours=6.0,
        required_skills=[
            SkillRecord(skill_name="fiber", category=SkillCategory.fiber, level="expert"),
            SkillRecord(skill_name="electrical", category=SkillCategory.electrical, level="qualified"),
        ],
        required_permits=[
            PermitRequirement(
                permit_type=PermitType.building_access,
                description="Building access permit",
                required=True,
                obtained=True,
                reference="BA-123",
            ),
            PermitRequirement(
                permit_type=PermitType.confined_space,
                description="Confined space entry",
                required=True,
                obtained=False,
            ),
        ],
        materials_required=[
            {"material_id": "MAT-001", "description": "Fiber splice tray", "quantity": 2, "unit": "each", "available": True},
            {"material_id": "MAT-002", "description": "Fusion splice kit", "quantity": 1, "unit": "kit", "available": False, "alternative": "MAT-003"},
        ],
        special_instructions="Customer requires escort in building.",
        dependencies=[{"id": "WO-099", "type": "work_order", "status": "completed"}],
    )


@pytest.fixture
def full_engineer() -> EngineerProfile:
    return EngineerProfile(
        engineer_id="ENG-200",
        name="Jane Doe",
        skills=[
            SkillRecord(skill_name="fiber", category=SkillCategory.fiber, level="expert"),
            SkillRecord(skill_name="electrical", category=SkillCategory.electrical, level="qualified"),
        ],
        accreditations=[
            Accreditation(name="confined_space_certification", issuing_body="SafetyCert", is_valid=True),
            Accreditation(name="general_competency", issuing_body="TrainingCo", is_valid=True),
        ],
        availability="available",
        location="Depot B",
    )


@pytest.fixture
def minimal_work_order() -> ParsedWorkOrder:
    return ParsedWorkOrder(
        work_order_id="WO-MIN",
        work_order_type=WorkOrderType.inspection,
        description="Routine inspection",
    )


@pytest.fixture
def minimal_engineer() -> EngineerProfile:
    return EngineerProfile(
        engineer_id="ENG-MIN",
        name="Minimal Engineer",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCompileFullWorkOrder:
    """test_compile_full_work_order: Compile WO+engineer and verify all objects."""

    def test_compile_returns_result(
        self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder, full_engineer: EngineerProfile
    ):
        result = compiler.compile(full_work_order, full_engineer)
        assert isinstance(result, FieldCompileResult)

    def test_work_order_object_generated(
        self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder, full_engineer: EngineerProfile
    ):
        result = compiler.compile(full_work_order, full_engineer)

        assert result.work_order["work_order_id"] == "WO-100"
        assert result.work_order["work_order_type"] == "repair"
        assert result.work_order["is_high_risk"] is True  # repair + urgent
        assert result.work_order["has_dependencies"] is True
        assert result.work_order["has_special_instructions"] is True

    def test_engineer_object_generated(
        self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder, full_engineer: EngineerProfile
    ):
        result = compiler.compile(full_work_order, full_engineer)

        assert result.engineer["engineer_id"] == "ENG-200"
        assert result.engineer["name"] == "Jane Doe"
        assert result.engineer["total_skill_count"] == 2
        assert result.engineer["valid_accreditation_count"] == 2

    def test_all_control_objects_aggregated(
        self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder, full_engineer: EngineerProfile
    ):
        result = compiler.compile(full_work_order, full_engineer)

        # Should have: work_order, engineer, skill_reqs, permit_reqs,
        # safety_preconditions, materials, schedule
        assert len(result.control_object_payloads) >= 7  # 1+1+2+2+n_safety+2+1

        types_present = {o["type"] for o in result.control_object_payloads}
        assert "work_order" in types_present
        assert "engineer" in types_present
        assert "skill_requirement" in types_present
        assert "permit_requirement" in types_present
        assert "safety_precondition" in types_present
        assert "material" in types_present
        assert "schedule" in types_present

    def test_control_object_payloads_have_type_and_payload(
        self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder, full_engineer: EngineerProfile
    ):
        result = compiler.compile(full_work_order, full_engineer)

        for obj in result.control_object_payloads:
            assert "type" in obj
            assert "payload" in obj


class TestCompileSafetyPreconditions:
    """test_compile_safety_preconditions: Verify safety preconditions are inferred
    for high-risk work."""

    def test_repair_gets_risk_assessment(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        preconditions = compiler.compile_safety_preconditions(full_work_order)
        types = {p["precondition_type"] for p in preconditions}

        assert "risk_assessment" in types
        assert "method_statement" in types  # repair type requires it

    def test_all_work_orders_get_ppe(self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder):
        preconditions = compiler.compile_safety_preconditions(minimal_work_order)
        types = {p["precondition_type"] for p in preconditions}

        assert "ppe" in types

    def test_confined_space_permit_adds_preconditions(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        preconditions = compiler.compile_safety_preconditions(full_work_order)
        types = {p["precondition_type"] for p in preconditions}

        # Confined space permit should add: risk_assessment, method_statement, ppe, toolbox_talk
        assert "toolbox_talk" in types

    def test_emergency_work_gets_toolbox_talk(self, compiler: FieldCompiler):
        wo = ParsedWorkOrder(
            work_order_id="WO-EMG",
            work_order_type=WorkOrderType.emergency,
            description="Emergency gas leak repair",
        )
        preconditions = compiler.compile_safety_preconditions(wo)
        types = {p["precondition_type"] for p in preconditions}

        assert "toolbox_talk" in types
        assert "risk_assessment" in types

    def test_gas_skill_adds_certification(self, compiler: FieldCompiler):
        wo = ParsedWorkOrder(
            work_order_id="WO-GAS",
            work_order_type=WorkOrderType.maintenance,
            description="Gas meter replacement",
            required_skills=[
                SkillRecord(skill_name="gas_fitting", category=SkillCategory.gas, level="qualified"),
            ],
        )
        preconditions = compiler.compile_safety_preconditions(wo)
        types = {p["precondition_type"] for p in preconditions}

        assert "certification" in types

    def test_precondition_fields_are_populated(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        preconditions = compiler.compile_safety_preconditions(full_work_order)

        for p in preconditions:
            assert "work_order_id" in p
            assert p["work_order_id"] == "WO-100"
            assert "precondition_type" in p
            assert "description" in p
            assert p["description"]  # not empty
            assert p["required"] is True
            assert p["verified"] is False

    def test_description_keywords_add_preconditions(self, compiler: FieldCompiler):
        wo = ParsedWorkOrder(
            work_order_id="WO-HAZ",
            work_order_type=WorkOrderType.maintenance,
            description="Replace hazardous chemical storage unit with excavation",
        )
        preconditions = compiler.compile_safety_preconditions(wo)
        types = {p["precondition_type"] for p in preconditions}

        assert "risk_assessment" in types  # "hazardous" keyword
        assert "method_statement" in types  # "excavat" keyword


class TestCompileSkillRequirements:
    """test_compile_skill_requirements: Verify skill requirements compile with
    category/level."""

    def test_skill_count(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        skills = compiler.compile_skill_requirements(full_work_order)
        assert len(skills) == 2

    def test_skill_fields(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        skills = compiler.compile_skill_requirements(full_work_order)

        for skill in skills:
            assert "work_order_id" in skill
            assert skill["work_order_id"] == "WO-100"
            assert "skill_name" in skill
            assert "category" in skill
            assert "required_level" in skill
            assert "is_specialist" in skill

    def test_specialist_skills_flagged(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        skills = compiler.compile_skill_requirements(full_work_order)

        electrical = [s for s in skills if s["skill_name"] == "electrical"]
        assert len(electrical) == 1
        assert electrical[0]["is_specialist"] is True  # electrical is specialist
        assert electrical[0]["category"] == "electrical"

    def test_no_skills_returns_empty(self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder):
        skills = compiler.compile_skill_requirements(minimal_work_order)
        assert len(skills) == 0


class TestCompilePermitRequirements:
    """test_compile_permit_requirements: Verify permits compile correctly."""

    def test_permit_count(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        permits = compiler.compile_permit_requirements(full_work_order)
        assert len(permits) == 2

    def test_permit_fields(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        permits = compiler.compile_permit_requirements(full_work_order)

        for permit in permits:
            assert "work_order_id" in permit
            assert "permit_type" in permit
            assert "required" in permit
            assert "obtained" in permit
            assert "is_blocking" in permit

    def test_unobtained_permit_is_blocking(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        permits = compiler.compile_permit_requirements(full_work_order)

        confined = [p for p in permits if p["permit_type"] == "confined_space"]
        assert len(confined) == 1
        assert confined[0]["is_blocking"] is True

    def test_obtained_permit_not_blocking(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        permits = compiler.compile_permit_requirements(full_work_order)

        building = [p for p in permits if p["permit_type"] == "building_access"]
        assert len(building) == 1
        assert building[0]["is_blocking"] is False


class TestCompileMaterials:
    """test_compile_materials: Verify materials compile with availability."""

    def test_material_count(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        materials = compiler.compile_materials(full_work_order)
        assert len(materials) == 2

    def test_material_fields(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        materials = compiler.compile_materials(full_work_order)

        for mat in materials:
            assert "work_order_id" in mat
            assert mat["work_order_id"] == "WO-100"
            assert "material_id" in mat
            assert "description" in mat
            assert "quantity" in mat
            assert "unit" in mat
            assert "available" in mat

    def test_available_material(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        materials = compiler.compile_materials(full_work_order)

        splice_tray = [m for m in materials if m["material_id"] == "MAT-001"]
        assert len(splice_tray) == 1
        assert splice_tray[0]["available"] is True
        assert splice_tray[0]["quantity"] == 2

    def test_unavailable_material_with_alternative(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        materials = compiler.compile_materials(full_work_order)

        splice_kit = [m for m in materials if m["material_id"] == "MAT-002"]
        assert len(splice_kit) == 1
        assert splice_kit[0]["available"] is False
        assert splice_kit[0]["alternative"] == "MAT-003"

    def test_no_materials_returns_empty(self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder):
        materials = compiler.compile_materials(minimal_work_order)
        assert len(materials) == 0


class TestCompileMinimalData:
    """test_compile_minimal_data: Handle minimal data gracefully."""

    def test_minimal_compile_succeeds(
        self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder, minimal_engineer: EngineerProfile
    ):
        result = compiler.compile(minimal_work_order, minimal_engineer)

        assert isinstance(result, FieldCompileResult)
        assert result.work_order["work_order_id"] == "WO-MIN"
        assert result.engineer["engineer_id"] == "ENG-MIN"

    def test_minimal_has_no_skills_or_permits(
        self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder, minimal_engineer: EngineerProfile
    ):
        result = compiler.compile(minimal_work_order, minimal_engineer)

        assert len(result.skill_requirements) == 0
        assert len(result.permit_requirements) == 0
        assert len(result.materials) == 0

    def test_minimal_still_gets_ppe_precondition(
        self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder, minimal_engineer: EngineerProfile
    ):
        result = compiler.compile(minimal_work_order, minimal_engineer)

        # All work orders get PPE precondition at minimum
        assert len(result.safety_preconditions) >= 1
        types = {p["precondition_type"] for p in result.safety_preconditions}
        assert "ppe" in types

    def test_minimal_work_order_not_high_risk(
        self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder, minimal_engineer: EngineerProfile
    ):
        result = compiler.compile(minimal_work_order, minimal_engineer)

        assert result.work_order["is_high_risk"] is False

    def test_minimal_engineer_has_zero_counts(
        self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder, minimal_engineer: EngineerProfile
    ):
        result = compiler.compile(minimal_work_order, minimal_engineer)

        assert result.engineer["total_skill_count"] == 0
        assert result.engineer["valid_accreditation_count"] == 0

    def test_schedule_compiled_for_minimal(
        self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder, minimal_engineer: EngineerProfile
    ):
        result = compiler.compile(minimal_work_order, minimal_engineer)

        assert result.schedule["work_order_id"] == "WO-MIN"
        assert result.schedule["has_defined_window"] is False
