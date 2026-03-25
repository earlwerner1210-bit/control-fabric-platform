"""Tests for the contract compiler (parser) with sample data."""

from __future__ import annotations

import pytest

from app.domain_packs.contract_margin.parsers import ContractParser
from app.domain_packs.contract_margin.schemas import (
    BillableCategory,
    BillableEvent,
    ClauseType,
    ExtractedClause,
    Obligation,
    PenaltyCondition,
    RateCardEntry,
    SLAEntry,
)


@pytest.fixture
def parser() -> ContractParser:
    return ContractParser()


@pytest.fixture
def sample_contract_text() -> str:
    return (
        "Master Services Agreement\n\n"
        "1.1 This agreement is between TelcoCorp and FieldServices Ltd.\n\n"
        "2.1 Provider shall deliver all scheduled network maintenance and equipment installation.\n\n"
        "2.2 Services include: network maintenance, equipment installation, emergency repair.\n\n"
        "3.1 Failure to meet SLA response times shall result in a penalty of 5% of monthly fees.\n\n"
        "4.1 SLA: P1: response 1hr, resolution 4hr; P2: response 2hr, resolution 8hr\n\n"
        "5.1 Rate card: standard maintenance: $125/hour; emergency repair: $187.50/hour\n\n"
    )


@pytest.fixture
def sample_contract_json() -> dict:
    return {
        "document_type": "contract",
        "title": "Master Services Agreement",
        "parties": ["TelcoCorp", "FieldServices Ltd"],
        "clauses": [
            {
                "id": "CL-001",
                "type": "obligation",
                "text": "Provider shall deliver all scheduled maintenance",
                "section": "2.1",
            },
            {
                "id": "CL-002",
                "type": "penalty",
                "text": "Failure to meet SLA response times shall result in 5% penalty",
                "section": "3.1",
            },
            {
                "id": "CL-003",
                "type": "scope",
                "text": "Services include network maintenance and equipment installation",
                "section": "2.2",
            },
        ],
        "sla_table": [
            {"priority": "P1", "response_time_hours": 1, "resolution_time_hours": 4},
            {"priority": "P2", "response_time_hours": 2, "resolution_time_hours": 8},
        ],
        "rate_card": [
            {"activity": "standard_maintenance", "rate": 125.0, "unit": "hour"},
            {"activity": "emergency_repair", "rate": 187.50, "unit": "hour"},
        ],
    }


class TestContractCompiler:
    """Tests for the ContractParser (compiler)."""

    def test_compile_obligations_from_clauses(self, parser: ContractParser, sample_contract_json: dict):
        """Obligations should be extracted from obligation-type clauses."""
        parsed = parser.parse_contract(sample_contract_json)
        obligations = parser.extract_obligations(parsed.clauses)

        assert len(obligations) >= 1
        assert all(isinstance(o, Obligation) for o in obligations)
        assert any("maintenance" in o.description.lower() for o in obligations)
        # Obligation should reference a clause
        assert all(o.clause_id for o in obligations)

    def test_compile_billable_events_from_rate_card(self, parser: ContractParser, sample_contract_json: dict):
        """Billable events should be compiled from the rate card."""
        parsed = parser.parse_contract(sample_contract_json)
        billable_events = parser.extract_billable_events(parsed.rate_card)

        assert len(billable_events) == 2
        assert all(isinstance(be, BillableEvent) for be in billable_events)

        activities = {be.activity for be in billable_events}
        assert "standard_maintenance" in activities
        assert "emergency_repair" in activities

        # T&M activities should have hourly category
        for be in billable_events:
            assert be.rate > 0
            assert be.unit == "hour"
            assert be.category == BillableCategory.time_and_materials

    def test_compile_penalty_conditions(self, parser: ContractParser, sample_contract_json: dict):
        """Penalty conditions should be extracted from penalty-type clauses."""
        parsed = parser.parse_contract(sample_contract_json)
        penalties = parser.extract_penalties(parsed.clauses)

        assert len(penalties) >= 1
        assert all(isinstance(p, PenaltyCondition) for p in penalties)
        # The penalty clause should reference SLA
        assert any("sla" in p.description.lower() or "penalty" in p.description.lower() for p in penalties)

    def test_compile_scope_boundaries(self, parser: ContractParser, sample_contract_json: dict):
        """Scope clauses should be parsed into clause objects."""
        parsed = parser.parse_contract(sample_contract_json)
        scope_clauses = [c for c in parsed.clauses if c.type == ClauseType.scope]

        assert len(scope_clauses) >= 1
        assert any("network maintenance" in c.text.lower() for c in scope_clauses)

    def test_compile_leakage_triggers(self, parser: ContractParser, sample_contract_text: str):
        """Rate card extraction should capture rates for leakage detection."""
        parsed = parser.parse_contract(sample_contract_text)

        # Rate card entries are the basis for leakage trigger analysis
        assert len(parsed.rate_card) >= 1
        for entry in parsed.rate_card:
            assert entry.rate > 0
            assert entry.activity

    def test_full_compile_pipeline(self, parser: ContractParser, sample_contract_json: dict):
        """Full compile pipeline should produce a complete ParsedContract."""
        parsed = parser.parse_contract(sample_contract_json)

        assert parsed.title == "Master Services Agreement"
        assert len(parsed.parties) == 2
        assert len(parsed.clauses) == 3
        assert len(parsed.sla_table) == 2
        assert len(parsed.rate_card) == 2

        # Compile derived objects
        obligations = parser.extract_obligations(parsed.clauses)
        penalties = parser.extract_penalties(parsed.clauses)
        billable_events = parser.extract_billable_events(parsed.rate_card)

        assert len(obligations) >= 1
        assert len(penalties) >= 1
        assert len(billable_events) == 2

        # Total rate card value
        total_rate = sum(r.rate for r in parsed.rate_card)
        assert total_rate == pytest.approx(312.50)

    def test_parse_from_text(self, parser: ContractParser, sample_contract_text: str):
        """Parser should extract clauses from raw text."""
        parsed = parser.parse_contract(sample_contract_text)

        assert parsed.document_type == "contract"
        assert len(parsed.clauses) > 0
        # Should extract SLA entries from text
        assert len(parsed.sla_table) >= 1
        # Should identify clause types
        clause_types = {c.type for c in parsed.clauses}
        assert len(clause_types) >= 1

    def test_clause_classification(self, parser: ContractParser):
        """Clause classifier should correctly identify clause types."""
        obligation_text = "Provider shall deliver all services as specified"
        penalty_text = "Failure to deliver shall result in a penalty of 10%"
        sla_text = "SLA response time must be within 4 hours"
        rate_text = "Standard rate is $125 per hour for all services"
        scope_text = "Services include network maintenance and installation"

        assert parser._classify_clause(obligation_text) == ClauseType.obligation
        assert parser._classify_clause(penalty_text) == ClauseType.penalty
        assert parser._classify_clause(sla_text) == ClauseType.sla
        assert parser._classify_clause(rate_text) == ClauseType.rate
        assert parser._classify_clause(scope_text) == ClauseType.scope
