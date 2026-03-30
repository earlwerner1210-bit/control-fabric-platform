"""Integration tests exercising the full domain pack pipeline end-to-end.

These tests verify that contract parsing → compilation → rule evaluation →
reconciliation → diagnosis works as a connected pipeline without mocking.
"""

from __future__ import annotations

import pytest

from app.domain_packs.contract_margin.compiler import ContractCompiler
from app.domain_packs.contract_margin.parsers import ContractParser
from app.domain_packs.contract_margin.rules import (
    BillabilityRuleEngine,
    PenaltyExposureAnalyzer,
    RecoveryRecommendationEngine,
    ScopeConflictDetector,
)
from app.domain_packs.contract_margin.schemas import (
    BillabilityDecision,
    LeakageTrigger,
    ParsedContract,
    PenaltyCondition,
    PenaltyExposureSummary,
    RateCardEntry,
)
from app.domain_packs.reconciliation import (
    EvidenceBundle,
    EvidenceChainValidator,
    MarginDiagnosisBundle,
    MarginDiagnosisReconciler,
)

# ---------------------------------------------------------------------------
# Full pipeline: parse → compile → evaluate → reconcile
# ---------------------------------------------------------------------------


class TestFullPipelineIntegration:
    """Test the complete domain pack pipeline."""

    @pytest.fixture
    def raw_contract(self) -> dict:
        """Simulated LLM-parsed contract output."""
        return {
            "document_type": "master_services_agreement",
            "title": "SPEN Managed Services Agreement",
            "effective_date": "2025-01-01",
            "expiry_date": "2027-12-31",
            "parties": ["SPEN", "Acme Ltd"],
            "governing_law": "Scotland",
            "payment_terms": "Net 30",
            "clauses": [
                {
                    "id": "CL-001",
                    "type": "obligation",
                    "text": "Monthly SLA reporting required",
                    "section": "5.1",
                },
                {
                    "id": "CL-002",
                    "type": "sla",
                    "text": "P1 response 2h, P2 response 4h",
                    "section": "6.1",
                },
                {
                    "id": "CL-003",
                    "type": "penalty",
                    "text": "5% penalty per SLA breach, capped at 30%",
                    "section": "7.1",
                },
                {
                    "id": "CL-004",
                    "type": "rate",
                    "text": "HV switching £450/day, cable jointing £180/each",
                    "section": "8.1",
                },
                {
                    "id": "CL-005",
                    "type": "scope",
                    "text": "All HV and LV maintenance in-scope",
                    "section": "3.1",
                },
            ],
            "sla_table": [
                {
                    "priority": "P1",
                    "response_time_hours": 2.0,
                    "resolution_time_hours": 8.0,
                    "penalty_percentage": 5.0,
                },
                {
                    "priority": "P2",
                    "response_time_hours": 4.0,
                    "resolution_time_hours": 24.0,
                    "penalty_percentage": 3.0,
                },
            ],
            "rate_card": [
                {"activity": "hv_switching", "unit": "day", "rate": 450.0, "currency": "GBP"},
                {"activity": "cable_jointing", "unit": "each", "rate": 180.0, "currency": "GBP"},
            ],
        }

    def test_parse_produces_valid_contract(self, raw_contract):
        """Parser should produce a valid ParsedContract from raw dict."""
        parser = ContractParser()
        parsed = parser.parse_contract(raw_contract)
        assert isinstance(parsed, ParsedContract)
        assert parsed.title == "SPEN Managed Services Agreement"
        assert len(parsed.clauses) == 5
        assert len(parsed.sla_table) == 2
        assert len(parsed.rate_card) == 2

    def test_compile_produces_result(self, raw_contract):
        """Compiler should produce a valid result with control objects."""
        parser = ContractParser()
        parsed = parser.parse_contract(raw_contract)

        compiler = ContractCompiler()
        result = compiler.compile(parsed)
        # Should have clauses, SLA entries, rate card entries
        assert len(result.clauses) == 5
        assert len(result.sla_entries) == 2
        assert len(result.rate_card_entries) == 2

    def test_billability_evaluation(self, raw_contract):
        """Billability engine should evaluate against rate card."""
        parser = ContractParser()
        parsed = parser.parse_contract(raw_contract)

        engine = BillabilityRuleEngine()
        decision = engine.evaluate(
            activity="hv_switching",
            rate_card=parsed.rate_card,
            obligations=[],
        )
        assert isinstance(decision, BillabilityDecision)
        assert decision.billable is True
        assert decision.rate_applied == 450.0

    def test_scope_conflict_detection(self, raw_contract):
        """Scope detector should flag out-of-scope activities."""
        parser = ContractParser()
        parsed = parser.parse_contract(raw_contract)

        detector = ScopeConflictDetector()
        activities = ["hv_switching", "new_construction"]
        conflicts = detector.detect_conflicts(parsed.scope_boundaries, activities)
        # new_construction should be a scope gap (not in any boundary)
        gaps = [c for c in conflicts if c["conflict_type"] == "scope_gap"]
        assert len(gaps) >= 1

    def test_full_reconciliation(self, raw_contract):
        """Full reconciler should produce a diagnosis bundle."""
        parser = ContractParser()
        parsed = parser.parse_contract(raw_contract)

        # Build contract objects for the linker
        contract_objects = [
            {
                "id": "CL-004",
                "type": "rate_card",
                "activity": "hv_switching",
                "rate": 450.0,
                "unit": "day",
            },
            {
                "id": "CL-004b",
                "type": "rate_card",
                "activity": "cable_jointing",
                "rate": 180.0,
                "unit": "each",
            },
            {"id": "CL-001", "type": "obligation", "description": "Monthly SLA reporting"},
        ]
        work_orders = [
            {
                "work_order_id": "WO-001",
                "description": "HV switching at Glasgow",
                "activity": "hv_switching",
                "rate": 450.0,
                "status": "completed",
            },
        ]

        reconciler = MarginDiagnosisReconciler()
        result = reconciler.reconcile(
            contract_objects=contract_objects,
            work_orders=work_orders,
        )
        assert isinstance(result, MarginDiagnosisBundle)
        assert result.verdict != ""


class TestLeakageToRecoveryPipeline:
    """Test leakage detection → recovery recommendation pipeline."""

    def test_leakage_triggers_generate_recommendations(self):
        triggers = [
            LeakageTrigger(
                trigger_type="unbilled_completed_work",
                description="WO-005 completed but not invoiced",
                severity="high",
                estimated_impact_value=3500.0,
            ),
            LeakageTrigger(
                trigger_type="rate_below_contract",
                description="Billed at £400 vs contracted £450",
                severity="medium",
                estimated_impact_value=500.0,
            ),
        ]
        rate_card = [RateCardEntry(activity="hv_switching", unit="day", rate=450.0, currency="GBP")]

        engine = RecoveryRecommendationEngine()
        recs = engine.build_recommendations(triggers, [], rate_card)
        assert len(recs) == 2
        # First should be backbill (unbilled work)
        assert recs[0].recommendation_type.value == "backbill"
        assert recs[0].estimated_recovery_value == 3500.0
        # Second should be rate adjustment
        assert recs[1].recommendation_type.value == "rate_adjustment"


class TestPenaltyAnalysisPipeline:
    """Test penalty exposure analysis pipeline."""

    def test_penalty_with_breaches(self):
        penalties = [
            PenaltyCondition(
                clause_id="CL-003",
                description="5% per SLA breach capped at 30%",
                trigger="SLA breach",
                penalty_type="percentage",
                cap=30.0,
            ),
        ]
        sla_perf = {"breach_detected": True, "metric_value": 5}

        analyzer = PenaltyExposureAnalyzer()
        result = analyzer.analyze(penalties, sla_perf, monthly_invoice_value=100000.0)
        assert isinstance(result, PenaltyExposureSummary)

    def test_penalty_without_breaches(self):
        penalties = [
            PenaltyCondition(
                clause_id="CL-003",
                description="5% per SLA breach",
                trigger="SLA breach",
                penalty_type="percentage",
            ),
        ]

        analyzer = PenaltyExposureAnalyzer()
        result = analyzer.analyze(penalties, {}, monthly_invoice_value=100000.0)
        assert isinstance(result, PenaltyExposureSummary)
        assert result.active_breaches == 0


class TestEvidenceChainIntegration:
    """Test evidence chain validation in pipeline context."""

    def test_full_chain_passes(self):
        validator = EvidenceChainValidator()
        bundle = EvidenceBundle(
            bundle_id="test",
            domains=["contract_margin", "utilities_field"],
            evidence_items=[
                {"type": "obligation", "id": "OBL-001"},
                {"type": "work_order", "id": "WO-001"},
                {"type": "daywork_sheet", "id": "DS-001"},
                {"type": "billing_gate", "id": "BG-001"},
            ],
            total_items=4,
            confidence=0.95,
        )
        results = validator.validate_chain(bundle)
        assert all(r["present"] for r in results)

    def test_partial_chain_warns(self):
        validator = EvidenceChainValidator()
        bundle = EvidenceBundle(
            bundle_id="test-partial",
            domains=["contract_margin"],
            evidence_items=[
                {"type": "rate_card", "id": "RC-001"},
                {"type": "work_order", "id": "WO-001"},
            ],
            total_items=2,
            confidence=0.6,
        )
        results = validator.validate_chain(bundle)
        missing = [r for r in results if not r["present"]]
        assert len(missing) == 2  # execution and billing missing
