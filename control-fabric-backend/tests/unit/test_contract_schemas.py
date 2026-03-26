"""Unit tests for contract margin domain pack Pydantic schemas.

Tests cover validators, methods, enums, and derived models in
app/domain_packs/contract_margin/schemas/contract.py.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.domain_packs.contract_margin.schemas.contract import (
    BillableCategory,
    BillableEvent,
    BillabilityDecision,
    ClauseSegment,
    ClauseType,
    CommercialEvidenceBundle,
    CommercialRecoveryRecommendation,
    ContractCompileSummary,
    ContractType,
    ExtractedClause,
    LeakageTrigger,
    MarginDiagnosisResult,
    Obligation,
    ParsedContract,
    PenaltyCondition,
    PriorityLevel,
    RateCardEntry,
    RecoveryType,
    ScopeBoundary,
    ScopeType,
    SLAEntry,
)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_clause_type_values(self):
        assert ClauseType.obligation.value == "obligation"
        assert ClauseType.sla.value == "sla"
        assert ClauseType.penalty.value == "penalty"
        assert ClauseType.re_attendance.value == "re_attendance"

    def test_contract_type_values(self):
        assert ContractType.master_services.value == "master_services"
        assert ContractType.change_order.value == "change_order"

    def test_scope_type_values(self):
        assert ScopeType.in_scope.value == "in_scope"
        assert ScopeType.out_of_scope.value == "out_of_scope"
        assert ScopeType.conditional.value == "conditional"

    def test_billable_category_values(self):
        assert BillableCategory.standard.value == "standard"
        assert BillableCategory.emergency.value == "emergency"
        assert BillableCategory.mobilisation.value == "mobilisation"

    def test_recovery_type_values(self):
        assert RecoveryType.backbill.value == "backbill"
        assert RecoveryType.dispute.value == "dispute"

    def test_priority_level_values(self):
        assert PriorityLevel.critical.value == "critical"
        assert PriorityLevel.low.value == "low"


# ---------------------------------------------------------------------------
# ClauseSegment tests
# ---------------------------------------------------------------------------


class TestClauseSegment:
    def test_valid_segment(self):
        seg = ClauseSegment(
            clause_id="CL-001",
            text="Some clause text",
            start_offset=0,
            end_offset=16,
        )
        assert seg.clause_id == "CL-001"
        assert seg.end_offset == 16

    def test_end_before_start_raises(self):
        with pytest.raises(ValidationError, match="end_offset must be >= start_offset"):
            ClauseSegment(
                clause_id="CL-001",
                text="Some text",
                start_offset=10,
                end_offset=5,
            )

    def test_equal_start_end(self):
        seg = ClauseSegment(
            clause_id="CL-001",
            text="X",
            start_offset=5,
            end_offset=5,
        )
        assert seg.start_offset == seg.end_offset

    def test_default_confidence(self):
        seg = ClauseSegment(
            clause_id="CL-001", text="text", start_offset=0, end_offset=4
        )
        assert seg.confidence == 1.0

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            ClauseSegment(
                clause_id="CL-001",
                text="text",
                start_offset=0,
                end_offset=4,
                confidence=1.5,
            )


# ---------------------------------------------------------------------------
# SLAEntry tests
# ---------------------------------------------------------------------------


class TestSLAEntry:
    def test_valid_entry(self):
        entry = SLAEntry(
            priority=PriorityLevel.critical,
            response_time_hours=2,
            resolution_time_hours=4,
        )
        assert entry.measurement_window == "monthly"

    def test_measurement_window_valid_values(self):
        for w in ("monthly", "quarterly", "annual", "weekly"):
            e = SLAEntry(
                priority=PriorityLevel.high,
                response_time_hours=4,
                resolution_time_hours=8,
                measurement_window=w,
            )
            assert e.measurement_window == w

    def test_measurement_window_case_insensitive(self):
        e = SLAEntry(
            priority=PriorityLevel.high,
            response_time_hours=4,
            resolution_time_hours=8,
            measurement_window="QUARTERLY",
        )
        assert e.measurement_window == "quarterly"

    def test_invalid_measurement_window(self):
        with pytest.raises(ValidationError, match="measurement_window must be one of"):
            SLAEntry(
                priority=PriorityLevel.high,
                response_time_hours=4,
                resolution_time_hours=8,
                measurement_window="biweekly",
            )


# ---------------------------------------------------------------------------
# RateCardEntry tests
# ---------------------------------------------------------------------------


class TestRateCardEntry:
    def test_currency_validation_valid(self):
        entry = RateCardEntry(activity="Test", rate=100.0, currency="usd")
        assert entry.currency == "USD"

    def test_currency_validation_invalid_length(self):
        with pytest.raises(ValidationError, match="3-letter ISO 4217"):
            RateCardEntry(activity="Test", rate=100.0, currency="EURO")

    def test_currency_validation_invalid_chars(self):
        with pytest.raises(ValidationError, match="3-letter ISO 4217"):
            RateCardEntry(activity="Test", rate=100.0, currency="12E")

    def test_is_active_within_range(self):
        entry = RateCardEntry(
            activity="Test",
            rate=100.0,
            effective_from=date(2024, 1, 1),
            effective_to=date(2026, 12, 31),
        )
        assert entry.is_active(date(2025, 6, 15)) is True

    def test_is_active_before_start(self):
        entry = RateCardEntry(
            activity="Test",
            rate=100.0,
            effective_from=date(2024, 1, 1),
            effective_to=date(2026, 12, 31),
        )
        assert entry.is_active(date(2023, 12, 31)) is False

    def test_is_active_after_end(self):
        entry = RateCardEntry(
            activity="Test",
            rate=100.0,
            effective_from=date(2024, 1, 1),
            effective_to=date(2026, 12, 31),
        )
        assert entry.is_active(date(2027, 1, 1)) is False

    def test_is_active_no_dates(self):
        entry = RateCardEntry(activity="Test", rate=100.0)
        assert entry.is_active(date(2030, 1, 1)) is True

    def test_effective_rate_standard(self):
        entry = RateCardEntry(
            activity="Test",
            rate=100.0,
            multipliers={"overtime": 1.5, "weekend": 2.0},
        )
        assert entry.effective_rate("standard") == 100.0

    def test_effective_rate_overtime(self):
        entry = RateCardEntry(
            activity="Test",
            rate=100.0,
            multipliers={"overtime": 1.5},
        )
        assert entry.effective_rate("overtime") == 150.0

    def test_effective_rate_unknown_category(self):
        entry = RateCardEntry(activity="Test", rate=200.0, multipliers={"x": 3.0})
        assert entry.effective_rate("unknown") == 200.0


# ---------------------------------------------------------------------------
# ParsedContract.is_active tests
# ---------------------------------------------------------------------------


class TestParsedContractIsActive:
    def test_active_within_dates(self):
        pc = ParsedContract(
            effective_date=date(2024, 1, 1), expiry_date=date(2026, 12, 31)
        )
        assert pc.is_active(date(2025, 6, 1)) is True

    def test_inactive_before_effective(self):
        pc = ParsedContract(
            effective_date=date(2024, 1, 1), expiry_date=date(2026, 12, 31)
        )
        assert pc.is_active(date(2023, 6, 1)) is False

    def test_inactive_after_expiry(self):
        pc = ParsedContract(
            effective_date=date(2024, 1, 1), expiry_date=date(2026, 12, 31)
        )
        assert pc.is_active(date(2027, 6, 1)) is False

    def test_active_no_dates(self):
        pc = ParsedContract()
        assert pc.is_active(date(2099, 1, 1)) is True


# ---------------------------------------------------------------------------
# ContractCompileSummary.from_parsed_contract tests
# ---------------------------------------------------------------------------


class TestContractCompileSummary:
    def test_from_parsed_contract_counts(self):
        pc = ParsedContract(
            title="Test Contract",
            parties=["A", "B"],
            effective_date=date(2024, 1, 1),
            expiry_date=date(2026, 12, 31),
            clauses=[
                ExtractedClause(type=ClauseType.obligation, text="clause1"),
                ExtractedClause(
                    type=ClauseType.penalty,
                    text="clause2",
                    risk_level=PriorityLevel.high,
                ),
            ],
            obligations=[
                Obligation(clause_id="CL-1", description="do something"),
            ],
            penalties=[
                PenaltyCondition(
                    clause_id="CL-2", description="penalty", trigger="breach"
                ),
            ],
            billable_events=[
                BillableEvent(activity="X", rate=100.0),
            ],
            sla_table=[
                SLAEntry(
                    priority=PriorityLevel.high,
                    response_time_hours=4,
                    resolution_time_hours=8,
                ),
            ],
            scope_boundaries=[
                ScopeBoundary(scope_type=ScopeType.in_scope),
            ],
        )
        summary = ContractCompileSummary.from_parsed_contract(pc)
        assert summary.contract_title == "Test Contract"
        assert summary.clause_count == 2
        assert summary.obligation_count == 1
        assert summary.penalty_count == 1
        assert summary.billable_event_count == 1
        assert summary.sla_entry_count == 1
        assert summary.scope_boundary_count == 1
        assert summary.risk_summary == {"medium": 1, "high": 1}

    def test_from_parsed_contract_empty(self):
        pc = ParsedContract()
        summary = ContractCompileSummary.from_parsed_contract(pc)
        assert summary.clause_count == 0
        assert summary.risk_summary == {}


# ---------------------------------------------------------------------------
# CommercialEvidenceBundle.completeness_score tests
# ---------------------------------------------------------------------------


class TestCommercialEvidenceBundle:
    def test_completeness_full(self):
        bundle = CommercialEvidenceBundle(
            contract_evidence=["a", "b"],
            work_order_evidence=["c"],
            execution_evidence=["d"],
            billing_evidence=["e"],
            gaps=[],
        )
        assert bundle.completeness_score() == 1.0

    def test_completeness_with_gaps(self):
        bundle = CommercialEvidenceBundle(
            contract_evidence=["a"],
            work_order_evidence=[],
            execution_evidence=[],
            billing_evidence=[],
            gaps=["missing_x", "missing_y", "missing_z"],
        )
        # 1 / (1 + 3) = 0.25
        assert bundle.completeness_score() == 0.25

    def test_completeness_empty(self):
        bundle = CommercialEvidenceBundle()
        assert bundle.completeness_score() == 0.0

    def test_completeness_half(self):
        bundle = CommercialEvidenceBundle(
            contract_evidence=["a"],
            gaps=["b"],
        )
        # 1 / (1 + 1) = 0.5
        assert bundle.completeness_score() == 0.5


# ---------------------------------------------------------------------------
# MarginDiagnosisResult verdict validator tests
# ---------------------------------------------------------------------------


class TestMarginDiagnosisResult:
    def _make_billability(self) -> BillabilityDecision:
        return BillabilityDecision(billable=True, rate_applied=100.0)

    def test_valid_verdicts(self):
        for v in ("billable", "non_billable", "partial", "review"):
            result = MarginDiagnosisResult(
                verdict=v, billability=self._make_billability()
            )
            assert result.verdict == v

    def test_invalid_verdict(self):
        with pytest.raises(ValidationError, match="verdict must be one of"):
            MarginDiagnosisResult(
                verdict="unknown", billability=self._make_billability()
            )

    def test_default_confidence(self):
        result = MarginDiagnosisResult(
            verdict="billable", billability=self._make_billability()
        )
        assert result.confidence == 0.85
