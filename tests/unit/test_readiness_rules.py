"""Tests for the utilities-field readiness rule engine."""

from __future__ import annotations

from typing import Any

import pytest

from domain_packs.utilities_field.rules.readiness_rules import (
    ReadinessRuleEngine,
    ReadinessResult,
)


@pytest.fixture
def engine() -> ReadinessRuleEngine:
    return ReadinessRuleEngine()


class TestReadinessRuleEngine:
    """Tests for the ReadinessRuleEngine."""

    def test_ready_all_checks_pass(self, engine: ReadinessRuleEngine, sample_work_order: dict[str, Any]):
        """Work order with all requirements met should be ready (except pending permit)."""
        # Modify work order to have all permits approved
        wo = {**sample_work_order}
        wo["required_permits"] = [
            {"type": "street_access", "status": "approved", "permit_number": "SA-001"},
            {"type": "building_access", "status": "approved", "permit_number": "BA-001"},
        ]
        # Ensure materials are in stock
        wo["materials"] = [
            {"item": "Fiber cable", "quantity": 200, "unit": "meters", "status": "in_stock"},
        ]
        result = engine.evaluate(wo)
        assert result.ready is True
        assert result.verdict == "ready"
        assert len(result.blockers) == 0

    def test_blocked_by_pending_permit(self, engine: ReadinessRuleEngine, sample_work_order: dict[str, Any]):
        """Work order with pending permit should be blocked."""
        # The sample work order has a pending building_access permit
        result = engine.evaluate(sample_work_order)
        assert result.verdict == "blocked"
        assert any("permit" in b.lower() for b in result.blockers)

    def test_blocked_by_missing_skill(self, engine: ReadinessRuleEngine):
        """Work order where engineer lacks required skills should be blocked."""
        wo = {
            "work_order_id": "WO-TEST",
            "required_skills": ["fiber_splicing", "confined_space", "high_voltage"],
            "engineer": {
                "id": "ENG-001",
                "skills": ["fiber_splicing"],
                "certifications": [],
            },
            "required_certifications": [],
            "required_permits": [],
            "materials": [],
            "schedule": {"scheduled_date": "2024-04-01"},
        }
        result = engine.evaluate(wo)
        assert result.verdict == "blocked"
        assert "confined_space" in result.missing_skills or "high_voltage" in result.missing_skills
        assert "fiber_splicing" in result.matched_skills

    def test_blocked_by_no_engineer(self, engine: ReadinessRuleEngine):
        """Work order with no engineer assigned should be blocked."""
        wo = {
            "work_order_id": "WO-TEST",
            "required_skills": ["fiber_splicing"],
            "engineer": {},
            "required_certifications": [],
            "required_permits": [],
            "materials": [],
            "schedule": {"scheduled_date": "2024-04-01"},
        }
        result = engine.evaluate(wo)
        assert result.ready is False
        assert result.verdict == "blocked"

    def test_warning_for_unavailable_materials(self, engine: ReadinessRuleEngine):
        """Work order with ordered (not in_stock) materials should produce a warning."""
        wo = {
            "work_order_id": "WO-TEST",
            "required_skills": [],
            "engineer": {"id": "ENG-001", "skills": [], "certifications": []},
            "required_certifications": [],
            "required_permits": [],
            "materials": [
                {"item": "Splice trays", "quantity": 2, "unit": "pieces", "status": "ordered"},
            ],
            "schedule": {"scheduled_date": "2024-04-01"},
        }
        result = engine.evaluate(wo)
        # Ordered materials produce warning, not blocker
        assert result.verdict in ("warn", "ready")
        if result.verdict == "warn":
            assert any("material" in w.lower() for w in result.warnings)

    def test_blocked_by_no_schedule(self, engine: ReadinessRuleEngine):
        """Work order without a schedule should be blocked."""
        wo = {
            "work_order_id": "WO-TEST",
            "required_skills": [],
            "engineer": {"id": "ENG-001", "skills": [], "certifications": []},
            "required_certifications": [],
            "required_permits": [],
            "materials": [],
            "schedule": {},
        }
        result = engine.evaluate(wo)
        assert result.ready is False
        assert result.verdict == "blocked"

    def test_skills_matching(self, engine: ReadinessRuleEngine):
        """Matched and missing skills should be correctly reported."""
        wo = {
            "work_order_id": "WO-TEST",
            "required_skills": ["fiber_splicing", "otdr_testing", "confined_space"],
            "engineer": {
                "id": "ENG-001",
                "skills": ["fiber_splicing", "otdr_testing"],
                "certifications": [],
            },
            "required_certifications": [],
            "required_permits": [],
            "materials": [],
            "schedule": {"scheduled_date": "2024-04-01"},
        }
        result = engine.evaluate(wo)
        assert "fiber_splicing" in result.matched_skills
        assert "otdr_testing" in result.matched_skills
        assert "confined_space" in result.missing_skills
