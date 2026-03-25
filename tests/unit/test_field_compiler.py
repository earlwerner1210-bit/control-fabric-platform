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
        scheduled_date="2099-04-15T08:00:00",
        scheduled_end="2099-04-15T16:00:00",
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

    def test_dispatch_preconditions_generated(
        self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder, full_engineer: EngineerProfile
    ):
        result = compiler.compile(full_work_order, full_engineer)

        assert len(result.dispatch_preconditions) > 0
        # Should include permit preconditions
        permit_preconds = [
            p for p in result.dispatch_preconditions
            if p.get("control_type") == "permit_precondition"
        ]
        assert len(permit_preconds) >= 2  # building_access + confined_space

    def test_skill_requirements_generated(
        self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder, full_engineer: EngineerProfile
    ):
        result = compiler.compile(full_work_order, full_engineer)

        assert len(result.skill_requirements) > 0
        skill_names = {s["skill_name"] for s in result.skill_requirements if s.get("control_type") == "skill_requirement"}
        assert "fiber" in skill_names
        assert "electrical" in skill_names

    def test_safety_preconditions_generated(
        self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder, full_engineer: EngineerProfile
    ):
        result = compiler.compile(full_work_order, full_engineer)
        assert len(result.safety_preconditions) > 0

    def test_readiness_checks_generated(
        self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder, full_engineer: EngineerProfile
    ):
        result = compiler.compile(full_work_order, full_engineer)
        assert len(result.readiness_checks) > 0

    def test_summary_generated(
        self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder, full_engineer: EngineerProfile
    ):
        result = compiler.compile(full_work_order, full_engineer)

        assert result.summary["work_order_id"] == "WO-100"
        assert result.summary["engineer_id"] == "ENG-200"
        assert "dispatch_ready" in result.summary
        assert "total_preconditions" in result.summary
        assert "total_skill_requirements" in result.summary


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

        # Confined space permit should add: risk_assessment, method_statement, ppe, toolbox_talk, certification
        assert "toolbox_talk" in types
        assert "certification" in types

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

    def test_electrical_skill_adds_ppe(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        preconditions = compiler.compile_safety_preconditions(full_work_order)
        elec_ppe = [
            p for p in preconditions
            if p.get("category") == "electrical" and p["precondition_type"] == "ppe"
        ]
        assert len(elec_ppe) >= 1


class TestCompileSkillRequirements:
    """test_compile_skill_requirements: Verify skill requirements compile with
    category/level."""

    def test_skill_count(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        skills = compiler.compile_skill_requirements(full_work_order)
        # Direct skills + implied skills from permits
        direct_skills = [s for s in skills if s.get("control_type") == "skill_requirement"]
        assert len(direct_skills) == 2

    def test_skill_fields(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        skills = compiler.compile_skill_requirements(full_work_order)

        direct_skills = [s for s in skills if s.get("control_type") == "skill_requirement"]
        for skill in direct_skills:
            assert "work_order_id" in skill
            assert skill["work_order_id"] == "WO-100"
            assert "skill_name" in skill
            assert "category" in skill
            assert "minimum_level" in skill
            assert "is_specialist" in skill

    def test_specialist_skills_flagged(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        skills = compiler.compile_skill_requirements(full_work_order)

        electrical = [s for s in skills if s.get("skill_name") == "electrical"]
        assert len(electrical) >= 1
        assert electrical[0]["is_specialist"] is True  # electrical is specialist
        assert electrical[0]["category"] == "electrical"

    def test_implied_skills_from_permits(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        skills = compiler.compile_skill_requirements(full_work_order)
        implied = [s for s in skills if s.get("control_type") == "implied_skill_requirement"]
        # confined_space permit implies confined_space_entry skill
        assert len(implied) >= 1
        assert any("confined_space_entry" in s.get("skill_name", "") for s in implied)

    def test_no_skills_returns_empty(self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder):
        skills = compiler.compile_skill_requirements(minimal_work_order)
        # No direct skills, no implied (no permits either)
        assert len(skills) == 0


class TestCompilePermitRequirements:
    """test_compile_permit_requirements: Verify permits compile via dispatch preconditions."""

    def test_permit_preconditions_count(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        preconds = compiler.compile_dispatch_preconditions(full_work_order, [])

        permit_preconds = [p for p in preconds if p.get("control_type") == "permit_precondition"]
        assert len(permit_preconds) == 2

    def test_unobtained_permit_is_blocking(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        preconds = compiler.compile_dispatch_preconditions(full_work_order, [])

        confined = [
            p for p in preconds
            if p.get("control_type") == "permit_precondition" and p.get("permit_type") == "confined_space"
        ]
        assert len(confined) == 1
        assert confined[0]["blocking"] is True
        assert confined[0]["met"] is False

    def test_obtained_permit_not_blocking(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        preconds = compiler.compile_dispatch_preconditions(full_work_order, [])

        building = [
            p for p in preconds
            if p.get("control_type") == "permit_precondition" and p.get("permit_type") == "building_access"
        ]
        assert len(building) == 1
        assert building[0]["blocking"] is False
        assert building[0]["met"] is True


class TestCompileMaterials:
    """test_compile_materials: Verify materials are checked via dispatch preconditions."""

    def test_materials_availability_check(self, compiler: FieldCompiler, full_work_order: ParsedWorkOrder):
        preconds = compiler.compile_dispatch_preconditions(full_work_order, [])

        mat_check = [p for p in preconds if p.get("control_type") == "materials_available"]
        assert len(mat_check) == 1
        # One material is unavailable
        assert mat_check[0]["met"] is False
        assert mat_check[0]["blocking"] is True

    def test_all_available_materials_pass(self, compiler: FieldCompiler):
        wo = ParsedWorkOrder(
            work_order_id="WO-MAT-OK",
            work_order_type=WorkOrderType.maintenance,
            description="Simple maintenance",
            materials_required=[
                {"material_id": "MAT-A", "description": "Cable", "available": True},
            ],
        )
        preconds = compiler.compile_dispatch_preconditions(wo, [])

        mat_check = [p for p in preconds if p.get("control_type") == "materials_available"]
        assert len(mat_check) == 1
        assert mat_check[0]["met"] is True

    def test_no_materials_passes(self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder):
        preconds = compiler.compile_dispatch_preconditions(minimal_work_order, [])

        mat_check = [p for p in preconds if p.get("control_type") == "materials_available"]
        assert len(mat_check) == 1
        assert mat_check[0]["met"] is True


class TestCompileMinimalData:
    """test_compile_minimal_data: Handle minimal data gracefully."""

    def test_minimal_compile_succeeds(
        self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder, minimal_engineer: EngineerProfile
    ):
        result = compiler.compile(minimal_work_order, minimal_engineer)

        assert isinstance(result, FieldCompileResult)
        assert result.summary["work_order_id"] == "WO-MIN"
        assert result.summary["engineer_id"] == "ENG-MIN"

    def test_minimal_has_no_skill_requirements(
        self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder, minimal_engineer: EngineerProfile
    ):
        result = compiler.compile(minimal_work_order, minimal_engineer)

        assert len(result.skill_requirements) == 0

    def test_minimal_still_gets_ppe_precondition(
        self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder, minimal_engineer: EngineerProfile
    ):
        result = compiler.compile(minimal_work_order, minimal_engineer)

        types = {p["precondition_type"] for p in result.safety_preconditions}
        assert "ppe" in types

    def test_minimal_readiness_checks_exist(
        self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder, minimal_engineer: EngineerProfile
    ):
        result = compiler.compile(minimal_work_order, minimal_engineer)

        assert len(result.readiness_checks) > 0
        check_names = {c["check"] for c in result.readiness_checks}
        assert "engineer_availability" in check_names
        assert "skill_coverage" in check_names

    def test_minimal_summary_dispatch_ready_info(
        self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder, minimal_engineer: EngineerProfile
    ):
        result = compiler.compile(minimal_work_order, minimal_engineer)

        assert "dispatch_ready" in result.summary
        assert result.summary["total_skill_requirements"] == 0

    def test_leakage_triggers_empty_with_no_history(
        self, compiler: FieldCompiler, minimal_work_order: ParsedWorkOrder, minimal_engineer: EngineerProfile
    ):
        result = compiler.compile(minimal_work_order, minimal_engineer)

        assert len(result.leakage_triggers) == 0
