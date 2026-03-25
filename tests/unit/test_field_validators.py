"""Tests for utilities-field validation rules."""

from __future__ import annotations

import pytest

from app.domain_packs.utilities_field.rules import (
    ReadinessRuleEngine,
    SafetyRuleEngine,
    SkillMatchEngine,
)
from app.domain_packs.utilities_field.schemas import (
    Accreditation,
    EngineerProfile,
    ParsedWorkOrder,
    PermitRequirement,
    PermitType,
    ReadinessStatus,
    SkillCategory,
    SkillRecord,
    WorkOrderType,
)


@pytest.fixture
def readiness_engine() -> ReadinessRuleEngine:
    return ReadinessRuleEngine()


@pytest.fixture
def safety_engine() -> SafetyRuleEngine:
    return SafetyRuleEngine()


@pytest.fixture
def skill_engine() -> SkillMatchEngine:
    return SkillMatchEngine()


@pytest.fixture
def ready_work_order() -> ParsedWorkOrder:
    """Work order with all requirements met."""
    return ParsedWorkOrder(
        work_order_id="WO-READY",
        work_order_type=WorkOrderType.maintenance,
        description="Standard fiber maintenance",
        required_skills=[
            SkillRecord(skill_name="fiber", category=SkillCategory.fiber),
        ],
        required_permits=[],
    )


@pytest.fixture
def qualified_engineer() -> EngineerProfile:
    """Engineer with matching skills and valid accreditations."""
    return EngineerProfile(
        engineer_id="ENG-QUAL",
        name="Jane Doe",
        skills=[
            SkillRecord(skill_name="fiber", category=SkillCategory.fiber, level="expert"),
            SkillRecord(skill_name="electrical", category=SkillCategory.electrical),
        ],
        accreditations=[
            Accreditation(name="general_competency", issuing_body="TrainingCo", is_valid=True),
            Accreditation(name="confined_space_certification", issuing_body="SafetyCert", is_valid=True),
        ],
        availability="available",
    )


class TestFieldValidators:
    """Tests for field readiness, safety, and skill validation rules."""

    def test_ready_with_blockers_fails(self, readiness_engine: ReadinessRuleEngine):
        """Work order with blockers should not be marked ready."""
        wo = ParsedWorkOrder(
            work_order_id="WO-BLOCKED",
            work_order_type=WorkOrderType.installation,
            required_skills=[
                SkillRecord(skill_name="gas", category=SkillCategory.gas),
            ],
            required_permits=[
                PermitRequirement(permit_type=PermitType.confined_space, required=True, obtained=False),
            ],
        )
        engineer = EngineerProfile(
            engineer_id="ENG-001",
            name="Bob",
            skills=[SkillRecord(skill_name="electrical", category=SkillCategory.electrical)],
            accreditations=[Accreditation(name="general_competency", is_valid=True)],
        )

        result = readiness_engine.evaluate(wo, engineer)

        assert result.status == ReadinessStatus.blocked
        assert len(result.blockers) > 0
        assert len(result.missing_prerequisites) > 0

    def test_blocked_without_reason_fails(self, readiness_engine: ReadinessRuleEngine):
        """A fully ready work order should not have any blockers."""
        wo = ParsedWorkOrder(
            work_order_id="WO-OK",
            work_order_type=WorkOrderType.maintenance,
            required_skills=[],
            required_permits=[],
        )
        engineer = EngineerProfile(
            engineer_id="ENG-OK",
            name="Alice",
            skills=[],
            accreditations=[],
        )

        result = readiness_engine.evaluate(wo, engineer)

        assert result.status == ReadinessStatus.ready
        assert len(result.blockers) == 0
        assert result.recommendation == "Clear to dispatch"

    def test_dispatch_with_blockers_fails(self, readiness_engine: ReadinessRuleEngine):
        """Missing permits should block dispatch."""
        wo = ParsedWorkOrder(
            work_order_id="WO-PERMIT",
            work_order_type=WorkOrderType.repair,
            required_skills=[],
            required_permits=[
                PermitRequirement(permit_type=PermitType.street_works, required=True, obtained=False),
                PermitRequirement(permit_type=PermitType.hot_works, required=True, obtained=False),
            ],
        )
        engineer = EngineerProfile(
            engineer_id="ENG-002",
            name="Charlie",
            skills=[],
            accreditations=[
                Accreditation(name="general_competency", is_valid=True),
                Accreditation(name="hot_works_certification", is_valid=True),
            ],
        )

        result = readiness_engine.evaluate(wo, engineer)

        assert result.status == ReadinessStatus.blocked
        permit_blockers = [b for b in result.blockers if b.blocker_type == "permit"]
        assert len(permit_blockers) >= 2

    def test_expired_accreditation_caught(self, readiness_engine: ReadinessRuleEngine):
        """Engineer with expired accreditation required by work type should be blocked."""
        wo = ParsedWorkOrder(
            work_order_id="WO-ACCRED",
            work_order_type=WorkOrderType.installation,  # requires general_competency
            required_skills=[],
            required_permits=[],
        )
        engineer = EngineerProfile(
            engineer_id="ENG-EXPIRED",
            name="Dave",
            skills=[],
            accreditations=[
                Accreditation(name="general_competency", issuing_body="TrainingCo", is_valid=False),
            ],
        )

        result = readiness_engine.evaluate(wo, engineer)

        # Installation requires general_competency; expired should block
        assert result.status == ReadinessStatus.blocked
        accred_blockers = [b for b in result.blockers if b.blocker_type == "accreditation"]
        assert len(accred_blockers) >= 1

    def test_safety_compliance_check(self, safety_engine: SafetyRuleEngine):
        """Safety engine should check confined space and hot works certifications."""
        wo = ParsedWorkOrder(
            work_order_id="WO-SAFETY",
            work_order_type=WorkOrderType.maintenance,
            required_skills=[],
            required_permits=[
                PermitRequirement(permit_type=PermitType.confined_space, required=True, obtained=True),
                PermitRequirement(permit_type=PermitType.hot_works, required=True, obtained=True),
            ],
        )
        # Engineer without required safety certifications
        engineer = EngineerProfile(
            engineer_id="ENG-UNSAFE",
            name="Eve",
            skills=[],
            accreditations=[],
        )

        results = safety_engine.evaluate(wo, engineer)

        failed = [r for r in results if not r.passed]
        assert len(failed) >= 2
        rule_names = {r.rule_name for r in failed}
        assert "confined_space_certified" in rule_names
        assert "hot_works_certified" in rule_names


class TestSkillMatching:
    """Tests for the skill matching engine."""

    def test_full_skill_match(self, skill_engine: SkillMatchEngine):
        """Engineer with all required skills should pass."""
        wo = ParsedWorkOrder(
            work_order_id="WO-MATCH",
            required_skills=[
                SkillRecord(skill_name="fiber", category=SkillCategory.fiber),
                SkillRecord(skill_name="electrical", category=SkillCategory.electrical),
            ],
        )
        engineer = EngineerProfile(
            engineer_id="ENG-MATCH",
            name="Test",
            skills=[
                SkillRecord(skill_name="fiber", category=SkillCategory.fiber),
                SkillRecord(skill_name="electrical", category=SkillCategory.electrical),
                SkillRecord(skill_name="hvac", category=SkillCategory.hvac),
            ],
        )

        result = skill_engine.evaluate_fit(wo, engineer)
        assert result.fit is True
        assert len(result.missing_skills) == 0
        assert "fiber" in result.matching_skills
        assert "electrical" in result.matching_skills

    def test_partial_skill_match(self, skill_engine: SkillMatchEngine):
        """Engineer missing some skills should fail fit check."""
        wo = ParsedWorkOrder(
            work_order_id="WO-PARTIAL",
            required_skills=[
                SkillRecord(skill_name="fiber", category=SkillCategory.fiber),
                SkillRecord(skill_name="gas", category=SkillCategory.gas),
            ],
        )
        engineer = EngineerProfile(
            engineer_id="ENG-PARTIAL",
            name="Test",
            skills=[
                SkillRecord(skill_name="fiber", category=SkillCategory.fiber),
            ],
        )

        result = skill_engine.evaluate_fit(wo, engineer)
        assert result.fit is False
        assert "gas" in result.missing_skills
        assert "fiber" in result.matching_skills
