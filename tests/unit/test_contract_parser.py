"""Tests for the contract-margin domain pack contract parser."""

from __future__ import annotations

from typing import Any

import pytest

from services.compiler_service.contract_parser import ContractParser

# Use the service-level parser for JSON-based parsing
# (domain-pack parser is text-based)


@pytest.fixture
def parser() -> ContractParser:
    return ContractParser()


@pytest.fixture
def msa_data(sample_contract: dict[str, Any]) -> dict[str, Any]:
    return sample_contract


class TestParseContract:
    """Tests for ContractParser.parse_contract."""

    def test_parse_contract_returns_all_fields(
        self, parser: ContractParser, msa_data: dict[str, Any]
    ):
        result = parser.parse_contract(msa_data)
        assert result["document_type"] == "master_services_agreement"
        assert result["title"] is not None
        assert len(result["parties"]) == 2
        assert "TelcoCorp Inc." in result["parties"]
        assert "FieldServices Ltd" in result["parties"]

    def test_parse_contract_dates(self, parser: ContractParser, msa_data: dict[str, Any]):
        result = parser.parse_contract(msa_data)
        assert result["effective_date"] == "2024-01-01"
        assert result["expiry_date"] == "2026-12-31"


class TestExtractClauses:
    """Tests for ContractParser.extract_clauses."""

    def test_extract_clauses_count(self, parser: ContractParser, msa_data: dict[str, Any]):
        clauses = parser.extract_clauses(msa_data)
        assert len(clauses) == 6

    def test_extract_clauses_types(self, parser: ContractParser, msa_data: dict[str, Any]):
        clauses = parser.extract_clauses(msa_data)
        types = [c["type"] for c in clauses]
        assert "obligation" in types
        assert "penalty" in types
        assert "sla" in types
        assert "scope" in types
        assert "rate" in types

    def test_extract_clause_penalty_details(self, parser: ContractParser, msa_data: dict[str, Any]):
        clauses = parser.extract_clauses(msa_data)
        penalty_clauses = [c for c in clauses if c["type"] == "penalty"]
        assert len(penalty_clauses) >= 1
        penalty = penalty_clauses[0]
        assert "penalty_details" in penalty
        assert penalty["penalty_details"]["penalty_percentage"] == 5.0

    def test_extract_clause_obligation_details(
        self, parser: ContractParser, msa_data: dict[str, Any]
    ):
        clauses = parser.extract_clauses(msa_data)
        obligation_clauses = [c for c in clauses if c["type"] == "obligation"]
        assert len(obligation_clauses) >= 1
        # At least one obligation should have time limit extracted
        has_time_limit = any(
            c.get("obligation_details", {}).get("time_limit_hours") is not None
            for c in obligation_clauses
        )
        assert has_time_limit

    def test_extract_clause_sla_details(self, parser: ContractParser, msa_data: dict[str, Any]):
        clauses = parser.extract_clauses(msa_data)
        sla_clauses = [c for c in clauses if c["type"] == "sla"]
        assert len(sla_clauses) >= 1
        sla = sla_clauses[0]
        assert "sla_details" in sla
        assert len(sla["sla_details"]) >= 1


class TestExtractSLATable:
    """Tests for ContractParser.extract_sla_table."""

    def test_extract_sla_table_count(self, parser: ContractParser, msa_data: dict[str, Any]):
        sla_table = parser.extract_sla_table(msa_data)
        assert len(sla_table) == 4

    def test_extract_sla_table_p1(self, parser: ContractParser, msa_data: dict[str, Any]):
        sla_table = parser.extract_sla_table(msa_data)
        p1 = [s for s in sla_table if s["priority"] == "P1"]
        assert len(p1) == 1
        assert p1[0]["response_time_hours"] == 1
        assert p1[0]["resolution_time_hours"] == 4
        assert p1[0]["availability"] == "24x7"

    def test_extract_sla_table_priorities(self, parser: ContractParser, msa_data: dict[str, Any]):
        sla_table = parser.extract_sla_table(msa_data)
        priorities = sorted([s["priority"] for s in sla_table])
        assert priorities == ["P1", "P2", "P3", "P4"]


class TestExtractRateCard:
    """Tests for ContractParser.extract_rate_card."""

    def test_extract_rate_card_count(self, parser: ContractParser, msa_data: dict[str, Any]):
        rate_card = parser.extract_rate_card(msa_data)
        assert len(rate_card) == 4

    def test_extract_rate_card_standard_maintenance(
        self, parser: ContractParser, msa_data: dict[str, Any]
    ):
        rate_card = parser.extract_rate_card(msa_data)
        standard = [r for r in rate_card if r["activity"] == "standard_maintenance"]
        assert len(standard) == 1
        assert standard[0]["rate"] == 125.00
        assert standard[0]["currency"] == "USD"
        assert standard[0]["unit"] == "hour"

    def test_extract_rate_card_all_rates_positive(
        self, parser: ContractParser, msa_data: dict[str, Any]
    ):
        rate_card = parser.extract_rate_card(msa_data)
        for entry in rate_card:
            assert entry["rate"] > 0
            assert entry["currency"] == "USD"
