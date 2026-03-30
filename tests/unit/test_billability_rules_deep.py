"""Deep tests for billability rule engine — approval, duplicate, expiry, minimum charge,
scope conflict detection, recovery recommendations, and penalty exposure analysis."""

from __future__ import annotations

from datetime import date

import pytest

from app.domain_packs.contract_margin.rules import (
    BillabilityRuleEngine,
    PenaltyExposureAnalyzer,
    RecoveryRecommendationEngine,
    ScopeConflictDetector,
)
from app.domain_packs.contract_margin.schemas import (
    LeakageTrigger,
    PenaltyCondition,
    RateCardEntry,
    RecoveryType,
    ScopeBoundaryObject,
    ScopeType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> BillabilityRuleEngine:
    return BillabilityRuleEngine()


@pytest.fixture
def basic_rate_card() -> list[RateCardEntry]:
    return [
        RateCardEntry(activity="standard_maintenance", rate=125.0, unit="hour", currency="GBP"),
    ]


@pytest.fixture
def basic_obligations() -> list[dict]:
    return [{"text": "Provider shall deliver all scheduled maintenance", "section": "3.1"}]


# ===================================================================
# Approval threshold check (Rule 4)
# ===================================================================


class TestApprovalThresholdCheck:
    """Tests for approval_threshold_check rule."""

    def test_below_threshold_passes(self, engine: BillabilityRuleEngine):
        """Rate below approval threshold should pass."""
        rc = [RateCardEntry(activity="small_job", rate=1000.0, unit="each")]
        result = engine.evaluate(
            activity="small_job",
            rate_card=rc,
            obligations=[],  # empty obligations = auto in-scope
            approval_threshold=5000.0,
        )
        assert result.billable is True

    def test_above_threshold_no_approval_fails(self, engine: BillabilityRuleEngine):
        """Rate above threshold without approval should fail."""
        rc = [RateCardEntry(activity="big_job", rate=7500.0, unit="each")]
        result = engine.evaluate(
            activity="big_job",
            rate_card=rc,
            obligations=[],
            approval_threshold=5000.0,
            has_approval=False,
        )
        assert result.billable is False
        assert any("Exceeds approval threshold" in r for r in result.reasons)

    def test_above_threshold_with_approval_passes(self, engine: BillabilityRuleEngine):
        """Rate above threshold with approval should pass."""
        rc = [RateCardEntry(activity="big_job", rate=7500.0, unit="each")]
        result = engine.evaluate(
            activity="big_job",
            rate_card=rc,
            obligations=[],
            approval_threshold=5000.0,
            has_approval=True,
        )
        assert result.billable is True

    def test_at_exact_threshold_passes(self, engine: BillabilityRuleEngine):
        """Rate exactly at threshold should pass (only > triggers)."""
        rc = [RateCardEntry(activity="edge_job", rate=5000.0, unit="each")]
        result = engine.evaluate(
            activity="edge_job",
            rate_card=rc,
            obligations=[],
            approval_threshold=5000.0,
        )
        assert result.billable is True


# ===================================================================
# Duplicate claim check (Rule 5)
# ===================================================================


class TestDuplicateClaimCheck:
    """Tests for duplicate_claim_check rule."""

    def test_duplicate_found(
        self,
        engine: BillabilityRuleEngine,
        basic_rate_card: list[RateCardEntry],
        basic_obligations: list[dict],
    ):
        """Same activity on same date is a duplicate."""
        result = engine.evaluate(
            activity="standard_maintenance",
            rate_card=basic_rate_card,
            obligations=basic_obligations,
            work_date=date(2025, 6, 15),
            prior_claims=[{"activity": "standard_maintenance", "date": "2025-06-15"}],
        )
        assert result.billable is False
        assert any("Duplicate claim" in r for r in result.reasons)

    def test_no_duplicate_different_date(
        self,
        engine: BillabilityRuleEngine,
        basic_rate_card: list[RateCardEntry],
        basic_obligations: list[dict],
    ):
        """Same activity on different date is not a duplicate."""
        result = engine.evaluate(
            activity="standard_maintenance",
            rate_card=basic_rate_card,
            obligations=basic_obligations,
            work_date=date(2025, 6, 16),
            prior_claims=[{"activity": "standard_maintenance", "date": "2025-06-15"}],
        )
        assert result.billable is True

    def test_no_duplicate_different_activity(
        self,
        engine: BillabilityRuleEngine,
        basic_rate_card: list[RateCardEntry],
        basic_obligations: list[dict],
    ):
        """Different activity on same date is not a duplicate."""
        result = engine.evaluate(
            activity="standard_maintenance",
            rate_card=basic_rate_card,
            obligations=basic_obligations,
            work_date=date(2025, 6, 15),
            prior_claims=[{"activity": "emergency_repair", "date": "2025-06-15"}],
        )
        assert result.billable is True

    def test_no_prior_claims(
        self,
        engine: BillabilityRuleEngine,
        basic_rate_card: list[RateCardEntry],
        basic_obligations: list[dict],
    ):
        """No prior claims means no duplicate."""
        result = engine.evaluate(
            activity="standard_maintenance",
            rate_card=basic_rate_card,
            obligations=basic_obligations,
            work_date=date(2025, 6, 15),
        )
        assert result.billable is True


# ===================================================================
# Expired rate check (Rule 6)
# ===================================================================


class TestExpiredRateCheck:
    """Tests for expired_rate_check rule."""

    def test_expired_rate(self, engine: BillabilityRuleEngine, basic_obligations: list[dict]):
        """Work after rate card expiry should fail."""
        rc = [
            RateCardEntry(
                activity="standard_maintenance",
                rate=125.0,
                unit="hour",
                effective_from=date(2024, 1, 1),
                effective_to=date(2024, 12, 31),
            ),
        ]
        result = engine.evaluate(
            activity="standard_maintenance",
            rate_card=rc,
            obligations=basic_obligations,
            work_date=date(2025, 3, 1),
        )
        assert result.billable is False
        assert any("Rate card expired" in r for r in result.reasons)

    def test_valid_rate_not_expired(
        self, engine: BillabilityRuleEngine, basic_obligations: list[dict]
    ):
        """Work before rate card expiry should pass."""
        rc = [
            RateCardEntry(
                activity="standard_maintenance",
                rate=125.0,
                unit="hour",
                effective_from=date(2024, 1, 1),
                effective_to=date(2025, 12, 31),
            ),
        ]
        result = engine.evaluate(
            activity="standard_maintenance",
            rate_card=rc,
            obligations=basic_obligations,
            work_date=date(2025, 3, 1),
        )
        assert result.billable is True

    def test_no_expiry_date_passes(
        self,
        engine: BillabilityRuleEngine,
        basic_rate_card: list[RateCardEntry],
        basic_obligations: list[dict],
    ):
        """Rate card without effective_to should pass regardless of work_date."""
        result = engine.evaluate(
            activity="standard_maintenance",
            rate_card=basic_rate_card,
            obligations=basic_obligations,
            work_date=date(2030, 1, 1),
        )
        assert result.billable is True

    def test_no_work_date_passes(
        self, engine: BillabilityRuleEngine, basic_obligations: list[dict]
    ):
        """No work_date provided means expiry check is skipped."""
        rc = [
            RateCardEntry(
                activity="standard_maintenance",
                rate=125.0,
                unit="hour",
                effective_to=date(2020, 1, 1),
            ),
        ]
        result = engine.evaluate(
            activity="standard_maintenance",
            rate_card=rc,
            obligations=basic_obligations,
        )
        # Without work_date, the expiry check cannot trigger
        assert result.billable is True


# ===================================================================
# Minimum charge enforcement (Rule 7)
# ===================================================================


class TestMinimumChargeEnforcement:
    """Tests for minimum_charge_enforcement rule."""

    def test_below_minimum_applies_minimum(self, engine: BillabilityRuleEngine):
        """Rate below minimum_charge should be bumped up."""
        rc = [RateCardEntry(activity="meter_reading", rate=15.0, unit="each", minimum_charge=50.0)]
        result = engine.evaluate(
            activity="meter_reading",
            rate_card=rc,
            obligations=[],
        )
        assert result.billable is True
        assert result.rate_applied == 50.0

    def test_above_minimum_keeps_rate(self, engine: BillabilityRuleEngine):
        """Rate above minimum_charge should be unchanged."""
        rc = [
            RateCardEntry(activity="cable_jointing", rate=485.0, unit="each", minimum_charge=50.0)
        ]
        result = engine.evaluate(
            activity="cable_jointing",
            rate_card=rc,
            obligations=[],
        )
        assert result.billable is True
        assert result.rate_applied == 485.0

    def test_no_minimum_charge_keeps_rate(
        self, engine: BillabilityRuleEngine, basic_rate_card: list[RateCardEntry]
    ):
        """No minimum_charge means rate is unchanged."""
        result = engine.evaluate(
            activity="standard_maintenance",
            rate_card=basic_rate_card,
            obligations=[],
        )
        assert result.rate_applied == 125.0


# ===================================================================
# ScopeConflictDetector
# ===================================================================


class TestScopeConflictDetector:
    """Tests for ScopeConflictDetector."""

    @pytest.fixture
    def detector(self) -> ScopeConflictDetector:
        return ScopeConflictDetector()

    @pytest.fixture
    def scope_boundaries(self) -> list[ScopeBoundaryObject]:
        return [
            ScopeBoundaryObject(
                scope_type=ScopeType.in_scope,
                description="Network maintenance and repair",
                activities=["network_maintenance", "fault_repair"],
            ),
            ScopeBoundaryObject(
                scope_type=ScopeType.out_of_scope,
                description="Software development",
                activities=["software_development"],
            ),
            ScopeBoundaryObject(
                scope_type=ScopeType.conditional,
                description="Emergency work after hours",
                activities=["emergency_callout"],
                conditions=["Prior approval from control room", "Within 50km radius"],
            ),
        ]

    def test_in_scope_no_conflict(
        self, detector: ScopeConflictDetector, scope_boundaries: list[ScopeBoundaryObject]
    ):
        conflicts = detector.detect_conflicts(scope_boundaries, ["network_maintenance"])
        assert len(conflicts) == 0

    def test_out_of_scope_conflict(
        self, detector: ScopeConflictDetector, scope_boundaries: list[ScopeBoundaryObject]
    ):
        conflicts = detector.detect_conflicts(scope_boundaries, ["software_development"])
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "out_of_scope"
        assert conflicts[0]["severity"] == "error"

    def test_conditional_unmet_conflict(
        self, detector: ScopeConflictDetector, scope_boundaries: list[ScopeBoundaryObject]
    ):
        conflicts = detector.detect_conflicts(scope_boundaries, ["emergency_callout"])
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "conditional_unmet"
        assert conflicts[0]["severity"] == "warning"

    def test_scope_gap_conflict(
        self, detector: ScopeConflictDetector, scope_boundaries: list[ScopeBoundaryObject]
    ):
        conflicts = detector.detect_conflicts(scope_boundaries, ["environmental_survey"])
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "scope_gap"
        assert conflicts[0]["severity"] == "warning"

    def test_multiple_conflicts(
        self, detector: ScopeConflictDetector, scope_boundaries: list[ScopeBoundaryObject]
    ):
        conflicts = detector.detect_conflicts(
            scope_boundaries,
            ["software_development", "environmental_survey", "network_maintenance"],
        )
        assert len(conflicts) == 2  # out_of_scope + scope_gap; in_scope has no conflict
        types = {c["conflict_type"] for c in conflicts}
        assert "out_of_scope" in types
        assert "scope_gap" in types

    def test_empty_activities_no_conflicts(
        self, detector: ScopeConflictDetector, scope_boundaries: list[ScopeBoundaryObject]
    ):
        conflicts = detector.detect_conflicts(scope_boundaries, [])
        assert len(conflicts) == 0


# ===================================================================
# RecoveryRecommendationEngine
# ===================================================================


class TestRecoveryRecommendationEngine:
    """Tests for RecoveryRecommendationEngine."""

    @pytest.fixture
    def recovery_engine(self) -> RecoveryRecommendationEngine:
        return RecoveryRecommendationEngine()

    @pytest.fixture
    def sample_rate_card(self) -> list[RateCardEntry]:
        return [
            RateCardEntry(activity="cable_jointing", rate=485.0, unit="each"),
            RateCardEntry(activity="fault_repair", rate=275.0, unit="each"),
        ]

    def test_unbilled_work_maps_to_backbill(
        self, recovery_engine: RecoveryRecommendationEngine, sample_rate_card: list[RateCardEntry]
    ):
        triggers = [
            LeakageTrigger(
                trigger_type="unbilled_completed_work",
                description="Work completed but not billed",
                severity="error",
                estimated_impact_value=750.0,
            ),
        ]
        recs = recovery_engine.build_recommendations(triggers, [], sample_rate_card)
        assert len(recs) == 1
        assert recs[0].recommendation_type == RecoveryType.backbill
        assert recs[0].estimated_recovery_value == 750.0

    def test_rate_below_contract_maps_to_rate_adjustment(
        self, recovery_engine: RecoveryRecommendationEngine, sample_rate_card: list[RateCardEntry]
    ):
        triggers = [
            LeakageTrigger(
                trigger_type="rate_below_contract",
                description="Billed below contract rate",
                severity="warning",
                estimated_impact_value=200.0,
            ),
        ]
        recs = recovery_engine.build_recommendations(triggers, [], sample_rate_card)
        assert len(recs) == 1
        assert recs[0].recommendation_type == RecoveryType.rate_adjustment

    def test_penalty_exposure_maps_to_penalty_waiver(
        self, recovery_engine: RecoveryRecommendationEngine, sample_rate_card: list[RateCardEntry]
    ):
        triggers = [
            LeakageTrigger(
                trigger_type="penalty_exposure_unmitigated",
                description="Penalty breach detected",
                severity="critical",
            ),
        ]
        recs = recovery_engine.build_recommendations(triggers, [], sample_rate_card)
        assert len(recs) == 1
        assert recs[0].recommendation_type == RecoveryType.penalty_waiver

    def test_scope_creep_maps_to_change_order(
        self, recovery_engine: RecoveryRecommendationEngine, sample_rate_card: list[RateCardEntry]
    ):
        triggers = [
            LeakageTrigger(
                trigger_type="scope_creep_detected",
                description="Out-of-scope work",
                severity="error",
                estimated_impact_value=3500.0,
            ),
        ]
        recs = recovery_engine.build_recommendations(triggers, [], sample_rate_card)
        assert len(recs) == 1
        assert recs[0].recommendation_type == RecoveryType.change_order

    def test_unknown_trigger_type_skipped(
        self, recovery_engine: RecoveryRecommendationEngine, sample_rate_card: list[RateCardEntry]
    ):
        triggers = [
            LeakageTrigger(
                trigger_type="unknown_trigger_xyz",
                description="Something unknown",
                severity="info",
            ),
        ]
        recs = recovery_engine.build_recommendations(triggers, [], sample_rate_card)
        assert len(recs) == 0

    def test_multiple_triggers_produce_multiple_recommendations(
        self, recovery_engine: RecoveryRecommendationEngine, sample_rate_card: list[RateCardEntry]
    ):
        triggers = [
            LeakageTrigger(
                trigger_type="unbilled_completed_work",
                description="t1",
                severity="error",
                estimated_impact_value=500.0,
            ),
            LeakageTrigger(
                trigger_type="rate_below_contract",
                description="t2",
                severity="warning",
                estimated_impact_value=100.0,
            ),
            LeakageTrigger(
                trigger_type="missing_daywork_sheet",
                description="t3",
                severity="error",
                estimated_impact_value=1200.0,
            ),
        ]
        recs = recovery_engine.build_recommendations(triggers, [], sample_rate_card)
        assert len(recs) == 3
        types = {r.recommendation_type for r in recs}
        assert RecoveryType.backbill in types
        assert RecoveryType.rate_adjustment in types


# ===================================================================
# PenaltyExposureAnalyzer
# ===================================================================


class TestPenaltyExposureAnalyzer:
    """Tests for PenaltyExposureAnalyzer."""

    @pytest.fixture
    def analyzer(self) -> PenaltyExposureAnalyzer:
        return PenaltyExposureAnalyzer()

    def test_breach_detected_exposure_calculated(self, analyzer: PenaltyExposureAnalyzer):
        conditions = [
            PenaltyCondition(
                clause_id="PC-001",
                description="SLA response time breach",
                trigger="response_time",
                penalty_amount="5%",
                penalty_type="percentage",
            ),
        ]
        sla = {"response_time": True, "days_since_breach": 10}
        result = analyzer.analyze(conditions, sla, monthly_invoice_value=100000.0)
        assert result.active_breaches == 1
        assert result.estimated_financial_exposure == 5000.0

    def test_within_grace_period_no_financial_exposure(self, analyzer: PenaltyExposureAnalyzer):
        conditions = [
            PenaltyCondition(
                clause_id="PC-002",
                description="Resolution SLA breach",
                trigger="resolution_time",
                penalty_amount="3%",
                penalty_type="percentage",
                grace_period_days=14,
            ),
        ]
        sla = {"resolution_time": True, "days_since_breach": 5}
        result = analyzer.analyze(conditions, sla, monthly_invoice_value=50000.0)
        assert result.active_breaches == 0
        assert result.estimated_financial_exposure == 0.0
        assert len(result.mitigation_actions) == 1
        assert "grace period" in result.mitigation_actions[0].lower()

    def test_cap_applied(self, analyzer: PenaltyExposureAnalyzer):
        conditions = [
            PenaltyCondition(
                clause_id="PC-003",
                description="Availability SLA breach",
                trigger="availability",
                penalty_amount="20%",
                penalty_type="percentage",
                cap=5000.0,
            ),
        ]
        sla = {"availability": True, "days_since_breach": 30}
        result = analyzer.analyze(conditions, sla, monthly_invoice_value=100000.0)
        assert result.active_breaches == 1
        # 20% of 100k = 20k but capped at 5k
        assert result.estimated_financial_exposure == 5000.0

    def test_no_breach_no_exposure(self, analyzer: PenaltyExposureAnalyzer):
        conditions = [
            PenaltyCondition(
                clause_id="PC-004",
                description="SLA not breached",
                trigger="response_time",
                penalty_amount="5%",
                penalty_type="percentage",
            ),
        ]
        sla = {"response_time": False}
        result = analyzer.analyze(conditions, sla, monthly_invoice_value=100000.0)
        assert result.active_breaches == 0
        assert result.estimated_financial_exposure == 0.0

    def test_fixed_penalty_type(self, analyzer: PenaltyExposureAnalyzer):
        conditions = [
            PenaltyCondition(
                clause_id="PC-005",
                description="Fixed penalty breach",
                trigger="uptime",
                penalty_amount="£2500",
                penalty_type="fixed",
            ),
        ]
        sla = {"uptime": True, "days_since_breach": 10}
        result = analyzer.analyze(conditions, sla, monthly_invoice_value=50000.0)
        assert result.active_breaches == 1
        assert result.estimated_financial_exposure == 2500.0

    def test_per_breach_penalty_type(self, analyzer: PenaltyExposureAnalyzer):
        conditions = [
            PenaltyCondition(
                clause_id="PC-006",
                description="Per-breach penalty",
                trigger="incidents",
                penalty_amount="£500",
                penalty_type="per_breach",
            ),
        ]
        sla = {"incidents": True, "days_since_breach": 10, "breach_count": 3}
        result = analyzer.analyze(conditions, sla, monthly_invoice_value=50000.0)
        assert result.active_breaches == 1
        assert result.estimated_financial_exposure == 1500.0
