"""Tests for the ContractCompiler from app.domain_packs.contract_margin.compiler."""

from __future__ import annotations

from datetime import date

import pytest

from app.domain_packs.contract_margin.compiler import ContractCompiler, ContractCompileResult
from app.domain_packs.contract_margin.schemas import (
    ClauseType,
    ContractType,
    ExtractedClause,
    ParsedContract,
    RateCardEntry,
    ScopeBoundaryObject,
    ScopeType,
    SLAEntry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def compiler() -> ContractCompiler:
    return ContractCompiler()


@pytest.fixture
def full_contract() -> ParsedContract:
    """A fully-populated contract with clauses, SLA, rate card, scope boundaries."""
    return ParsedContract(
        document_type="contract",
        title="Master Services Agreement",
        effective_date=date(2024, 1, 1),
        expiry_date=date(2026, 12, 31),
        parties=["TelcoCorp Inc.", "FieldServices Ltd"],
        contract_type=ContractType.master_services,
        clauses=[
            ExtractedClause(
                id="CL-001",
                type=ClauseType.obligation,
                text="Provider shall deliver all scheduled network maintenance.",
                section="2.1",
                confidence=0.95,
            ),
            ExtractedClause(
                id="CL-002",
                type=ClauseType.penalty,
                text="Failure to meet SLA response times shall result in 5% penalty.",
                section="3.1",
                confidence=0.90,
            ),
            ExtractedClause(
                id="CL-003",
                type=ClauseType.scope,
                text="Services include network maintenance and equipment installation.",
                section="2.2",
                confidence=0.85,
            ),
            ExtractedClause(
                id="CL-004",
                type=ClauseType.obligation,
                text="Provider must provide monthly progress reports.",
                section="4.1",
                confidence=0.92,
            ),
        ],
        clause_segments=[],
        sla_table=[
            SLAEntry(
                priority="P1",
                response_time_hours=1.0,
                resolution_time_hours=4.0,
                availability="24x7",
                penalty_percentage=5.0,
                measurement_window="monthly",
            ),
            SLAEntry(
                priority="P2",
                response_time_hours=2.0,
                resolution_time_hours=8.0,
                availability="24x7",
                penalty_percentage=3.0,
            ),
            SLAEntry(
                priority="P3",
                response_time_hours=8.0,
                resolution_time_hours=24.0,
                availability="business_hours",
            ),
        ],
        rate_card=[
            RateCardEntry(
                activity="standard_maintenance",
                unit="hour",
                rate=125.00,
                currency="USD",
                escalation_rate=3.0,
                minimum_charge=250.0,
            ),
            RateCardEntry(
                activity="emergency_repair",
                unit="hour",
                rate=187.50,
                currency="USD",
                overtime_multiplier=1.5,
            ),
        ],
        scope_boundaries=[
            ScopeBoundaryObject(
                scope_type=ScopeType.in_scope,
                description="Network maintenance and monitoring",
                activities=["network_maintenance", "monitoring"],
                clause_refs=["CL-003"],
            ),
            ScopeBoundaryObject(
                scope_type=ScopeType.out_of_scope,
                description="Capital equipment procurement",
                conditions=["Requires separate PO"],
                activities=["procurement"],
                clause_refs=["CL-003"],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCompileFullContract:
    """test_compile_full_contract: Parse a contract with clauses, SLA, rate card,
    then compile and verify all control objects are generated."""

    def test_compile_produces_all_sections(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        assert isinstance(result, ContractCompileResult)
        assert len(result.clauses) > 0
        assert len(result.sla_entries) > 0
        assert len(result.rate_card_entries) > 0
        assert len(result.obligations) > 0
        assert len(result.penalties) > 0
        assert len(result.scope_boundaries) > 0

    def test_control_object_payloads_aggregated(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        # Every compiled item should appear in control_object_payloads
        expected_count = (
            len(result.clauses)
            + len(result.sla_entries)
            + len(result.rate_card_entries)
            + len(result.obligations)
            + len(result.penalties)
            + len(result.scope_boundaries)
        )
        assert len(result.control_object_payloads) == expected_count

    def test_control_object_payloads_have_type_and_payload(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        for obj in result.control_object_payloads:
            assert "type" in obj
            assert "payload" in obj
            assert obj["type"] in (
                "clause",
                "sla_entry",
                "rate_card_entry",
                "obligation",
                "penalty_condition",
                "scope_boundary",
                "billing_gate",
                "recovery_recommendation",
            )

    def test_control_objects_have_control_ids(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        for clause in result.clauses:
            assert "control_id" in clause
        for sla in result.sla_entries:
            assert "control_id" in sla
        for rc in result.rate_card_entries:
            assert "control_id" in rc


class TestCompileClausesByType:
    """test_compile_clauses_by_type: Verify obligation and penalty clauses
    are correctly categorized."""

    def test_obligation_clauses_extracted(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        obligation_clauses = [c for c in result.clauses if c["clause_type"] == "obligation"]
        assert len(obligation_clauses) >= 2  # CL-001 and CL-004
        for oc in obligation_clauses:
            assert oc["risk_level"] == "medium"

    def test_penalty_clauses_extracted(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        penalty_clauses = [c for c in result.clauses if c["clause_type"] == "penalty"]
        assert len(penalty_clauses) >= 1
        for pc in penalty_clauses:
            assert pc["risk_level"] == "high"

    def test_scope_clauses_extracted(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        scope_clauses = [c for c in result.clauses if c["clause_type"] == "scope"]
        assert len(scope_clauses) >= 1

    def test_obligations_compiled_from_clauses(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        assert len(result.obligations) >= 2
        for ob in result.obligations:
            assert ob["control_type"] == "obligation"
            assert "clause_id" in ob
            assert "description" in ob
            assert "risk_level" in ob
            assert "status" in ob
            assert ob["status"] == "active"

    def test_penalties_compiled_from_clauses(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        assert len(result.penalties) >= 1
        for pen in result.penalties:
            assert pen["control_type"] == "penalty_condition"
            assert "clause_id" in pen
            assert "description" in pen

    def test_sla_penalties_auto_generated(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        """SLA entries with penalty_percentage should auto-generate penalty conditions."""
        result = compiler.compile(full_contract)

        sla_penalties = [p for p in result.penalties if p["clause_id"].startswith("sla-")]
        # P1 and P2 SLAs have penalty percentages
        assert len(sla_penalties) >= 2
        for sp in sla_penalties:
            assert sp["penalty_type"] == "percentage"
            assert "sla_breach" in sp.get("trigger", "")


class TestCompileSLAEntries:
    """test_compile_sla_entries: Verify SLA entries are compiled with correct fields."""

    def test_sla_entry_count(self, compiler: ContractCompiler, full_contract: ParsedContract):
        result = compiler.compile(full_contract)
        assert len(result.sla_entries) == 3

    def test_sla_entry_fields(self, compiler: ContractCompiler, full_contract: ParsedContract):
        result = compiler.compile(full_contract)

        for sla in result.sla_entries:
            assert "control_type" in sla
            assert sla["control_type"] == "sla_entry"
            assert "priority" in sla
            assert "response_time_hours" in sla
            assert "resolution_time_hours" in sla
            assert "availability" in sla
            assert "measurement_window" in sla
            assert "has_penalty_clause" in sla
            assert "severity" in sla
            assert "response_to_resolution_ratio" in sla

    def test_p1_sla_severity_is_critical(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        p1 = [s for s in result.sla_entries if s["priority"] == "P1"]
        assert len(p1) == 1
        assert p1[0]["severity"] == "critical"
        assert p1[0]["response_time_hours"] == 1.0
        assert p1[0]["resolution_time_hours"] == 4.0
        assert p1[0]["has_penalty_clause"] is True

    def test_p2_sla_severity_is_error(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        p2 = [s for s in result.sla_entries if s["priority"] == "P2"]
        assert len(p2) == 1
        assert p2[0]["severity"] == "error"
        assert p2[0]["has_penalty_clause"] is True

    def test_p3_sla_no_penalty(self, compiler: ContractCompiler, full_contract: ParsedContract):
        result = compiler.compile(full_contract)

        p3 = [s for s in result.sla_entries if s["priority"] == "P3"]
        assert len(p3) == 1
        assert p3[0]["has_penalty_clause"] is False

    def test_response_to_resolution_ratio(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        p1 = [s for s in result.sla_entries if s["priority"] == "P1"][0]
        assert p1["response_to_resolution_ratio"] == pytest.approx(0.25)


class TestCompileRateCard:
    """test_compile_rate_card: Verify rate card entries compile correctly."""

    def test_rate_card_count(self, compiler: ContractCompiler, full_contract: ParsedContract):
        result = compiler.compile(full_contract)
        assert len(result.rate_card_entries) == 2

    def test_rate_card_fields(self, compiler: ContractCompiler, full_contract: ParsedContract):
        result = compiler.compile(full_contract)

        for rc in result.rate_card_entries:
            assert rc["control_type"] == "rate_card_entry"
            assert "activity" in rc
            assert "unit" in rc
            assert "rate" in rc
            assert "currency" in rc
            assert isinstance(rc["rate"], float)

    def test_standard_maintenance_rate(
        self, compiler: ContractCompiler, full_contract: ParsedContract
    ):
        result = compiler.compile(full_contract)

        sm = [r for r in result.rate_card_entries if r["activity"] == "standard_maintenance"]
        assert len(sm) == 1
        assert sm[0]["rate"] == 125.0
        assert sm[0]["currency"] == "USD"
        assert sm[0]["has_escalation_clause"] is True
        assert sm[0]["escalation_rate"] == 3.0
        assert sm[0]["has_minimum_charge"] is True
        assert sm[0]["minimum_charge"] == 250.0

    def test_emergency_repair_rate(self, compiler: ContractCompiler, full_contract: ParsedContract):
        result = compiler.compile(full_contract)

        er = [r for r in result.rate_card_entries if r["activity"] == "emergency_repair"]
        assert len(er) == 1
        assert er[0]["rate"] == 187.50
        assert er[0]["has_overtime_clause"] is True
        assert er[0]["overtime_multiplier"] == 1.5


class TestCompileEmptyContract:
    """test_compile_empty_contract: Handle empty/minimal contract gracefully."""

    def test_empty_clauses(self, compiler: ContractCompiler):
        contract = ParsedContract(document_type="contract")
        result = compiler.compile(contract)

        assert isinstance(result, ContractCompileResult)
        assert len(result.clauses) == 0
        assert len(result.sla_entries) == 0
        assert len(result.rate_card_entries) == 0
        assert len(result.obligations) == 0
        assert len(result.penalties) == 0
        assert len(result.scope_boundaries) == 0
        assert len(result.control_object_payloads) == 0

    def test_minimal_contract_with_one_clause(self, compiler: ContractCompiler):
        contract = ParsedContract(
            document_type="contract",
            title="Minimal",
            clauses=[
                ExtractedClause(
                    id="CL-ONLY",
                    type=ClauseType.obligation,
                    text="Provider shall comply.",
                    section="1.1",
                ),
            ],
        )
        result = compiler.compile(contract)

        assert len(result.clauses) == 1
        assert len(result.obligations) == 1
        assert len(result.penalties) == 0
        assert len(result.sla_entries) == 0
        assert len(result.rate_card_entries) == 0

    def test_no_sla_no_rate_card(self, compiler: ContractCompiler):
        contract = ParsedContract(
            document_type="contract",
            clauses=[
                ExtractedClause(
                    id="CL-1", type=ClauseType.penalty, text="Penalty clause.", section="5.1"
                ),
            ],
        )
        result = compiler.compile(contract)

        assert len(result.sla_entries) == 0
        assert len(result.rate_card_entries) == 0
        assert len(result.penalties) >= 1


class TestCompileScopeBoundaries:
    """test_compile_scope_boundaries: Verify scope boundaries compile correctly."""

    def test_scope_boundary_count(self, compiler: ContractCompiler, full_contract: ParsedContract):
        result = compiler.compile(full_contract)
        assert len(result.scope_boundaries) == 2

    def test_in_scope_boundary(self, compiler: ContractCompiler, full_contract: ParsedContract):
        result = compiler.compile(full_contract)

        in_scope = [s for s in result.scope_boundaries if s["scope_type"] == "in_scope"]
        assert len(in_scope) == 1
        assert in_scope[0]["is_restrictive"] is False
        assert in_scope[0]["activity_count"] == 2
        assert "network_maintenance" in in_scope[0]["activities"]

    def test_out_of_scope_boundary(self, compiler: ContractCompiler, full_contract: ParsedContract):
        result = compiler.compile(full_contract)

        out_scope = [s for s in result.scope_boundaries if s["scope_type"] == "out_of_scope"]
        assert len(out_scope) == 1
        assert out_scope[0]["is_restrictive"] is True
        assert out_scope[0]["has_conditions"] is True
        assert "Requires separate PO" in out_scope[0]["conditions"]

    def test_scope_boundary_fields(self, compiler: ContractCompiler, full_contract: ParsedContract):
        result = compiler.compile(full_contract)

        for sb in result.scope_boundaries:
            assert sb["control_type"] == "scope_boundary"
            assert "scope_type" in sb
            assert "description" in sb
            assert "conditions" in sb
            assert "clause_refs" in sb
            assert "activities" in sb
            assert "is_restrictive" in sb
            assert "has_conditions" in sb
            assert "activity_count" in sb
