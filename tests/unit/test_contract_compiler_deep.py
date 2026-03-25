"""Deep tests for ContractCompiler — Wave 1 compilation methods."""

from __future__ import annotations

from datetime import date

import pytest

from app.domain_packs.contract_margin.compiler import ContractCompiler, ContractCompileResult
from app.domain_packs.contract_margin.schemas import (
    ClauseSegment,
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
def contract_with_scope() -> ParsedContract:
    """Contract with in-scope and out-of-scope boundaries."""
    return ParsedContract(
        document_type="contract",
        title="Scope Test Contract",
        parties=["AlphaCorp", "BetaServices"],
        clauses=[
            ExtractedClause(
                id="CL-001", type=ClauseType.scope,
                text="Services include network maintenance and monitoring.",
                section="2.1",
            ),
            ExtractedClause(
                id="CL-002", type=ClauseType.obligation,
                text="Provider shall deliver all scheduled maintenance.",
                section="2.2",
            ),
        ],
        scope_boundaries=[
            ScopeBoundaryObject(
                scope_type=ScopeType.in_scope,
                description="Network maintenance and monitoring",
                activities=["network_maintenance", "monitoring"],
                clause_refs=["CL-001"],
            ),
            ScopeBoundaryObject(
                scope_type=ScopeType.out_of_scope,
                description="Capital procurement",
                conditions=["Requires separate PO"],
                activities=["procurement"],
                clause_refs=["CL-001"],
            ),
            ScopeBoundaryObject(
                scope_type=ScopeType.conditional,
                description="Emergency overtime",
                conditions=["Subject to manager approval"],
                activities=["emergency_overtime"],
                clause_refs=["CL-002"],
            ),
        ],
    )


@pytest.fixture
def contract_with_billing_gates() -> ParsedContract:
    """Contract with clauses that reference billing prerequisites."""
    return ParsedContract(
        document_type="contract",
        title="Billing Gate Contract",
        clauses=[
            ExtractedClause(
                id="CL-010", type=ClauseType.obligation,
                text="Prior approval must be obtained before commencing variation work.",
                section="3.1",
            ),
            ExtractedClause(
                id="CL-011", type=ClauseType.obligation,
                text="A signed daywork sheet must accompany all T&M claims.",
                section="3.2",
            ),
            ExtractedClause(
                id="CL-012", type=ClauseType.obligation,
                text="Completion certificate is required before final invoicing.",
                section="3.3",
            ),
            ExtractedClause(
                id="CL-013", type=ClauseType.obligation,
                text="Provider shall submit as-built drawings within 14 days.",
                section="3.4",
            ),
            ExtractedClause(
                id="CL-014", type=ClauseType.obligation,
                text="All permits must be closed out before demobilisation.",
                section="3.5",
            ),
            ExtractedClause(
                id="CL-015", type=ClauseType.obligation,
                text="A purchase order must be raised for all work exceeding threshold.",
                section="3.6",
            ),
            ExtractedClause(
                id="CL-016", type=ClauseType.obligation,
                text="Customer sign-off is required on all completed jobs.",
                section="3.7",
            ),
            ExtractedClause(
                id="CL-017", type=ClauseType.obligation,
                text="A variation order must be issued for scope changes.",
                section="3.8",
            ),
        ],
    )


@pytest.fixture
def spen_contract() -> ParsedContract:
    """Full SPEN-style contract fixture."""
    return ParsedContract(
        document_type="contract",
        title="SPEN Managed Services Agreement",
        effective_date=date(2024, 1, 1),
        expiry_date=date(2027, 12, 31),
        parties=["SPEN", "FieldForce Ltd"],
        contract_type=ContractType.master_services,
        clauses=[
            ExtractedClause(
                id="CL-S01", type=ClauseType.obligation,
                text="Provider shall maintain all safety certifications.",
                section="5.1", confidence=0.95,
            ),
            ExtractedClause(
                id="CL-S02", type=ClauseType.penalty,
                text="Failure to meet SLA shall result in 5% penalty. Breach cap at $50,000.",
                section="6.1", confidence=0.90,
            ),
            ExtractedClause(
                id="CL-S03", type=ClauseType.scope,
                text="Services include HV switching, LV fault repair, cable jointing.",
                section="1.1", confidence=0.92,
            ),
            ExtractedClause(
                id="CL-S04", type=ClauseType.obligation,
                text="Prior approval is required for all emergency callouts above threshold.",
                section="7.1", confidence=0.88,
            ),
            ExtractedClause(
                id="CL-S05", type=ClauseType.obligation,
                text="Completion certificate must be submitted before final payment.",
                section="7.2", confidence=0.91,
            ),
        ],
        sla_table=[
            SLAEntry(
                priority="P1", response_time_hours=1.0,
                resolution_time_hours=4.0, availability="24x7",
                penalty_percentage=5.0,
            ),
            SLAEntry(
                priority="P2", response_time_hours=2.0,
                resolution_time_hours=8.0, availability="24x7",
                penalty_percentage=3.0,
            ),
        ],
        rate_card=[
            RateCardEntry(
                activity="hv_switching", unit="hour", rate=150.0,
                currency="GBP", escalation_rate=2.5,
            ),
            RateCardEntry(
                activity="lv_fault_repair", unit="hour", rate=125.0,
                currency="GBP",
            ),
        ],
        scope_boundaries=[
            ScopeBoundaryObject(
                scope_type=ScopeType.in_scope,
                description="HV switching and LV fault repair",
                activities=["hv_switching", "lv_fault_repair", "cable_jointing"],
                clause_refs=["CL-S03"],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Tests: compile_scope_boundaries
# ---------------------------------------------------------------------------


class TestCompileScopeBoundariesInScope:
    def test_in_scope_boundary_compiled(
        self, compiler: ContractCompiler, contract_with_scope: ParsedContract
    ):
        result = compiler.compile(contract_with_scope)
        in_scope = [s for s in result.scope_boundaries if s["scope_type"] == "in_scope"]
        assert len(in_scope) == 1
        assert in_scope[0]["is_restrictive"] is False
        assert "network_maintenance" in in_scope[0]["activities"]


class TestCompileScopeBoundariesOutOfScope:
    def test_out_of_scope_boundary_compiled(
        self, compiler: ContractCompiler, contract_with_scope: ParsedContract
    ):
        result = compiler.compile(contract_with_scope)
        out_scope = [s for s in result.scope_boundaries if s["scope_type"] == "out_of_scope"]
        assert len(out_scope) == 1
        assert out_scope[0]["is_restrictive"] is True
        assert out_scope[0]["has_conditions"] is True


# ---------------------------------------------------------------------------
# Tests: compile_billing_gates
# ---------------------------------------------------------------------------


class TestCompileBillingGatesFromObligations:
    def test_billing_gates_extracted(
        self, compiler: ContractCompiler, contract_with_billing_gates: ParsedContract
    ):
        result = compiler.compile(contract_with_billing_gates)
        assert len(result.billing_gates) > 0
        gate_types = [g["gate_type"] for g in result.billing_gates]
        assert "prior_approval" in gate_types
        assert "daywork_sheet_signed" in gate_types
        assert "completion_certificate" in gate_types


class TestCompileBillingGatesAllTypes:
    def test_all_gate_types(
        self, compiler: ContractCompiler, contract_with_billing_gates: ParsedContract
    ):
        result = compiler.compile(contract_with_billing_gates)
        gate_types = set(g["gate_type"] for g in result.billing_gates)
        assert "prior_approval" in gate_types
        assert "purchase_order" in gate_types
        assert "variation_order" in gate_types
        assert "daywork_sheet_signed" in gate_types
        assert "completion_certificate" in gate_types
        assert "customer_sign_off" in gate_types
        assert "as_built_submitted" in gate_types
        assert "permit_closed_out" in gate_types

    def test_billing_gate_fields(
        self, compiler: ContractCompiler, contract_with_billing_gates: ParsedContract
    ):
        result = compiler.compile(contract_with_billing_gates)
        for gate in result.billing_gates:
            assert "control_id" in gate
            assert gate["control_type"] == "billing_gate"
            assert "gate_type" in gate
            assert "description" in gate
            assert "clause_id" in gate
            assert gate["satisfied"] is False


# ---------------------------------------------------------------------------
# Tests: compile_recovery_recommendations
# ---------------------------------------------------------------------------


class TestCompileRecoveryRecommendationsBackbill:
    def test_backbill_recommendation(self, compiler: ContractCompiler):
        leakage_triggers = [
            {
                "trigger_type": "unbilled_work",
                "description": "10 hours of maintenance not invoiced",
                "estimated_impact_value": 1250.0,
                "clause_refs": ["CL-001"],
            },
        ]
        recs = compiler.compile_recovery_recommendations(leakage_triggers, [])
        assert len(recs) == 1
        assert recs[0]["recommendation_type"] == "backbill"
        assert recs[0]["estimated_recovery_value"] == 1250.0
        assert recs[0]["priority"] == "high"


class TestCompileRecoveryRecommendationsRateAdjustment:
    def test_rate_adjustment_recommendation(self, compiler: ContractCompiler):
        leakage_triggers = [
            {
                "trigger_type": "rate_mismatch",
                "description": "Rate applied is below contracted rate",
                "estimated_impact_value": 500.0,
            },
        ]
        recs = compiler.compile_recovery_recommendations(leakage_triggers, [])
        assert len(recs) == 1
        assert recs[0]["recommendation_type"] == "rate_adjustment"
        assert recs[0]["priority"] == "medium"


class TestCompileRecoveryRecommendationsChangeOrder:
    def test_change_order_recommendation(self, compiler: ContractCompiler):
        leakage_triggers = [
            {
                "trigger_type": "unpriced_variation",
                "description": "Additional work performed without pricing",
                "estimated_impact_value": 3000.0,
                "clause_refs": ["CL-003"],
            },
        ]
        recs = compiler.compile_recovery_recommendations(leakage_triggers, [])
        assert len(recs) == 1
        assert recs[0]["recommendation_type"] == "change_order"
        assert recs[0]["priority"] == "high"
        assert recs[0]["estimated_recovery_value"] == 3000.0


# ---------------------------------------------------------------------------
# Tests: compile full contract with new features
# ---------------------------------------------------------------------------


class TestCompileFullContractWithScope:
    def test_scope_in_full_compile(
        self, compiler: ContractCompiler, contract_with_scope: ParsedContract
    ):
        result = compiler.compile(contract_with_scope)
        assert len(result.scope_boundaries) == 3
        types = set(s["scope_type"] for s in result.scope_boundaries)
        assert "in_scope" in types
        assert "out_of_scope" in types
        assert "conditional" in types


class TestCompileFullContractWithBillingGates:
    def test_billing_gates_in_full_compile(
        self, compiler: ContractCompiler, contract_with_billing_gates: ParsedContract
    ):
        result = compiler.compile(contract_with_billing_gates)
        assert len(result.billing_gates) >= 6
        # Billing gates should appear in control_object_payloads
        bg_payloads = [
            p for p in result.control_object_payloads if p["type"] == "billing_gate"
        ]
        assert len(bg_payloads) == len(result.billing_gates)


class TestCompilePreservesSourceLineage:
    def test_clause_ids_preserved(
        self, compiler: ContractCompiler, spen_contract: ParsedContract
    ):
        result = compiler.compile(spen_contract)
        clause_ids = [c["clause_id"] for c in result.clauses]
        assert "CL-S01" in clause_ids
        assert "CL-S02" in clause_ids

    def test_billing_gate_clause_ids(
        self, compiler: ContractCompiler, spen_contract: ParsedContract
    ):
        result = compiler.compile(spen_contract)
        for gate in result.billing_gates:
            assert gate["clause_id"].startswith("CL-")


class TestCompileCreatesNormalizedIds:
    def test_all_control_ids_are_uuids(
        self, compiler: ContractCompiler, spen_contract: ParsedContract
    ):
        import uuid as uuid_mod
        result = compiler.compile(spen_contract)
        for obj in result.control_object_payloads:
            payload = obj["payload"]
            control_id = payload.get("control_id", "")
            # Should be a valid UUID
            uuid_mod.UUID(control_id)


class TestCompileSummaryIncludesAllCounts:
    def test_all_sections_populated(
        self, compiler: ContractCompiler, spen_contract: ParsedContract
    ):
        result = compiler.compile(spen_contract)
        # Verify all sections of the result are populated for a full contract
        assert len(result.clauses) >= 5
        assert len(result.sla_entries) == 2
        assert len(result.rate_card_entries) == 2
        assert len(result.obligations) >= 2
        assert len(result.penalties) >= 1
        assert len(result.scope_boundaries) == 1
        assert len(result.billing_gates) >= 1

    def test_payload_count_matches(
        self, compiler: ContractCompiler, spen_contract: ParsedContract
    ):
        result = compiler.compile(spen_contract)
        expected = (
            len(result.clauses)
            + len(result.sla_entries)
            + len(result.rate_card_entries)
            + len(result.obligations)
            + len(result.penalties)
            + len(result.scope_boundaries)
            + len(result.billing_gates)
            + len(result.recovery_recommendations)
        )
        assert len(result.control_object_payloads) == expected


class TestCompileEmptyInput:
    def test_empty_contract(self, compiler: ContractCompiler):
        contract = ParsedContract(document_type="contract")
        result = compiler.compile(contract)
        assert isinstance(result, ContractCompileResult)
        assert len(result.clauses) == 0
        assert len(result.billing_gates) == 0
        assert len(result.recovery_recommendations) == 0
        assert len(result.control_object_payloads) == 0


class TestCompileSpenContractFixture:
    def test_spen_full_compile(
        self, compiler: ContractCompiler, spen_contract: ParsedContract
    ):
        result = compiler.compile(spen_contract)
        # All expected sections present
        assert result.clauses
        assert result.sla_entries
        assert result.rate_card_entries
        assert result.obligations
        assert result.penalties
        assert result.scope_boundaries
        assert result.billing_gates

        # Verify SLA penalty auto-generation
        sla_penalties = [
            p for p in result.penalties if p["clause_id"].startswith("sla-")
        ]
        assert len(sla_penalties) >= 2


class TestCompileRecoveryEstimatedValues:
    def test_estimated_values_from_rate_card(self, compiler: ContractCompiler):
        leakage_triggers = [
            {
                "trigger_type": "unbilled_work",
                "description": "Unbilled HV switching",
                "activity": "hv_switching",
                "estimated_impact_value": 0.0,
            },
        ]
        rate_card = [
            {"activity": "hv_switching", "rate": 150.0, "currency": "GBP"},
        ]
        recs = compiler.compile_recovery_recommendations(leakage_triggers, rate_card)
        assert len(recs) == 1
        assert recs[0]["estimated_recovery_value"] == 150.0

    def test_estimated_values_from_trigger(self, compiler: ContractCompiler):
        leakage_triggers = [
            {
                "trigger_type": "rate_mismatch",
                "description": "Under-charged rate",
                "estimated_impact_value": 750.0,
            },
        ]
        recs = compiler.compile_recovery_recommendations(leakage_triggers, [])
        assert len(recs) == 1
        assert recs[0]["estimated_recovery_value"] == 750.0
