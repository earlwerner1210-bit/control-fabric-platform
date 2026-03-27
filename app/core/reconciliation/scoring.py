"""Reconciliation scoring — quantifies mismatch severity."""

from __future__ import annotations

from app.core.reconciliation.types import (
    Mismatch,
    MismatchSeverity,
    ReconciliationScore,
)
from app.core.types import ConfidenceScore

SEVERITY_WEIGHTS: dict[MismatchSeverity, float] = {
    MismatchSeverity.CRITICAL: 1.0,
    MismatchSeverity.HIGH: 0.7,
    MismatchSeverity.MEDIUM: 0.4,
    MismatchSeverity.LOW: 0.2,
    MismatchSeverity.INFO: 0.0,
}


def score_mismatches(mismatches: list[Mismatch]) -> ReconciliationScore:
    """Score a set of mismatches into a ReconciliationScore."""
    if not mismatches:
        return ReconciliationScore(
            overall_score=1.0,
            confidence=ConfidenceScore(1.0),
            mismatch_count=0,
        )

    counts = {sev: 0 for sev in MismatchSeverity}
    financial_total = 0.0
    weighted_sum = 0.0

    for m in mismatches:
        counts[m.severity] += 1
        financial_total += m.financial_impact
        weighted_sum += SEVERITY_WEIGHTS.get(m.severity, 0.0)

    max_possible = len(mismatches) * 1.0
    penalty = min(weighted_sum / max(max_possible, 1.0), 1.0)
    overall = max(1.0 - penalty, 0.0)

    avg_confidence = sum(
        float(m.evidence[0].confidence) if m.evidence else 0.8 for m in mismatches
    ) / len(mismatches)

    return ReconciliationScore(
        overall_score=round(overall, 4),
        confidence=ConfidenceScore(round(avg_confidence, 4)),
        mismatch_count=len(mismatches),
        critical_count=counts[MismatchSeverity.CRITICAL],
        high_count=counts[MismatchSeverity.HIGH],
        medium_count=counts[MismatchSeverity.MEDIUM],
        low_count=counts[MismatchSeverity.LOW],
        info_count=counts[MismatchSeverity.INFO],
        financial_impact_total=round(financial_total, 2),
    )
