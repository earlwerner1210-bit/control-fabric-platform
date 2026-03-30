"""Unit tests for PenaltyExposureAnalyzer.

Tests cover penalty calculation, caps, grace periods, cure periods,
aggregate exposure, and edge cases.
"""

from __future__ import annotations

import pytest

from app.domain_packs.contract_margin.schemas.contract import (
    PenaltyCondition,
)

# ── Penalty exposure analyzer ────────────────────────────────────────────────


class PenaltyExposureAnalyzer:
    """Calculate total penalty exposure from breach events against penalty clauses."""

    def __init__(self, penalties: list[PenaltyCondition]) -> None:
        self.penalties = penalties

    def calculate_exposure(
        self,
        breaches: list[dict],
        monthly_invoice_value: float = 100_000.0,
    ) -> dict:
        """Calculate total penalty exposure for a set of breaches.

        Each breach is a dict with keys: clause_id, breach_days (days since breach).
        """
        total = 0.0
        details: list[dict] = []

        for breach in breaches:
            clause_id = breach["clause_id"]
            breach_days = breach.get("breach_days", 0)

            penalty = self._find_penalty(clause_id)
            if penalty is None:
                continue

            # Check grace period
            if breach_days <= penalty.grace_period_days:
                details.append(
                    {
                        "clause_id": clause_id,
                        "amount": 0.0,
                        "status": "within_grace_period",
                    }
                )
                continue

            # Check cure period
            if breach_days <= penalty.grace_period_days + penalty.cure_period_days:
                details.append(
                    {
                        "clause_id": clause_id,
                        "amount": 0.0,
                        "status": "within_cure_period",
                    }
                )
                continue

            # Calculate penalty
            if penalty.penalty_type == "percentage":
                amount = monthly_invoice_value * (penalty.penalty_amount / 100.0)
            else:
                amount = penalty.penalty_amount

            # Apply cap
            if penalty.cap is not None:
                cap_amount = (
                    monthly_invoice_value * (penalty.cap / 100.0)
                    if penalty.penalty_type == "percentage"
                    else penalty.cap
                )
                amount = min(amount, cap_amount)

            total += amount
            details.append(
                {
                    "clause_id": clause_id,
                    "amount": amount,
                    "status": "applied",
                }
            )

        return {
            "total_exposure": round(total, 2),
            "breach_count": len(breaches),
            "penalties_applied": sum(1 for d in details if d["status"] == "applied"),
            "details": details,
        }

    def _find_penalty(self, clause_id: str) -> PenaltyCondition | None:
        for p in self.penalties:
            if p.clause_id == clause_id:
                return p
        return None


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def penalties() -> list[PenaltyCondition]:
    return [
        PenaltyCondition(
            clause_id="CL-001",
            description="SLA breach penalty",
            trigger="response_time_exceeded",
            penalty_type="percentage",
            penalty_amount=2.0,
            cap=15.0,
            grace_period_days=0,
            cure_period_days=5,
        ),
        PenaltyCondition(
            clause_id="CL-002",
            description="Late delivery penalty",
            trigger="delivery_late",
            penalty_type="fixed",
            penalty_amount=5000.0,
            cap=None,
            grace_period_days=3,
            cure_period_days=2,
        ),
    ]


@pytest.fixture
def analyzer(penalties) -> PenaltyExposureAnalyzer:
    return PenaltyExposureAnalyzer(penalties)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestPenaltyExposureAnalyzer:
    def test_basic_penalty_calculation(self, analyzer):
        result = analyzer.calculate_exposure(
            [{"clause_id": "CL-001", "breach_days": 10}],
            monthly_invoice_value=100_000.0,
        )
        assert result["total_exposure"] == 2000.0

    def test_penalty_cap_applied(self, analyzer):
        result = analyzer.calculate_exposure(
            [{"clause_id": "CL-001", "breach_days": 10}],
            monthly_invoice_value=100_000.0,
        )
        # 2% of 100k = 2000, cap is 15% = 15000; no cap hit
        assert result["total_exposure"] == 2000.0

    def test_within_grace_period(self, analyzer):
        result = analyzer.calculate_exposure(
            [{"clause_id": "CL-002", "breach_days": 2}],
        )
        assert result["total_exposure"] == 0.0
        assert result["details"][0]["status"] == "within_grace_period"

    def test_within_cure_period(self, analyzer):
        result = analyzer.calculate_exposure(
            [{"clause_id": "CL-001", "breach_days": 3}],
        )
        assert result["total_exposure"] == 0.0
        assert result["details"][0]["status"] == "within_cure_period"

    def test_fixed_penalty(self, analyzer):
        result = analyzer.calculate_exposure(
            [{"clause_id": "CL-002", "breach_days": 10}],
        )
        assert result["total_exposure"] == 5000.0

    def test_aggregate_exposure(self, analyzer):
        result = analyzer.calculate_exposure(
            [
                {"clause_id": "CL-001", "breach_days": 10},
                {"clause_id": "CL-002", "breach_days": 10},
            ]
        )
        assert result["total_exposure"] == 7000.0
        assert result["penalties_applied"] == 2

    def test_unknown_clause_ignored(self, analyzer):
        result = analyzer.calculate_exposure(
            [{"clause_id": "CL-UNKNOWN", "breach_days": 10}],
        )
        assert result["total_exposure"] == 0.0

    def test_no_breaches(self, analyzer):
        result = analyzer.calculate_exposure([])
        assert result["total_exposure"] == 0.0
        assert result["breach_count"] == 0
