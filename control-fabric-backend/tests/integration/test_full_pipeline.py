"""Integration tests exercising the full domain pack pipeline end-to-end.

Contract parsing → billability → leakage → scope → penalty → recovery →
reconciliation pipeline without mocking.
"""

from __future__ import annotations

import pytest

from app.domain_packs.contract_margin.parsers.contract_parser import ContractParser
from app.domain_packs.contract_margin.rules.billability import BillabilityRuleEngine
from app.domain_packs.contract_margin.rules.leakage import LeakageRuleEngine
from app.domain_packs.contract_margin.rules.penalty import PenaltyExposureAnalyzer
from app.domain_packs.contract_margin.rules.recovery import RecoveryRecommendationEngine
from app.domain_packs.contract_margin.rules.scope import ScopeConflictDetector
from app.domain_packs.contract_margin.schemas.contract import (
    ContractCompileSummary,
    ParsedContract,
    RateCardEntry,
    ScopeBoundary,
    ScopeType,
)
from app.domain_packs.reconciliation.conflict_detector import ConflictDetector
from app.domain_packs.reconciliation.evidence import (
    EvidenceAssembler,
    EvidenceChainValidator,
)
from app.domain_packs.reconciliation.linkers import (
    ContractWorkOrderLinker,
    WorkOrderIncidentLinker,
)
from app.domain_packs.reconciliation.margin_reconciler import (
    MarginDiagnosisBundle,
    MarginDiagnosisReconciler,
)


@pytest.fixture
def raw_contract() -> dict:
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


class TestFullPipelineIntegration:
    """End-to-end pipeline tests."""

    def test_parse_produces_valid_contract(self, raw_contract):
        parser = ContractParser()
        parsed = parser.parse_contract(raw_contract)
        assert isinstance(parsed, ParsedContract)
        assert parsed.title == "SPEN Managed Services Agreement"
        assert len(parsed.clauses) == 5
        assert len(parsed.sla_table) == 2
        assert len(parsed.rate_card) == 2

    def test_compile_summary_from_parsed(self, raw_contract):
        parser = ContractParser()
        parsed = parser.parse_contract(raw_contract)
        summary = ContractCompileSummary.from_parsed_contract(parsed)
        assert summary.clause_count == 5
        assert summary.sla_entry_count == 2

    def test_billability_evaluation(self, raw_contract):
        parser = ContractParser()
        parsed = parser.parse_contract(raw_contract)
        engine = BillabilityRuleEngine()
        decision = engine.evaluate(
            activity={"name": "hv_switching", "evidence": ["completion_report"]},
            rate_card=parsed.rate_card,
            obligations=parsed.obligations,
        )
        assert decision.billable is True
        assert decision.rate_applied == 450.0

    def test_billability_unknown_activity(self, raw_contract):
        parser = ContractParser()
        parsed = parser.parse_contract(raw_contract)
        engine = BillabilityRuleEngine()
        decision = engine.evaluate(
            activity={"name": "new_construction"},
            rate_card=parsed.rate_card,
            obligations=[],
        )
        assert decision.billable is False

    def test_scope_conflict_detection(self):
        detector = ScopeConflictDetector()
        boundaries = [
            ScopeBoundary(
                scope_type=ScopeType.in_scope,
                description="HV and LV maintenance",
                activities=["hv_switching", "cable_jointing"],
            ),
            ScopeBoundary(
                scope_type=ScopeType.out_of_scope,
                description="New construction",
                activities=["new_construction"],
            ),
        ]
        conflicts = detector.detect_conflicts(
            boundaries,
            [{"name": "hv_switching"}, {"name": "new_construction"}, {"name": "unknown_xyz"}],
        )
        assert len(conflicts) >= 1

    def test_penalty_exposure_with_breach(self, raw_contract):
        parser = ContractParser()
        parsed = parser.parse_contract(raw_contract)
        analyzer = PenaltyExposureAnalyzer()
        result = analyzer.analyze(
            penalty_conditions=parsed.penalties,
            sla_performance=[{"breach_detected": True, "metric_value": 3}],
            monthly_invoice_value=100000.0,
        )
        assert result.total_penalties >= 0

    def test_leakage_detection(self, raw_contract):
        parser = ContractParser()
        parsed = parser.parse_contract(raw_contract)
        engine = LeakageRuleEngine()
        triggers = engine.detect(
            activity={"name": "hv_switching", "billed": False, "status": "completed"},
            rate_card=parsed.rate_card,
            work_orders=[
                {"activity": "hv_switching", "status": "completed", "billed": False},
            ],
            obligations=parsed.obligations,
        )
        assert len(triggers) >= 1

    def test_recovery_recommendations(self):
        from app.domain_packs.contract_margin.schemas.contract import LeakageTrigger, PriorityLevel

        engine = RecoveryRecommendationEngine()
        triggers = [
            LeakageTrigger(
                trigger_type="unbilled_completed_work",
                description="WO-005 completed but not invoiced",
                severity=PriorityLevel.high,
                estimated_impact_value=3500.0,
            ),
        ]
        rate_card = [RateCardEntry(activity="hv_switching", unit="day", rate=450.0)]
        recs = engine.build_recommendations(triggers, [], rate_card)
        assert len(recs) >= 1
        assert recs[0].estimated_recovery_value == 3500.0


class TestReconciliationPipeline:
    """Test cross-domain reconciliation."""

    @pytest.fixture
    def contract_objects(self):
        return [
            {"id": "CO-1", "description": "HV switching maintenance", "rate": 450.0},
            {"id": "CO-2", "description": "Cable jointing repairs", "rate": 180.0},
        ]

    @pytest.fixture
    def work_orders(self):
        return [
            {
                "work_order_id": "WO-1",
                "description": "HV switching at Glasgow",
                "status": "completed",
                "rate": 450.0,
            },
            {
                "work_order_id": "WO-2",
                "description": "Cable jointing Edinburgh",
                "status": "completed",
                "rate": 180.0,
            },
        ]

    @pytest.fixture
    def incidents(self):
        return [
            {
                "incident_id": "INC-1",
                "description": "Power outage affecting HV switching",
                "status": "resolved",
                "work_order_refs": ["WO-1"],
            },
        ]

    def test_contract_wo_linker(self, contract_objects, work_orders):
        linker = ContractWorkOrderLinker()
        all_links = []
        for wo in work_orders:
            links = linker.link(contract_objects, wo)
            all_links.extend(links)
        assert len(all_links) >= 2

    def test_wo_incident_linker(self, work_orders, incidents):
        linker = WorkOrderIncidentLinker()
        links = linker.link(work_orders[0], incidents)
        assert len(links) >= 1
        assert links[0].link_type == "ref_match"

    def test_evidence_assembler(self, contract_objects, work_orders, incidents):
        assembler = EvidenceAssembler()
        bundle = assembler.assemble_margin_evidence(contract_objects, work_orders, incidents)
        assert bundle.total_items > 0
        assert len(bundle.domains) >= 2

    def test_evidence_chain_validator(self, contract_objects, work_orders, incidents):
        assembler = EvidenceAssembler()
        bundle = assembler.assemble_margin_evidence(contract_objects, work_orders, incidents)
        validator = EvidenceChainValidator()
        results = validator.validate_chain(bundle)
        assert len(results) == 4
        assert all("stage" in r for r in results)

    def test_full_reconciler(self, contract_objects, work_orders, incidents):
        reconciler = MarginDiagnosisReconciler()
        result = reconciler.reconcile(
            contract_objects=contract_objects,
            work_orders=work_orders,
            incidents=incidents,
        )
        assert isinstance(result, MarginDiagnosisBundle)
        assert result.verdict != ""

    def test_reconciler_without_incidents(self, contract_objects, work_orders):
        reconciler = MarginDiagnosisReconciler()
        result = reconciler.reconcile(
            contract_objects=contract_objects,
            work_orders=work_orders,
        )
        assert isinstance(result, MarginDiagnosisBundle)

    def test_conflict_detector(self):
        detector = ConflictDetector()
        conflicts = detector.detect_contract_field_conflict(
            {"description": "HV switching maintenance", "rate": 450.0},
            {
                "description": "Cable installation new site",
                "rate": 500.0,
                "work_category": "construction",
            },
        )
        assert len(conflicts) >= 1


class TestEndToEndMarginDiagnosis:
    """Full end-to-end: parse -> billability -> leakage -> scope -> penalty -> recovery -> evidence."""

    @pytest.fixture
    def parsed_contract(self, raw_contract):
        return ContractParser().parse_contract(raw_contract)

    def test_full_diagnosis_billable_activity(self, parsed_contract):
        """Full pipeline for a clearly billable activity."""
        activity = {
            "name": "hv_switching",
            "category": "standard",
            "value": 450.0,
            "scope": "in_scope",
            "evidence": ["completion_report"],
            "hours": 8,
            "daywork_sheet": True,
        }
        bill_engine = BillabilityRuleEngine()
        decision = bill_engine.evaluate(
            activity=activity,
            rate_card=parsed_contract.rate_card,
            obligations=parsed_contract.obligations,
        )
        assert decision.billable is True

        leak_engine = LeakageRuleEngine()
        triggers = leak_engine.detect(
            activity=activity,
            rate_card=parsed_contract.rate_card,
            work_orders=[
                {
                    "activity": "hv_switching",
                    "status": "completed",
                    "billed": True,
                    "value": 450.0,
                }
            ],
            obligations=parsed_contract.obligations,
        )
        unbilled = [t for t in triggers if t.trigger_type == "unbilled_completed_work"]
        assert len(unbilled) == 0

    def test_full_diagnosis_unbillable_activity(self, parsed_contract):
        """Full pipeline for an out-of-scope activity."""
        activity = {
            "name": "new_construction",
            "category": "standard",
            "value": 5000.0,
            "scope": "out_of_scope",
            "evidence": [],
            "hours": 16,
            "daywork_sheet": False,
        }
        bill_engine = BillabilityRuleEngine()
        decision = bill_engine.evaluate(
            activity=activity,
            rate_card=parsed_contract.rate_card,
            obligations=parsed_contract.obligations,
        )
        assert decision.billable is False

    def test_penalty_into_recovery(self, parsed_contract):
        """Penalty analysis feeds into recovery recommendations."""
        leak_engine = LeakageRuleEngine()
        triggers = leak_engine.detect(
            activity={"name": "hv_switching", "daywork_sheet": True, "hours": 8},
            rate_card=parsed_contract.rate_card,
            work_orders=[
                {
                    "activity": "hv_switching",
                    "status": "completed",
                    "billed": False,
                    "value": 450.0,
                }
            ],
            obligations=parsed_contract.obligations,
        )
        recovery_engine = RecoveryRecommendationEngine()
        recs = recovery_engine.build_recommendations(triggers, contract_objects=parsed_contract)
        assert len(recs) >= 1

    def test_evidence_chain_for_complete_scenario(self):
        """Evidence assembler + validator on a rich scenario."""
        assembler = EvidenceAssembler()
        bundle = assembler.assemble_margin_evidence(
            contract_objects=[
                {
                    "id": "C-1",
                    "description": "HV maintenance",
                    "rate_card_ref": "RC-1",
                    "obligation_refs": ["O-1"],
                },
            ],
            work_orders=[
                {
                    "work_order_id": "WO-1",
                    "status": "completed",
                    "completion_evidence": [{"type": "photo", "ref": "P1"}],
                    "billing_gates": [{"gate_id": "BG-1", "name": "signoff", "status": "passed"}],
                },
            ],
            incidents=[
                {
                    "incident_id": "INC-1",
                    "title": "Fault",
                    "severity": "high",
                    "resolution_summary": "Fixed",
                },
            ],
        )
        assert bundle.total_items >= 5

        validator = EvidenceChainValidator()
        results = validator.validate_chain(bundle)
        present = {r["stage"] for r in results if r["present"]}
        assert "contract_basis" in present
        assert "work_authorization" in present
        assert "execution_evidence" in present
        assert "billing_evidence" in present

    def test_scope_pipeline_conditional_unmet(self):
        """Scope detector correctly flags conditional unmet."""
        boundaries = [
            ScopeBoundary(
                scope_type=ScopeType.conditional,
                description="Emergency works require pre-approval",
                activities=["Emergency Repair"],
                conditions=["emergency_auth"],
            ),
        ]
        detector = ScopeConflictDetector()
        conflicts = detector.detect_conflicts(
            boundaries,
            [{"name": "Emergency Repair", "conditions_met": []}],
        )
        assert len(conflicts) >= 1
        assert conflicts[0]["conflict_type"] == "conditional_unmet"

    def test_scope_pipeline_no_conflict_for_in_scope(self):
        boundaries = [
            ScopeBoundary(
                scope_type=ScopeType.in_scope,
                description="Standard maintenance",
                activities=["hv_switching"],
            ),
        ]
        detector = ScopeConflictDetector()
        conflicts = detector.detect_conflicts(boundaries, [{"name": "hv_switching"}])
        assert len(conflicts) == 0

    def test_cross_domain_linking_pipeline(self):
        """Contract -> WO -> Incident linking chain."""
        co_linker = ContractWorkOrderLinker()
        wo_linker = WorkOrderIncidentLinker()

        contracts = [{"id": "C-1", "description": "HV switching maintenance scheduled"}]
        wo = {
            "work_order_id": "WO-1",
            "description": "HV switching maintenance Glasgow",
            "status": "completed",
        }
        incidents = [
            {"incident_id": "INC-1", "work_order_refs": ["WO-1"], "description": "HV fault"},
        ]

        co_links = co_linker.link(contracts, wo)
        assert len(co_links) >= 1

        wo_links = wo_linker.link(wo, incidents)
        assert len(wo_links) >= 1
        assert wo_links[0].link_type == "ref_match"
