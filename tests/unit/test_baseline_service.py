"""Tests for the baseline comparison service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.report import BaselineExpectation, BaselineMatchType
from app.services.baseline import BaselineComparisonService


@pytest.fixture
def svc() -> BaselineComparisonService:
    return BaselineComparisonService()


CASE_ID = uuid.uuid4()


class TestStoreExpectation:
    def test_store_expectation(self, svc: BaselineComparisonService):
        result = svc.store_expectation(
            CASE_ID,
            BaselineExpectation(
                expected_outcome="billable",
                expected_confidence=0.95,
                expected_reasoning="Standard rate card applies",
                source="human_expert",
            ),
        )
        assert result["expected_outcome"] == "billable"
        assert result["expected_confidence"] == 0.95
        assert result["source"] == "human_expert"

    def test_get_expectation(self, svc: BaselineComparisonService):
        svc.store_expectation(CASE_ID, BaselineExpectation(expected_outcome="billable"))
        exp = svc.get_expectation(CASE_ID)
        assert exp is not None
        assert exp["expected_outcome"] == "billable"

    def test_get_missing_expectation(self, svc: BaselineComparisonService):
        assert svc.get_expectation(uuid.uuid4()) is None


class TestCompare:
    def test_exact_match(self, svc: BaselineComparisonService):
        svc.store_expectation(CASE_ID, BaselineExpectation(expected_outcome="billable"))
        result = svc.compare(CASE_ID, platform_outcome="billable")
        assert result.match_type == BaselineMatchType.EXACT_MATCH

    def test_partial_match(self, svc: BaselineComparisonService):
        svc.store_expectation(CASE_ID, BaselineExpectation(expected_outcome="billable"))
        result = svc.compare(CASE_ID, platform_outcome="billable_with_conditions")
        assert result.match_type == BaselineMatchType.PARTIAL_MATCH

    def test_false_positive(self, svc: BaselineComparisonService):
        svc.store_expectation(CASE_ID, BaselineExpectation(expected_outcome="rejected"))
        result = svc.compare(CASE_ID, platform_outcome="approved")
        assert result.match_type == BaselineMatchType.FALSE_POSITIVE

    def test_false_negative(self, svc: BaselineComparisonService):
        svc.store_expectation(CASE_ID, BaselineExpectation(expected_outcome="approved"))
        result = svc.compare(CASE_ID, platform_outcome="rejected")
        assert result.match_type == BaselineMatchType.FALSE_NEGATIVE

    def test_false_negative_no_outcome(self, svc: BaselineComparisonService):
        svc.store_expectation(CASE_ID, BaselineExpectation(expected_outcome="billable"))
        result = svc.compare(CASE_ID)
        assert result.match_type == BaselineMatchType.FALSE_NEGATIVE

    def test_reviewer_outcome_takes_precedence(self, svc: BaselineComparisonService):
        svc.store_expectation(CASE_ID, BaselineExpectation(expected_outcome="billable"))
        result = svc.compare(CASE_ID, platform_outcome="not_billable", reviewer_outcome="billable")
        assert result.match_type == BaselineMatchType.EXACT_MATCH

    def test_compare_missing_expectation(self, svc: BaselineComparisonService):
        with pytest.raises(ValueError, match="No baseline expectation"):
            svc.compare(uuid.uuid4(), platform_outcome="billable")

    def test_useful_but_not_correct(self, svc: BaselineComparisonService):
        svc.store_expectation(CASE_ID, BaselineExpectation(expected_outcome="scope_a"))
        result = svc.compare(CASE_ID, platform_outcome="scope_b")
        assert result.match_type == BaselineMatchType.USEFUL_BUT_NOT_CORRECT


class TestGetComparison:
    def test_get_after_compare(self, svc: BaselineComparisonService):
        svc.store_expectation(CASE_ID, BaselineExpectation(expected_outcome="billable"))
        svc.compare(CASE_ID, platform_outcome="billable")
        comp = svc.get_comparison(CASE_ID)
        assert comp is not None
        assert comp.match_type == BaselineMatchType.EXACT_MATCH

    def test_get_missing(self, svc: BaselineComparisonService):
        assert svc.get_comparison(uuid.uuid4()) is None


class TestSummary:
    def test_empty_summary(self, svc: BaselineComparisonService):
        summary = svc.get_summary()
        assert summary.total_compared == 0
        assert summary.accuracy_rate == 0.0

    def test_summary_with_comparisons(self, svc: BaselineComparisonService):
        cases = [uuid.uuid4() for _ in range(4)]
        svc.store_expectation(cases[0], BaselineExpectation(expected_outcome="billable"))
        svc.store_expectation(cases[1], BaselineExpectation(expected_outcome="billable"))
        svc.store_expectation(cases[2], BaselineExpectation(expected_outcome="rejected"))
        svc.store_expectation(cases[3], BaselineExpectation(expected_outcome="scope_a"))

        svc.compare(cases[0], platform_outcome="billable")  # exact
        svc.compare(cases[1], platform_outcome="billable_partial")  # partial
        svc.compare(cases[2], platform_outcome="approved")  # false positive
        svc.compare(cases[3], platform_outcome="scope_b")  # useful not correct

        summary = svc.get_summary()
        assert summary.total_compared == 4
        assert summary.exact_matches == 1
        assert summary.partial_matches == 1
        assert summary.false_positives == 1
        assert summary.accuracy_rate == 0.5
