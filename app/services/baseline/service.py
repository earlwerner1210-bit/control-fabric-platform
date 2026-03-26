"""Baseline comparison engine — compares platform vs human decisions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.report import (
    BaselineComparisonResult,
    BaselineComparisonSummary,
    BaselineExpectation,
    BaselineMatchType,
)


class BaselineComparisonService:
    """Compares platform decision vs human/expected baseline."""

    def __init__(self) -> None:
        self._expectations: dict[uuid.UUID, dict[str, Any]] = {}
        self._comparisons: dict[uuid.UUID, dict[str, Any]] = {}

    def store_expectation(
        self,
        pilot_case_id: uuid.UUID,
        data: BaselineExpectation,
    ) -> dict[str, Any]:
        expectation = {
            "pilot_case_id": pilot_case_id,
            "expected_outcome": data.expected_outcome,
            "expected_confidence": data.expected_confidence,
            "expected_reasoning": data.expected_reasoning,
            "source": data.source,
            "metadata": data.metadata,
            "created_at": datetime.now(UTC),
        }
        self._expectations[pilot_case_id] = expectation
        return expectation

    def get_expectation(self, pilot_case_id: uuid.UUID) -> dict[str, Any] | None:
        return self._expectations.get(pilot_case_id)

    def compare(
        self,
        pilot_case_id: uuid.UUID,
        platform_outcome: str | None = None,
        reviewer_outcome: str | None = None,
    ) -> BaselineComparisonResult:
        expectation = self._expectations.get(pilot_case_id)
        if expectation is None:
            raise ValueError(f"No baseline expectation for case {pilot_case_id}")

        expected = expectation["expected_outcome"]
        match_type = self._determine_match_type(expected, platform_outcome, reviewer_outcome)

        confidence_delta = None
        if platform_outcome and expectation.get("expected_confidence") is not None:
            confidence_delta = 0.0

        comparison = {
            "id": uuid.uuid4(),
            "pilot_case_id": pilot_case_id,
            "expected_outcome": expected,
            "platform_outcome": platform_outcome,
            "reviewer_outcome": reviewer_outcome,
            "match_type": match_type,
            "confidence_delta": confidence_delta,
            "notes": None,
            "metadata": expectation.get("metadata", {}),
            "created_at": datetime.now(UTC),
        }
        self._comparisons[pilot_case_id] = comparison
        return BaselineComparisonResult(**comparison)

    def get_comparison(self, pilot_case_id: uuid.UUID) -> BaselineComparisonResult | None:
        comp = self._comparisons.get(pilot_case_id)
        if comp is None:
            return None
        return BaselineComparisonResult(**comp)

    def get_summary(self) -> BaselineComparisonSummary:
        comparisons = list(self._comparisons.values())
        total = len(comparisons)
        if total == 0:
            return BaselineComparisonSummary(
                total_compared=0,
                exact_matches=0,
                partial_matches=0,
                false_positives=0,
                false_negatives=0,
                useful_not_correct=0,
                correct_low_confidence=0,
                accuracy_rate=0.0,
            )

        counts: dict[str, int] = {}
        for c in comparisons:
            mt = c["match_type"]
            key = mt.value if isinstance(mt, BaselineMatchType) else mt
            counts[key] = counts.get(key, 0) + 1

        exact = counts.get("exact_match", 0)
        partial = counts.get("partial_match", 0)
        accuracy = (exact + partial) / total if total > 0 else 0.0

        return BaselineComparisonSummary(
            total_compared=total,
            exact_matches=exact,
            partial_matches=partial,
            false_positives=counts.get("false_positive", 0),
            false_negatives=counts.get("false_negative", 0),
            useful_not_correct=counts.get("useful_but_not_correct", 0),
            correct_low_confidence=counts.get("correct_but_low_confidence", 0),
            accuracy_rate=accuracy,
        )

    def _determine_match_type(
        self,
        expected: str,
        platform_outcome: str | None,
        reviewer_outcome: str | None,
    ) -> BaselineMatchType:
        final = reviewer_outcome or platform_outcome
        if final is None:
            return BaselineMatchType.FALSE_NEGATIVE

        expected_lower = expected.lower().strip()
        final_lower = final.lower().strip()

        if expected_lower == final_lower:
            return BaselineMatchType.EXACT_MATCH

        if expected_lower in final_lower or final_lower in expected_lower:
            return BaselineMatchType.PARTIAL_MATCH

        # Check for positive/negative mismatches
        positive_signals = {"billable", "approved", "ready", "compliant", "pass", "escalate"}
        negative_signals = {"not_billable", "rejected", "blocked", "non_compliant", "fail", "no_escalation"}

        expected_positive = any(s in expected_lower for s in positive_signals)
        final_positive = any(s in final_lower for s in positive_signals)
        expected_negative = any(s in expected_lower for s in negative_signals)
        final_negative = any(s in final_lower for s in negative_signals)

        if expected_negative and final_positive:
            return BaselineMatchType.FALSE_POSITIVE
        if expected_positive and final_negative:
            return BaselineMatchType.FALSE_NEGATIVE

        return BaselineMatchType.USEFUL_BUT_NOT_CORRECT
