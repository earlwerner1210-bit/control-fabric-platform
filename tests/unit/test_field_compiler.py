"""Tests for the utilities-field compiler (parser)."""

from __future__ import annotations

import pytest

from app.domain_packs.utilities_field.parsers import (
    EngineerProfileParser,
    WorkOrderParser,
)
from app.domain_packs.utilities_field.schemas import (
    EngineerProfile,
    ParsedWorkOrder,
    PermitType,
    SkillCategory,
    WorkOrderType,
)


@pytest.fixture
def wo_parser() -> WorkOrderParser:
    return WorkOrderParser()


@pytest.fixture
def eng_parser() -> EngineerProfileParser:
    return EngineerProfileParser()


@pytest.fixture
def sample_wo_data() -> dict:
    return {
        "work_order_id": "WO-001",
        "work_order_type": "maintenance",
        "description": "Scheduled fiber maintenance at central office",
        "location": "Building A, Floor 3",
        "scheduled_date": "2024-04-15",
        "priority": "normal",
        "required_skills": [
            {"skill_name": "fiber", "category": "fiber"},
            {"skill_name": "electrical", "category": "electrical"},
        ],
        "required_permits": [
            {"permit_type": "building_access", "required": True, "obtained": True},
            {"permit_type": "confined_space", "required": True, "obtained": False},
        ],
        "prerequisites": [{"type": "risk_assessment", "completed": True}],
        "estimated_duration_hours": 4.0,
        "customer": "TelcoCorp",
    }


@pytest.fixture
def sample_engineer_data() -> dict:
    return {
        "engineer_id": "ENG-001",
        "name": "John Smith",
        "skills": [
            {"skill_name": "fiber", "category": "fiber", "level": "expert"},
            {"skill_name": "electrical", "category": "electrical", "level": "qualified"},
        ],
        "accreditations": [
            {"name": "confined_space_certification", "issuing_body": "SafetyCert", "is_valid": True},
            {"name": "general_competency", "issuing_body": "TrainingCo", "is_valid": True},
        ],
        "availability": "available",
        "location": "Depot A",
    }


class TestFieldCompiler:
    """Tests for the work order and engineer profile parsers."""

    def test_compile_dispatch_preconditions(self, wo_parser: WorkOrderParser, sample_wo_data: dict):
        """Work order should compile dispatch preconditions from permits and prerequisites."""
        parsed = wo_parser.parse_work_order(sample_wo_data)

        assert isinstance(parsed, ParsedWorkOrder)
        assert len(parsed.required_permits) == 2
        # One permit obtained, one not
        obtained = [p for p in parsed.required_permits if p.obtained]
        not_obtained = [p for p in parsed.required_permits if not p.obtained]
        assert len(obtained) == 1
        assert len(not_obtained) == 1
        assert not_obtained[0].permit_type == PermitType.confined_space
        assert parsed.prerequisites is not None

    def test_compile_skill_requirements(self, wo_parser: WorkOrderParser, sample_wo_data: dict):
        """Work order should compile required skills."""
        parsed = wo_parser.parse_work_order(sample_wo_data)

        assert len(parsed.required_skills) == 2
        skill_names = {s.skill_name for s in parsed.required_skills}
        assert "fiber" in skill_names
        assert "electrical" in skill_names

        # Categories should be parsed
        skill_categories = {s.category for s in parsed.required_skills}
        assert SkillCategory.fiber in skill_categories
        assert SkillCategory.electrical in skill_categories

    def test_compile_safety_preconditions(self, wo_parser: WorkOrderParser):
        """Work order with safety-critical permits should compile safety preconditions."""
        wo_data = {
            "work_order_id": "WO-SAFETY",
            "work_order_type": "maintenance",
            "required_skills": [],
            "required_permits": [
                {"permit_type": "confined_space", "required": True, "obtained": False},
                {"permit_type": "hot_works", "required": True, "obtained": False},
                {"permit_type": "height_works", "required": True, "obtained": True},
            ],
        }
        parsed = wo_parser.parse_work_order(wo_data)

        assert len(parsed.required_permits) == 3
        confined = [p for p in parsed.required_permits if p.permit_type == PermitType.confined_space]
        hot = [p for p in parsed.required_permits if p.permit_type == PermitType.hot_works]
        height = [p for p in parsed.required_permits if p.permit_type == PermitType.height_works]
        assert len(confined) == 1 and not confined[0].obtained
        assert len(hot) == 1 and not hot[0].obtained
        assert len(height) == 1 and height[0].obtained

    def test_compile_readiness_checks(
        self,
        wo_parser: WorkOrderParser,
        eng_parser: EngineerProfileParser,
        sample_wo_data: dict,
        sample_engineer_data: dict,
    ):
        """Compiled work order and engineer profile should support readiness evaluation."""
        parsed_wo = wo_parser.parse_work_order(sample_wo_data)
        parsed_eng = eng_parser.parse_profile(sample_engineer_data)

        assert isinstance(parsed_wo, ParsedWorkOrder)
        assert isinstance(parsed_eng, EngineerProfile)

        # Engineer should have matching skills
        required_names = {s.skill_name for s in parsed_wo.required_skills}
        engineer_names = {s.skill_name for s in parsed_eng.skills}
        assert required_names.issubset(engineer_names), (
            f"Engineer missing skills: {required_names - engineer_names}"
        )

        # Engineer should have accreditations
        assert len(parsed_eng.accreditations) >= 1
        accred_names = {a.name for a in parsed_eng.accreditations}
        assert "confined_space_certification" in accred_names

    def test_parse_work_order_type(self, wo_parser: WorkOrderParser):
        """Different work order types should parse correctly."""
        for wo_type in ["installation", "maintenance", "repair", "inspection", "emergency"]:
            parsed = wo_parser.parse_work_order({
                "work_order_id": f"WO-{wo_type}",
                "work_order_type": wo_type,
            })
            assert parsed.work_order_type == WorkOrderType(wo_type)

    def test_parse_work_order_from_text(self, wo_parser: WorkOrderParser):
        """Parser should handle raw text input."""
        parsed = wo_parser.parse_work_order("WO-12345 Fiber maintenance at central office")
        assert parsed.work_order_id == "WO-12345"
        assert "Fiber maintenance" in parsed.description

    def test_parse_engineer_profile(self, eng_parser: EngineerProfileParser, sample_engineer_data: dict):
        """Engineer profile should parse all fields."""
        parsed = eng_parser.parse_profile(sample_engineer_data)

        assert parsed.engineer_id == "ENG-001"
        assert parsed.name == "John Smith"
        assert len(parsed.skills) == 2
        assert len(parsed.accreditations) == 2
        assert parsed.availability == "available"
        assert parsed.location == "Depot A"
