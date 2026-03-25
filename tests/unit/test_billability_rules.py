"""Tests for the contract-margin billability rule engine."""

from __future__ import annotations

from typing import Any

import pytest

from domain_packs.contract_margin.rules.billability_rules import (
    BillabilityRuleEngine,
    WorkEvent,
)
from domain_packs.contract_margin.schemas.contract_schemas import (
    BillableEvent,
    ExtractedClause,
    ParsedContract,
    RateCardEntry,
    SLAEntry,
)
from domain_packs.contract_margin.taxonomy.contract_taxonomy import (
    BillableCategory,
    ClauseType,
    ContractType,
)


@pytest.fixture
def engine() -> BillabilityRuleEngine:
    return BillabilityRuleEngine()


@pytest.fixture
def sample_parsed_contract() -> ParsedContract:
    """Create a sample parsed contract for testing."""
    return ParsedContract(
        contract_type=ContractType.master_services,
        title="Test MSA",
        parties=["TelcoCorp Inc.", "FieldServices Ltd"],
        billing_category=BillableCategory.time_and_materials,
        clauses=[
            ExtractedClause(
                clause_id="CL-001",
                clause_type=ClauseType.scope,
                text="Services include: network maintenance, equipment installation, emergency repair.",
                section_ref="2.1",
            ),
            ExtractedClause(
                clause_id="CL-002",
                clause_type=ClauseType.rate,
                text="Standard rate: $125/hr.",
                section_ref="5.1",
            ),
        ],
        rate_card=[
            RateCardEntry(role_or_item="standard_maintenance", rate=125.0, rate_unit="hourly"),
            RateCardEntry(role_or_item="emergency_repair", rate=187.5, rate_unit="hourly"),
        ],
        sla_entries=[
            SLAEntry(metric_name="P1 Resolution", target_value=4, unit="hours"),
        ],
        billable_events=[
            BillableEvent(
                description="Standard maintenance work",
                category=BillableCategory.time_and_materials,
                requires_approval=False,
                excluded_activities=["travel", "admin"],
            ),
        ],
    )


class TestBillabilityRuleEngine:
    """Tests for the BillabilityRuleEngine."""

    def test_billable_standard_event(self, engine: BillabilityRuleEngine, sample_parsed_contract: ParsedContract):
        """A standard maintenance event should be billable."""
        event = WorkEvent(
            event_id="WE-001",
            description="Scheduled fiber maintenance",
            activity_type="standard_maintenance",
            hours=4.0,
            role="standard_maintenance",
            sla_met=True,
        )
        result = engine.evaluate(event, sample_parsed_contract)
        assert result.billable is True
        assert result.confidence >= 0.6
        assert result.applicable_rate == 125.0

    def test_not_billable_no_rate_card(self, engine: BillabilityRuleEngine):
        """An event with no matching rate card should not be billable (T&M contract)."""
        contract = ParsedContract(
            contract_type=ContractType.master_services,
            title="Test MSA",
            billing_category=BillableCategory.time_and_materials,
            rate_card=[],  # Empty rate card
            clauses=[],
            billable_events=[],
        )
        event = WorkEvent(
            event_id="WE-002",
            description="Some work",
            activity_type="maintenance",
            hours=4.0,
            role="engineer",
        )
        result = engine.evaluate(event, contract)
        assert result.billable is False

    def test_not_billable_excluded_activity(self, engine: BillabilityRuleEngine, sample_parsed_contract: ParsedContract):
        """An excluded activity should not be billable."""
        event = WorkEvent(
            event_id="WE-003",
            description="Travel to site",
            activity_type="travel",
            hours=2.0,
            role="standard_maintenance",
            sla_met=True,
        )
        result = engine.evaluate(event, sample_parsed_contract)
        assert result.billable is False

    def test_billable_sla_not_met_warning(self, engine: BillabilityRuleEngine, sample_parsed_contract: ParsedContract):
        """An event where SLA is not met should produce a warning but may still be billable."""
        event = WorkEvent(
            event_id="WE-004",
            description="Maintenance with SLA miss",
            activity_type="standard_maintenance",
            hours=4.0,
            role="standard_maintenance",
            sla_met=False,
        )
        result = engine.evaluate(event, sample_parsed_contract)
        # SLA miss doesn't block billability but reduces confidence
        assert any("SLA" in r.message for r in result.rule_results if not r.passed)

    def test_not_billable_missing_approval(self, engine: BillabilityRuleEngine):
        """An event requiring approval without it should not be billable."""
        contract = ParsedContract(
            contract_type=ContractType.master_services,
            title="Test MSA",
            billing_category=BillableCategory.time_and_materials,
            rate_card=[
                RateCardEntry(role_or_item="emergency_repair", rate=187.5, rate_unit="hourly"),
            ],
            clauses=[],
            billable_events=[
                BillableEvent(
                    description="emergency_repair work",
                    category=BillableCategory.time_and_materials,
                    requires_approval=True,
                    excluded_activities=[],
                ),
            ],
        )
        event = WorkEvent(
            event_id="WE-005",
            description="Emergency repair",
            activity_type="emergency_repair",
            hours=3.0,
            role="emergency_repair",
            has_approval=False,
        )
        result = engine.evaluate(event, contract)
        assert result.billable is False

    def test_fixed_price_no_rate_card_passes(self, engine: BillabilityRuleEngine):
        """Fixed-price contracts don't require a rate card."""
        contract = ParsedContract(
            contract_type=ContractType.master_services,
            title="Fixed Price MSA",
            billing_category=BillableCategory.fixed_price,
            rate_card=[],
            clauses=[],
            billable_events=[],
        )
        event = WorkEvent(
            event_id="WE-006",
            description="Milestone delivery",
            activity_type="delivery",
            hours=0,
            role="project_manager",
        )
        result = engine.evaluate(event, contract)
        # Should pass the rate card check for fixed-price
        rate_rule = [r for r in result.rule_results if r.rule_name == "has_valid_rate"]
        assert len(rate_rule) == 1
        assert rate_rule[0].passed is True
