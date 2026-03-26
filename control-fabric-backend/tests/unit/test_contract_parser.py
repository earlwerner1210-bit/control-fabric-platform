"""Unit tests for contract parsing logic.

Tests cover parsing of contract payloads, clause extraction, SLA normalisation,
rate card handling, scope boundaries, obligations, penalties, and billable events.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.domain_packs.contract_margin.schemas.contract import (
    BillableCategory,
    BillableEvent,
    ClauseType,
    ContractType,
    Obligation,
    ParsedContract,
    PenaltyCondition,
    PriorityLevel,
    RateCardEntry,
    ScopeType,
    SLAEntry,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_parsed_contract(overrides: dict[str, Any] | None = None) -> ParsedContract:
    """Build a ParsedContract with sensible defaults, applying overrides."""
    data: dict[str, Any] = {
        "title": "Test Contract",
        "parties": ["Party A", "Party B"],
        "contract_type": ContractType.master_services,
        "effective_date": date(2024, 1, 1),
        "expiry_date": date(2025, 12, 31),
    }
    if overrides:
        data.update(overrides)
    return ParsedContract(**data)


# ── Parsing tests ────────────────────────────────────────────────────────────


class TestParseDictPayload:
    """Test that a raw dict payload can be parsed into a ParsedContract."""

    def test_parse_dict_payload(self, sample_contract: dict[str, Any]) -> None:
        contract = ParsedContract(**sample_contract)
        assert contract.title == "SPEN Master Services Agreement – HV Network Maintenance"
        assert len(contract.parties) == 2
        assert contract.contract_type == ContractType.master_services

    def test_parse_preserves_all_fields(self, sample_contract: dict[str, Any]) -> None:
        contract = ParsedContract(**sample_contract)
        assert contract.governing_law == "Scotland"
        assert contract.payment_terms == "30 days net"
        assert contract.effective_date == date(2024, 1, 1)
        assert contract.expiry_date == date(2027, 12, 31)


class TestParseClauses:
    """Test clause extraction from contract payload."""

    def test_parse_clauses(self, sample_contract: dict[str, Any]) -> None:
        contract = ParsedContract(**sample_contract)
        assert len(contract.clauses) == 6

    def test_clause_types_correctly_assigned(self, sample_contract: dict[str, Any]) -> None:
        contract = ParsedContract(**sample_contract)
        types = [c.type for c in contract.clauses]
        assert ClauseType.obligation in types
        assert ClauseType.sla in types
        assert ClauseType.penalty in types

    def test_clause_confidence_in_range(self, sample_contract: dict[str, Any]) -> None:
        contract = ParsedContract(**sample_contract)
        for clause in contract.clauses:
            assert 0.0 <= clause.confidence <= 1.0


class TestParseSLATable:
    """Test SLA table parsing and normalisation."""

    def test_parse_sla_table(self, sample_contract: dict[str, Any]) -> None:
        contract = ParsedContract(**sample_contract)
        assert len(contract.sla_table) == 3

    def test_normalize_sla_entry_minutes(self) -> None:
        """SLA entries specified in minutes should be normalised to hours."""
        entry = SLAEntry(
            priority=PriorityLevel.critical,
            response_time_hours=0.5,
            resolution_time_hours=2.0,
        )
        assert entry.response_time_hours == 0.5
        assert entry.resolution_time_hours == 2.0

    def test_normalize_sla_entry_hours(self) -> None:
        entry = SLAEntry(
            priority=PriorityLevel.high,
            response_time_hours=2.0,
            resolution_time_hours=8.0,
        )
        assert entry.response_time_hours == 2.0
        assert entry.resolution_time_hours == 8.0

    def test_sla_availability_defaults(self) -> None:
        entry = SLAEntry(
            priority=PriorityLevel.medium,
            response_time_hours=4.0,
            resolution_time_hours=24.0,
        )
        assert entry.availability == 99.5

    def test_sla_measurement_window_validation(self) -> None:
        entry = SLAEntry(
            priority=PriorityLevel.low,
            response_time_hours=24.0,
            resolution_time_hours=72.0,
            measurement_window="quarterly",
        )
        assert entry.measurement_window == "quarterly"

    def test_sla_invalid_measurement_window_rejected(self) -> None:
        with pytest.raises(ValueError, match="measurement_window"):
            SLAEntry(
                priority=PriorityLevel.low,
                response_time_hours=24.0,
                resolution_time_hours=72.0,
                measurement_window="biennially",
            )


class TestParseRateCard:
    """Test rate card parsing and normalisation."""

    def test_parse_rate_card(self, sample_contract: dict[str, Any]) -> None:
        contract = ParsedContract(**sample_contract)
        assert len(contract.rate_card) == 3
        hv = contract.rate_card[0]
        assert hv.activity == "HV Switching"
        assert hv.rate == 450.00
        assert hv.currency == "GBP"

    def test_normalize_rate_entry_aliases(self) -> None:
        """Currency codes should be uppercased."""
        entry = RateCardEntry(activity="Test", rate=100.0, currency="gbp")
        assert entry.currency == "GBP"

    def test_rate_card_effective_rate_with_multiplier(self) -> None:
        entry = RateCardEntry(
            activity="HV Switching",
            rate=450.0,
            multipliers={"overtime": 1.5, "weekend": 2.0},
        )
        assert entry.effective_rate("overtime") == 675.0
        assert entry.effective_rate("weekend") == 900.0
        assert entry.effective_rate("standard") == 450.0

    def test_rate_card_is_active(self) -> None:
        entry = RateCardEntry(
            activity="Test",
            rate=100.0,
            effective_from=date(2024, 1, 1),
            effective_to=date(2025, 12, 31),
        )
        assert entry.is_active(date(2024, 6, 15))
        assert not entry.is_active(date(2026, 1, 1))
        assert not entry.is_active(date(2023, 12, 31))

    def test_invalid_currency_rejected(self) -> None:
        with pytest.raises(ValueError, match="3-letter ISO 4217"):
            RateCardEntry(activity="Test", rate=100.0, currency="POUNDS")


class TestExtractScopeBoundaries:
    """Test scope boundary extraction."""

    def test_extract_scope_boundaries(self, sample_contract: dict[str, Any]) -> None:
        contract = ParsedContract(**sample_contract)
        assert len(contract.scope_boundaries) == 3
        in_scope = [sb for sb in contract.scope_boundaries if sb.scope_type == ScopeType.in_scope]
        assert len(in_scope) == 1
        assert "HV Switching" in in_scope[0].activities

    def test_scope_boundary_conditional(self, sample_contract: dict[str, Any]) -> None:
        contract = ParsedContract(**sample_contract)
        conditional = [
            sb for sb in contract.scope_boundaries if sb.scope_type == ScopeType.conditional
        ]
        assert len(conditional) == 1
        assert len(conditional[0].conditions) == 2


class TestExtractObligations:
    """Test obligation extraction from clauses."""

    def test_extract_obligations_from_clauses(self) -> None:
        obligation = Obligation(
            clause_id="CL-001",
            description="Maintain minimum crew of two qualified engineers",
            frequency="per_event",
            owner="provider",
            evidence_required=["ecs_card", "confined_space_cert"],
        )
        assert obligation.clause_id == "CL-001"
        assert obligation.owner == "provider"
        assert len(obligation.evidence_required) == 2

    def test_obligation_defaults(self) -> None:
        obligation = Obligation(clause_id="CL-X", description="Test obligation")
        assert obligation.frequency == "per_event"
        assert obligation.owner == "provider"
        assert obligation.deadline_days == 30


class TestExtractPenalties:
    """Test penalty condition extraction."""

    def test_extract_penalties(self) -> None:
        penalty = PenaltyCondition(
            clause_id="CL-003",
            description="SLA breach penalty",
            trigger="response_time_exceeded",
            penalty_type="percentage",
            penalty_amount=2.0,
            cap=15.0,
            grace_period_days=0,
            cure_period_days=5,
        )
        assert penalty.penalty_amount == 2.0
        assert penalty.cap == 15.0
        assert penalty.cure_period_days == 5


class TestExtractBillableEvents:
    """Test billable event extraction."""

    def test_extract_billable_events(self) -> None:
        event = BillableEvent(
            activity="HV Switching",
            category=BillableCategory.standard,
            rate=450.0,
            unit="each",
            prerequisites=["isolation_confirmed"],
            evidence_required=["photo", "daywork_sheet"],
        )
        assert event.activity == "HV Switching"
        assert event.rate == 450.0
        assert len(event.evidence_required) == 2


class TestEdgeCases:
    """Edge cases and defaults."""

    def test_empty_input(self) -> None:
        contract = ParsedContract()
        assert contract.clauses == []
        assert contract.sla_table == []
        assert contract.rate_card == []
        assert contract.scope_boundaries == []

    def test_missing_fields_defaults(self) -> None:
        contract = ParsedContract()
        assert contract.document_type == "contract"
        assert contract.title == ""
        assert contract.contract_type == ContractType.master_services
        assert contract.governing_law == "England and Wales"
        assert contract.payment_terms == "30 days net"

    def test_clause_type_enum(self) -> None:
        assert ClauseType.obligation.value == "obligation"
        assert ClauseType.sla.value == "sla"
        assert ClauseType.penalty.value == "penalty"
        assert ClauseType.rate.value == "rate"
        assert ClauseType.scope.value == "scope"
        assert ClauseType.evidence.value == "evidence"

    def test_contract_type_enum(self) -> None:
        assert ContractType.master_services.value == "master_services"
        assert ContractType.statement_of_work.value == "statement_of_work"
        assert ContractType.change_order.value == "change_order"
        assert ContractType.amendment.value == "amendment"
        assert ContractType.framework.value == "framework"

    def test_contract_is_active(self) -> None:
        contract = _build_parsed_contract()
        assert contract.is_active(date(2024, 6, 15))
        assert not contract.is_active(date(2023, 12, 31))
        assert not contract.is_active(date(2026, 1, 1))

    def test_contract_is_active_no_dates(self) -> None:
        contract = ParsedContract()
        assert contract.is_active(date(2024, 6, 15))
