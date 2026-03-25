"""Tests for the contract-margin leakage detection rule engine."""

from __future__ import annotations

import pytest

from domain_packs.contract_margin.rules.leakage_rules import (
    LeakageRuleEngine,
    WorkHistoryEntry,
)
from domain_packs.contract_margin.schemas.contract_schemas import (
    ParsedContract,
    PenaltyCondition,
    RateCardEntry,
)
from domain_packs.contract_margin.taxonomy.contract_taxonomy import (
    BillableCategory,
    ContractType,
)


@pytest.fixture
def engine() -> LeakageRuleEngine:
    return LeakageRuleEngine()


@pytest.fixture
def sample_contract() -> ParsedContract:
    """Create a sample contract for leakage testing."""
    return ParsedContract(
        contract_type=ContractType.master_services,
        title="Test MSA",
        billing_category=BillableCategory.time_and_materials,
        rate_card=[
            RateCardEntry(role_or_item="standard_maintenance", rate=125.0, rate_unit="hourly"),
            RateCardEntry(role_or_item="emergency_repair", rate=187.5, rate_unit="hourly"),
        ],
        clauses=[],
        penalties=[],
    )


class TestLeakageRuleEngine:
    """Tests for the LeakageRuleEngine."""

    def test_no_leakage_healthy(self, engine: LeakageRuleEngine, sample_contract: ParsedContract):
        """No issues should produce healthy verdict."""
        history = [
            WorkHistoryEntry(
                entry_id="WH-001",
                description="Scheduled maintenance",
                role="standard_maintenance",
                hours=8.0,
                actual_rate=125.0,
                date="2024-03-01",
                billed=True,
                in_original_scope=True,
            ),
        ]
        triggers = engine.evaluate(sample_contract, history)
        assert len(triggers) == 0

        diagnosis = engine.diagnose(sample_contract, history)
        assert diagnosis.verdict == "healthy"

    def test_unbilled_work_detected(self, engine: LeakageRuleEngine, sample_contract: ParsedContract):
        """Unbilled completed work should be detected."""
        history = [
            WorkHistoryEntry(
                entry_id="WH-001",
                description="Emergency repair",
                role="standard_maintenance",
                hours=6.0,
                actual_rate=125.0,
                date="2024-03-01",
                billed=False,
                in_original_scope=True,
            ),
        ]
        triggers = engine.evaluate(sample_contract, history)
        assert len(triggers) >= 1
        unbilled = [t for t in triggers if t.driver.value == "unbilled_work"]
        assert len(unbilled) >= 1
        assert unbilled[0].estimated_impact == 750.0  # 6 * 125

    def test_rate_erosion_detected(self, engine: LeakageRuleEngine, sample_contract: ParsedContract):
        """Work billed below contract rate should be flagged."""
        history = [
            WorkHistoryEntry(
                entry_id="WH-002",
                description="Maintenance work",
                role="standard_maintenance",
                hours=8.0,
                actual_rate=100.0,  # Below contract rate of 125
                date="2024-03-02",
                billed=True,
                in_original_scope=True,
            ),
        ]
        triggers = engine.evaluate(sample_contract, history)
        rate_erosion = [t for t in triggers if t.driver.value == "rate_erosion"]
        assert len(rate_erosion) >= 1
        assert rate_erosion[0].estimated_impact == 200.0  # (125 - 100) * 8

    def test_scope_creep_detected(self, engine: LeakageRuleEngine, sample_contract: ParsedContract):
        """Out-of-scope work without change order should be flagged."""
        history = [
            WorkHistoryEntry(
                entry_id="WH-003",
                description="New feature development",
                role="developer",
                hours=40.0,
                actual_rate=150.0,
                date="2024-03-03",
                billed=True,
                in_original_scope=False,
                change_order_ref=None,
            ),
        ]
        triggers = engine.evaluate(sample_contract, history)
        scope = [t for t in triggers if t.driver.value == "scope_creep"]
        assert len(scope) >= 1

    def test_missing_change_order_detected(self, engine: LeakageRuleEngine, sample_contract: ParsedContract):
        """Out-of-scope work without change order should also flag missing CO."""
        history = [
            WorkHistoryEntry(
                entry_id="WH-004",
                description="Additional work",
                role="engineer",
                hours=10.0,
                actual_rate=125.0,
                date="2024-03-04",
                billed=True,
                in_original_scope=False,
                change_order_ref=None,
            ),
        ]
        triggers = engine.evaluate(sample_contract, history)
        missing_co = [t for t in triggers if t.driver.value == "missing_change_order"]
        assert len(missing_co) >= 1

    def test_penalty_exposure_flagged(self, engine: LeakageRuleEngine):
        """Uncapped penalty with formula should be flagged."""
        contract = ParsedContract(
            contract_type=ContractType.master_services,
            title="Test MSA",
            rate_card=[],
            clauses=[],
            penalties=[
                PenaltyCondition(
                    trigger_condition="SLA breach",
                    penalty_type="liquidated_damages",
                    amount=None,
                    amount_formula="5% of monthly invoice per breach",
                    cap=None,
                ),
            ],
        )
        triggers = engine.evaluate(contract, [])
        penalty = [t for t in triggers if t.driver.value == "penalty_exposure"]
        assert len(penalty) >= 1

    def test_diagnosis_verdict_levels(self, engine: LeakageRuleEngine, sample_contract: ParsedContract):
        """Diagnosis verdict should reflect leakage severity."""
        # Small leakage
        small_history = [
            WorkHistoryEntry(
                entry_id="WH-S1",
                description="Small task",
                role="standard_maintenance",
                hours=2.0,
                actual_rate=120.0,
                date="2024-03-01",
                billed=True,
                in_original_scope=True,
            ),
        ]
        diagnosis = engine.diagnose(sample_contract, small_history)
        assert diagnosis.verdict in ("healthy", "at_risk")

        # Large leakage
        large_history = [
            WorkHistoryEntry(
                entry_id="WH-L1",
                description="Large unbilled project",
                role="standard_maintenance",
                hours=500.0,
                actual_rate=125.0,
                date="2024-03-01",
                billed=False,
                in_original_scope=True,
            ),
        ]
        diagnosis = engine.diagnose(sample_contract, large_history)
        assert diagnosis.verdict in ("leaking", "critical")
        assert diagnosis.total_estimated_leakage is not None
        assert diagnosis.total_estimated_leakage > 0
