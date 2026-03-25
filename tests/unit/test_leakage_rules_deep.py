"""Deep tests for the 5 new leakage detection rules plus edge cases."""

from __future__ import annotations

import pytest

from app.domain_packs.contract_margin.rules import LeakageRuleEngine


@pytest.fixture
def engine() -> LeakageRuleEngine:
    return LeakageRuleEngine()


# ===================================================================
# _check_time_based_rate_mismatch (Rule 10)
# ===================================================================

class TestTimeBasedRateMismatch:
    """Tests for out-of-hours work billed at standard rate."""

    def test_overtime_billed_at_standard_rate(self, engine: LeakageRuleEngine):
        """Overtime work billed at standard rate should trigger leakage."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "cable_repair",
                "time_of_day": "overtime",
                "billed_rate": 100.0,
                "contract_rate": 100.0,
                "expected_multiplier": 1.5,
                "hours": 4,
            }],
        )
        time_triggers = [t for t in triggers if t.trigger_type == "time_rate_mismatch"]
        assert len(time_triggers) == 1
        # delta per hour = 150 - 100 = 50, * 4 hours = 200
        assert time_triggers[0].estimated_impact_value == 200.0

    def test_weekend_billed_at_standard_rate(self, engine: LeakageRuleEngine):
        """Weekend work billed at standard rate should trigger leakage."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "substation_check",
                "time_of_day": "weekend",
                "billed_rate": 200.0,
                "contract_rate": 200.0,
                "expected_multiplier": 1.5,
                "hours": 8,
            }],
        )
        time_triggers = [t for t in triggers if t.trigger_type == "time_rate_mismatch"]
        assert len(time_triggers) == 1
        # delta per hour = 300 - 200 = 100, * 8 = 800
        assert time_triggers[0].estimated_impact_value == 800.0

    def test_normal_hours_no_trigger(self, engine: LeakageRuleEngine):
        """Normal hours work should not trigger time rate mismatch."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "cable_repair",
                "time_of_day": "normal",
                "billed_rate": 100.0,
                "contract_rate": 100.0,
                "hours": 4,
            }],
        )
        time_triggers = [t for t in triggers if t.trigger_type == "time_rate_mismatch"]
        assert len(time_triggers) == 0

    def test_overtime_already_billed_at_premium_no_trigger(self, engine: LeakageRuleEngine):
        """Overtime work billed above contract rate should not trigger."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "cable_repair",
                "time_of_day": "overtime",
                "billed_rate": 150.0,
                "contract_rate": 100.0,
                "expected_multiplier": 1.5,
                "hours": 4,
            }],
        )
        time_triggers = [t for t in triggers if t.trigger_type == "time_rate_mismatch"]
        assert len(time_triggers) == 0


# ===================================================================
# _check_material_cost_passthrough (Rule 11)
# ===================================================================

class TestMaterialCostPassthrough:
    """Tests for materials used but not billed."""

    def test_material_not_billed(self, engine: LeakageRuleEngine):
        """Materials used but not billed should trigger leakage."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "joint_replacement",
                "material_cost": 350.0,
                "material_billed": False,
            }],
        )
        mat_triggers = [t for t in triggers if t.trigger_type == "material_cost_not_billed"]
        assert len(mat_triggers) == 1
        assert mat_triggers[0].estimated_impact_value == 350.0

    def test_material_billed_no_trigger(self, engine: LeakageRuleEngine):
        """Materials that were billed should not trigger."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "joint_replacement",
                "material_cost": 350.0,
                "material_billed": True,
            }],
        )
        mat_triggers = [t for t in triggers if t.trigger_type == "material_cost_not_billed"]
        assert len(mat_triggers) == 0

    def test_no_material_cost_no_trigger(self, engine: LeakageRuleEngine):
        """Work without material cost should not trigger."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "inspection",
            }],
        )
        mat_triggers = [t for t in triggers if t.trigger_type == "material_cost_not_billed"]
        assert len(mat_triggers) == 0


# ===================================================================
# _check_subcontractor_margin_leak (Rule 12)
# ===================================================================

class TestSubcontractorMarginLeak:
    """Tests for subcontractor cost exceeding billed rate."""

    def test_sub_cost_exceeds_billed_rate(self, engine: LeakageRuleEngine):
        """Subcontractor cost > billed rate should trigger."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "tree_cutting",
                "subcontractor_cost": 800.0,
                "billed_rate": 600.0,
                "quantity": 1,
            }],
        )
        sub_triggers = [t for t in triggers if t.trigger_type == "subcontractor_margin_leak"]
        assert len(sub_triggers) == 1
        assert sub_triggers[0].estimated_impact_value == 200.0

    def test_sub_cost_below_billed_rate_no_trigger(self, engine: LeakageRuleEngine):
        """Subcontractor cost < billed rate should not trigger."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "tree_cutting",
                "subcontractor_cost": 400.0,
                "billed_rate": 600.0,
                "quantity": 1,
            }],
        )
        sub_triggers = [t for t in triggers if t.trigger_type == "subcontractor_margin_leak"]
        assert len(sub_triggers) == 0

    def test_sub_cost_with_quantity_multiplier(self, engine: LeakageRuleEngine):
        """Impact should be multiplied by quantity."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "tree_cutting",
                "subcontractor_cost": 800.0,
                "billed_rate": 600.0,
                "quantity": 3,
            }],
        )
        sub_triggers = [t for t in triggers if t.trigger_type == "subcontractor_margin_leak"]
        assert len(sub_triggers) == 1
        # delta = 200, * 3 = 600
        assert sub_triggers[0].estimated_impact_value == 600.0


# ===================================================================
# _check_mobilisation_not_charged (Rule 13)
# ===================================================================

class TestMobilisationNotCharged:
    """Tests for remote site mobilisation not billed."""

    def test_mobilisation_not_billed(self, engine: LeakageRuleEngine):
        """Remote site mobilisation not billed should trigger."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "overhead_line_repair",
                "remote_site": True,
                "mobilisation_cost": 450.0,
                "mobilisation_billed": False,
            }],
        )
        mob_triggers = [t for t in triggers if t.trigger_type == "mobilisation_not_charged"]
        assert len(mob_triggers) == 1
        assert mob_triggers[0].estimated_impact_value == 450.0

    def test_mobilisation_billed_no_trigger(self, engine: LeakageRuleEngine):
        """Remote site mobilisation that was billed should not trigger."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "overhead_line_repair",
                "remote_site": True,
                "mobilisation_cost": 450.0,
                "mobilisation_billed": True,
            }],
        )
        mob_triggers = [t for t in triggers if t.trigger_type == "mobilisation_not_charged"]
        assert len(mob_triggers) == 0

    def test_non_remote_site_no_trigger(self, engine: LeakageRuleEngine):
        """Non-remote site work should not trigger mobilisation check."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "local_repair",
                "remote_site": False,
                "mobilisation_cost": 50.0,
                "mobilisation_billed": False,
            }],
        )
        mob_triggers = [t for t in triggers if t.trigger_type == "mobilisation_not_charged"]
        assert len(mob_triggers) == 0


# ===================================================================
# _check_warranty_period_rework (Rule 14)
# ===================================================================

class TestWarrantyPeriodRework:
    """Tests for rework within warranty period billed as new work."""

    def test_warranty_rework_billed(self, engine: LeakageRuleEngine):
        """Rework within warranty billed as new should trigger."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "cable_joint_repair",
                "is_rework": True,
                "within_warranty_period": True,
                "billed": True,
                "billed_rate": 485.0,
                "hours": 3,
            }],
        )
        war_triggers = [t for t in triggers if t.trigger_type == "warranty_rework_billed"]
        assert len(war_triggers) == 1
        assert war_triggers[0].estimated_impact_value == 1455.0  # 485 * 3

    def test_warranty_rework_not_billed_no_trigger(self, engine: LeakageRuleEngine):
        """Rework within warranty that is not billed should not trigger."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "cable_joint_repair",
                "is_rework": True,
                "within_warranty_period": True,
                "billed": False,
                "billed_rate": 485.0,
                "hours": 3,
            }],
        )
        war_triggers = [t for t in triggers if t.trigger_type == "warranty_rework_billed"]
        assert len(war_triggers) == 0

    def test_rework_outside_warranty_no_trigger(self, engine: LeakageRuleEngine):
        """Rework outside warranty period should not trigger."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "cable_joint_repair",
                "is_rework": True,
                "within_warranty_period": False,
                "billed": True,
                "billed_rate": 485.0,
                "hours": 3,
            }],
        )
        war_triggers = [t for t in triggers if t.trigger_type == "warranty_rework_billed"]
        assert len(war_triggers) == 0

    def test_non_rework_no_trigger(self, engine: LeakageRuleEngine):
        """Non-rework work should not trigger warranty check."""
        triggers = engine.evaluate(
            contract_objects=[],
            work_history=[{
                "activity": "cable_joint_repair",
                "is_rework": False,
                "within_warranty_period": True,
                "billed": True,
                "billed_rate": 485.0,
                "hours": 3,
            }],
        )
        war_triggers = [t for t in triggers if t.trigger_type == "warranty_rework_billed"]
        assert len(war_triggers) == 0


# ===================================================================
# Integration: multiple new rules fire together
# ===================================================================

class TestMultipleNewLeakageRules:
    """Test that multiple new rules can fire simultaneously."""

    def test_multiple_leakage_types_detected(self, engine: LeakageRuleEngine):
        """A work history with multiple issues should produce multiple triggers."""
        work_history = [
            {
                "activity": "cable_repair",
                "time_of_day": "overtime",
                "billed_rate": 100.0,
                "contract_rate": 100.0,
                "expected_multiplier": 1.5,
                "hours": 4,
            },
            {
                "activity": "joint_replacement",
                "material_cost": 350.0,
                "material_billed": False,
            },
            {
                "activity": "tree_cutting",
                "subcontractor_cost": 800.0,
                "billed_rate": 600.0,
                "quantity": 1,
            },
            {
                "activity": "overhead_line_repair",
                "remote_site": True,
                "mobilisation_cost": 450.0,
                "mobilisation_billed": False,
            },
            {
                "activity": "cable_joint_repair",
                "is_rework": True,
                "within_warranty_period": True,
                "billed": True,
                "billed_rate": 485.0,
                "hours": 3,
            },
        ]
        triggers = engine.evaluate(contract_objects=[], work_history=work_history)
        trigger_types = {t.trigger_type for t in triggers}

        assert "time_rate_mismatch" in trigger_types
        assert "material_cost_not_billed" in trigger_types
        assert "subcontractor_margin_leak" in trigger_types
        assert "mobilisation_not_charged" in trigger_types
        assert "warranty_rework_billed" in trigger_types
