"""Deep e2e tests for cross-pack reconciliation pipeline."""

from __future__ import annotations

import pytest

from app.domain_packs.contract_margin.rules import (
    PenaltyExposureAnalyzer,
    RecoveryRecommendationEngine,
    ScopeConflictDetector,
)
from app.domain_packs.contract_margin.schemas import (
    CommercialRecoveryRecommendation,
    LeakageTrigger,
    PenaltyCondition,
    PenaltyExposureSummary,
    RateCardEntry,
    ScopeBoundaryObject,
    ScopeType,
)
from app.domain_packs.reconciliation import (
    ContractWorkOrderLinker,
    ContradictionDetector,
    EvidenceBundle,
    EvidenceChainValidator,
    MarginDiagnosisBundle,
    MarginDiagnosisReconciler,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def contract_objects() -> list[dict]:
    """Contract objects as dicts for linker."""
    return [
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
        {
            "id": "CL-004c",
            "type": "rate_card",
            "activity": "metering",
            "rate": 95.0,
            "unit": "each",
        },
        {"id": "CL-001", "type": "obligation", "description": "Monthly SLA reporting"},
        {"id": "CL-005", "type": "scope", "description": "All HV and LV maintenance"},
    ]


@pytest.fixture
def spen_work_orders() -> list[dict]:
    """SPEN work orders for reconciliation."""
    return [
        {
            "work_order_id": "WO-001",
            "work_order_type": "maintenance",
            "description": "HV switching maintenance at Glasgow substation",
            "activity": "hv_switching",
            "rate": 450.0,
            "status": "completed",
        },
        {
            "work_order_id": "WO-002",
            "work_order_type": "repair",
            "description": "Cable jointing repair Edinburgh",
            "activity": "cable_jointing",
            "rate": 180.0,
            "status": "completed",
        },
        {
            "work_order_id": "WO-003",
            "work_order_type": "construction",
            "description": "New construction overhead line",
            "activity": "new_construction",
            "rate": 500.0,
            "status": "completed",
        },
    ]


@pytest.fixture
def spen_incidents() -> list[dict]:
    """SPEN incidents for reconciliation."""
    return [
        {
            "incident_id": "INC-001",
            "type": "incident",
            "description": "Power outage affecting hv switching equipment",
            "severity": "P1",
            "status": "resolved",
            "work_order_ref": "WO-001",
        },
    ]


@pytest.fixture
def scope_boundaries() -> list[ScopeBoundaryObject]:
    return [
        ScopeBoundaryObject(
            scope_type=ScopeType.in_scope,
            description="All HV and LV maintenance",
            activities=["hv_switching", "cable_jointing", "metering"],
        ),
        ScopeBoundaryObject(
            scope_type=ScopeType.out_of_scope,
            description="New construction",
            activities=["new_construction", "greenfield"],
        ),
    ]


# ---------------------------------------------------------------------------
# Tests: Contract-Work Order Linking
# ---------------------------------------------------------------------------


class TestContractWorkOrderLinking:
    """Test contract <-> work order linkage."""

    def test_links_matching_activities(self, contract_objects, spen_work_orders):
        linker = ContractWorkOrderLinker()
        # Link each WO individually (API takes single WO)
        all_links = []
        for wo in spen_work_orders:
            links = linker.link(contract_objects, wo)
            all_links.extend(links)
        # At least the in-scope WOs should link to rate card entries
        assert len(all_links) >= 2

    def test_link_returns_cross_plane_links(self, contract_objects, spen_work_orders):
        linker = ContractWorkOrderLinker()
        links = linker.link(contract_objects, spen_work_orders[0])
        for link in links:
            assert hasattr(link, "source_id")
            assert hasattr(link, "target_id")
            assert hasattr(link, "link_type")


# ---------------------------------------------------------------------------
# Tests: Scope Conflict Detection
# ---------------------------------------------------------------------------


class TestScopeConflictDetection:
    """Test scope boundary conflict detection."""

    def test_detect_out_of_scope_work(self, scope_boundaries):
        detector = ScopeConflictDetector()
        activities = ["hv_switching", "cable_jointing", "new_construction"]
        conflicts = detector.detect_conflicts(scope_boundaries, activities)
        out_of_scope = [c for c in conflicts if c.get("conflict_type") == "out_of_scope"]
        assert len(out_of_scope) >= 1
        assert any("new_construction" in c.get("activity", "") for c in out_of_scope)

    def test_no_conflict_for_in_scope(self, scope_boundaries):
        detector = ScopeConflictDetector()
        activities = ["hv_switching", "cable_jointing"]
        conflicts = detector.detect_conflicts(scope_boundaries, activities)
        out_of_scope = [c for c in conflicts if c.get("conflict_type") == "out_of_scope"]
        assert len(out_of_scope) == 0

    def test_scope_gap_detected(self, scope_boundaries):
        """Activity not in any scope boundary."""
        detector = ScopeConflictDetector()
        activities = ["unknown_activity_xyz"]
        conflicts = detector.detect_conflicts(scope_boundaries, activities)
        gaps = [c for c in conflicts if c.get("conflict_type") == "scope_gap"]
        assert len(gaps) >= 1


# ---------------------------------------------------------------------------
# Tests: Full Reconciliation Pipeline
# ---------------------------------------------------------------------------


class TestFullReconciliationPipeline:
    """Test the complete margin diagnosis reconciliation."""

    def test_reconciler_produces_bundle(self, contract_objects, spen_work_orders, spen_incidents):
        reconciler = MarginDiagnosisReconciler()
        result = reconciler.reconcile(
            contract_objects=contract_objects,
            work_orders=spen_work_orders,
            incidents=spen_incidents,
        )
        assert isinstance(result, MarginDiagnosisBundle)
        assert result.verdict != ""

    def test_reconciler_detects_links(self, contract_objects, spen_work_orders, spen_incidents):
        reconciler = MarginDiagnosisReconciler()
        result = reconciler.reconcile(
            contract_objects=contract_objects,
            work_orders=spen_work_orders,
            incidents=spen_incidents,
        )
        assert len(result.contract_wo_links) >= 2  # WO-001 and WO-002 should link

    def test_reconciler_without_incidents(self, contract_objects, spen_work_orders):
        reconciler = MarginDiagnosisReconciler()
        result = reconciler.reconcile(
            contract_objects=contract_objects,
            work_orders=spen_work_orders,
        )
        assert isinstance(result, MarginDiagnosisBundle)


# ---------------------------------------------------------------------------
# Tests: Evidence Chain Validation
# ---------------------------------------------------------------------------


class TestEvidenceChainValidation:
    """Test evidence chain validation."""

    def _make_bundle(self, items: list[dict]) -> EvidenceBundle:
        return EvidenceBundle(
            bundle_id="test-bundle",
            domains=["contract_margin", "utilities_field"],
            evidence_items=items,
            total_items=len(items),
            confidence=0.9,
        )

    def test_complete_chain_valid(self):
        validator = EvidenceChainValidator()
        bundle = self._make_bundle(
            [
                {"type": "rate_card", "id": "CL-004"},
                {"type": "work_order", "id": "WO-001"},
                {"type": "completion_certificate", "id": "CERT-001"},
                {"type": "invoice", "id": "INV-001"},
            ]
        )
        results = validator.validate_chain(bundle)
        assert all(r["present"] for r in results)

    def test_missing_billing_evidence(self):
        validator = EvidenceChainValidator()
        bundle = self._make_bundle(
            [
                {"type": "rate_card", "id": "CL-004"},
                {"type": "work_order", "id": "WO-001"},
                {"type": "completion_certificate", "id": "CERT-001"},
            ]
        )
        results = validator.validate_chain(bundle)
        billing_stage = next((r for r in results if r["stage"] == "billing_evidence"), None)
        assert billing_stage is not None
        assert billing_stage["present"] is False

    def test_missing_all_stages(self):
        validator = EvidenceChainValidator()
        bundle = self._make_bundle([])
        results = validator.validate_chain(bundle)
        missing = [r for r in results if not r["present"]]
        assert len(missing) == 4


# ---------------------------------------------------------------------------
# Tests: Contradiction Detection
# ---------------------------------------------------------------------------


class TestContradictionDetection:
    """Test contradiction detection between domains."""

    def test_detect_with_field_data(self):
        detector = ContradictionDetector()
        contract_data = {
            "scope_boundaries": [
                {"scope_type": "in_scope", "activities": ["cable_jointing"]},
            ],
            "rate_card": [{"activity": "cable_jointing", "rate": 180.0}],
        }
        field_data = {
            "description": "Cable jointing repair",
            "scope_status": "out_of_scope",
            "rate": 250.0,
        }
        contradictions = detector.detect(contract_data, field_data)
        assert isinstance(contradictions, list)

    def test_empty_detection(self):
        detector = ContradictionDetector()
        contradictions = detector.detect({}, {})
        assert isinstance(contradictions, list)


# ---------------------------------------------------------------------------
# Tests: Recovery Recommendations
# ---------------------------------------------------------------------------


class TestRecoveryRecommendations:
    """Test recovery recommendation engine."""

    def test_generates_recommendations_for_leakage(self):
        engine = RecoveryRecommendationEngine()
        triggers = [
            LeakageTrigger(
                trigger_type="unbilled_completed_work",
                description="Completed work WO-005 has no corresponding invoice",
                severity="high",
                estimated_impact_value=5000.0,
                clause_refs=["CL-004"],
            ),
        ]
        rate_card = [RateCardEntry(activity="hv_switching", unit="day", rate=450.0)]
        recs = engine.build_recommendations(triggers, [], rate_card)
        assert len(recs) >= 1
        assert isinstance(recs[0], CommercialRecoveryRecommendation)
        assert recs[0].estimated_recovery_value == 5000.0

    def test_empty_triggers_no_recommendations(self):
        engine = RecoveryRecommendationEngine()
        recs = engine.build_recommendations([], [], [])
        assert len(recs) == 0

    def test_unknown_trigger_type_skipped(self):
        engine = RecoveryRecommendationEngine()
        triggers = [
            LeakageTrigger(
                trigger_type="completely_unknown_trigger_xyz",
                description="Unknown",
                severity="low",
            ),
        ]
        recs = engine.build_recommendations(triggers, [], [])
        assert len(recs) == 0


# ---------------------------------------------------------------------------
# Tests: Penalty Exposure
# ---------------------------------------------------------------------------


class TestPenaltyExposure:
    """Test penalty exposure analysis."""

    def test_penalty_analysis_returns_summary(self):
        analyzer = PenaltyExposureAnalyzer()
        penalties = [
            PenaltyCondition(
                clause_id="CL-003",
                description="5% per SLA breach",
                trigger="SLA breach",
                penalty_type="percentage",
                cap=30.0,
            ),
        ]
        sla_performance = {"breach_detected": True, "metric_value": 3}
        result = analyzer.analyze(penalties, sla_performance, monthly_invoice_value=100000.0)
        assert isinstance(result, PenaltyExposureSummary)
        assert result.total_penalties >= 0

    def test_no_penalties_empty(self):
        analyzer = PenaltyExposureAnalyzer()
        result = analyzer.analyze([], {})
        assert isinstance(result, PenaltyExposureSummary)
        assert result.total_penalties == 0
        assert result.active_breaches == 0
