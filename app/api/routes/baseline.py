"""API routes for baseline comparison."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.baseline import (
    BaselineComparisonRequest,
    BaselineComparisonResult,
    BaselineComparisonSummary,
    BaselineExpectationCreate,
    BaselineExpectationResponse,
    BaselineMatchType,
)

router = APIRouter(prefix="/api/v1", tags=["baseline"])

# In-memory service instance for now
_baseline_expectations: dict[uuid.UUID, dict] = {}
_baseline_comparisons: dict[uuid.UUID, dict] = {}


@router.post(
    "/pilot-cases/{pilot_case_id}/baseline",
    response_model=BaselineExpectationResponse,
)
async def create_baseline_expectation(
    pilot_case_id: uuid.UUID,
    data: BaselineExpectationCreate,
) -> BaselineExpectationResponse:
    from datetime import UTC, datetime

    record = {
        "id": uuid.uuid4(),
        "pilot_case_id": pilot_case_id,
        "expected_outcome": data.expected_outcome,
        "expected_confidence": data.expected_confidence,
        "expected_reasoning": data.expected_reasoning,
        "expected_status": data.expected_status,
        "expected_billability": data.expected_billability,
        "expected_next_action": data.expected_next_action,
        "expected_owner": data.expected_owner,
        "expected_escalation": data.expected_escalation,
        "expected_recovery_action": data.expected_recovery_action,
        "expected_evidence_refs": data.expected_evidence_refs,
        "source": data.source,
        "metadata": data.metadata,
        "created_at": datetime.now(UTC),
    }
    _baseline_expectations[pilot_case_id] = record
    return BaselineExpectationResponse(**record)


@router.get(
    "/pilot-cases/{pilot_case_id}/baseline",
    response_model=BaselineExpectationResponse,
)
async def get_baseline_expectation(
    pilot_case_id: uuid.UUID,
) -> BaselineExpectationResponse:
    record = _baseline_expectations.get(pilot_case_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Baseline expectation not found")
    return BaselineExpectationResponse(**record)


@router.post(
    "/pilot-cases/{pilot_case_id}/baseline/compare",
    response_model=BaselineComparisonResult,
)
async def compare_baseline(
    pilot_case_id: uuid.UUID,
    data: BaselineComparisonRequest,
) -> BaselineComparisonResult:
    from datetime import UTC, datetime

    expectation = _baseline_expectations.get(pilot_case_id)
    if expectation is None:
        raise HTTPException(status_code=404, detail="Baseline expectation not found")

    expected = expectation["expected_outcome"]
    final = data.reviewer_outcome or data.platform_outcome

    if final is None:
        match_type = BaselineMatchType.FALSE_NEGATIVE
    elif expected.lower().strip() == final.lower().strip():
        match_type = BaselineMatchType.EXACT_MATCH
    elif expected.lower() in final.lower() or final.lower() in expected.lower():
        match_type = BaselineMatchType.PARTIAL_MATCH
    else:
        positive_signals = {"billable", "approved", "ready", "compliant", "pass"}
        negative_signals = {"not_billable", "rejected", "blocked", "non_compliant", "fail"}

        expected_lower = expected.lower()
        final_lower = final.lower()
        expected_neg = any(s in expected_lower for s in negative_signals)
        final_pos = any(s in final_lower for s in positive_signals)
        expected_pos = any(s in expected_lower for s in positive_signals)
        final_neg = any(s in final_lower for s in negative_signals)

        if expected_neg and final_pos:
            match_type = BaselineMatchType.FALSE_POSITIVE
        elif expected_pos and final_neg:
            match_type = BaselineMatchType.FALSE_NEGATIVE
        else:
            match_type = BaselineMatchType.USEFUL_BUT_NOT_CORRECT

    confidence_delta = None
    if data.platform_confidence is not None and expectation.get("expected_confidence") is not None:
        confidence_delta = data.platform_confidence - expectation["expected_confidence"]

    comparison = {
        "id": uuid.uuid4(),
        "pilot_case_id": pilot_case_id,
        "expected_outcome": expected,
        "platform_outcome": data.platform_outcome,
        "platform_status": data.platform_status,
        "reviewer_outcome": data.reviewer_outcome,
        "reviewer_status": data.reviewer_status,
        "match_type": match_type,
        "confidence_delta": confidence_delta,
        "mismatch_reasons": data.mismatch_reasons,
        "notes": None,
        "metadata": data.metadata,
        "created_at": datetime.now(UTC),
    }
    _baseline_comparisons[pilot_case_id] = comparison
    return BaselineComparisonResult(**comparison)


@router.get(
    "/pilot-reports/baseline-comparison",
    response_model=BaselineComparisonSummary,
)
async def get_baseline_comparison_summary() -> BaselineComparisonSummary:
    comparisons = list(_baseline_comparisons.values())
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
    fp = counts.get("false_positive", 0)
    fn = counts.get("false_negative", 0)

    return BaselineComparisonSummary(
        total_compared=total,
        exact_matches=exact,
        partial_matches=partial,
        false_positives=fp,
        false_negatives=fn,
        useful_not_correct=counts.get("useful_but_not_correct", 0),
        correct_low_confidence=counts.get("correct_but_low_confidence", 0),
        accuracy_rate=(exact + partial) / total if total > 0 else 0.0,
        false_positive_rate=fp / total if total > 0 else 0.0,
        false_negative_rate=fn / total if total > 0 else 0.0,
    )
