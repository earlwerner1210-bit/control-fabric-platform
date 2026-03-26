"""Tests for the feedback service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.feedback import (
    FeedbackCategory,
    FeedbackEntryCreate,
    FeedbackSeverity,
)
from app.services.feedback import FeedbackService


@pytest.fixture
def svc() -> FeedbackService:
    return FeedbackService()


CASE_ID = uuid.uuid4()
USER = uuid.uuid4()


class TestSubmitFeedback:
    def test_submit_feedback(self, svc: FeedbackService):
        result = svc.submit_feedback(
            CASE_ID,
            USER,
            FeedbackEntryCreate(
                category=FeedbackCategory.RULE_ACCURACY,
                severity=FeedbackSeverity.HIGH,
                title="Rate card rule mismatch",
                description="Rule R001 applies wrong multiplier for weekend rates",
                affected_component="rule_engine",
                suggested_improvement="Add weekend rate exception to rule R001",
            ),
        )
        assert result.category == FeedbackCategory.RULE_ACCURACY
        assert result.severity == FeedbackSeverity.HIGH
        assert result.affected_component == "rule_engine"
        assert result.pilot_case_id == CASE_ID
        assert result.submitted_by == USER

    def test_submit_with_tags(self, svc: FeedbackService):
        result = svc.submit_feedback(
            CASE_ID,
            USER,
            FeedbackEntryCreate(
                category=FeedbackCategory.EVIDENCE_GAP,
                title="Missing field completion",
                description="No field completion certificate in evidence chain",
                tags=["pilot_wave_1", "spen"],
            ),
        )
        assert "pilot_wave_1" in result.tags

    def test_submit_minimal(self, svc: FeedbackService):
        result = svc.submit_feedback(
            CASE_ID,
            USER,
            FeedbackEntryCreate(
                category=FeedbackCategory.OTHER,
                title="General note",
                description="Some feedback",
            ),
        )
        assert result.severity == FeedbackSeverity.MEDIUM


class TestGetCaseFeedback:
    def test_get_feedback(self, svc: FeedbackService):
        svc.submit_feedback(
            CASE_ID,
            USER,
            FeedbackEntryCreate(
                category=FeedbackCategory.FALSE_POSITIVE,
                title="FP",
                description="False positive found",
            ),
        )
        svc.submit_feedback(
            CASE_ID,
            USER,
            FeedbackEntryCreate(
                category=FeedbackCategory.MODEL_QUALITY,
                title="MQ",
                description="Model quality issue",
            ),
        )
        entries = svc.get_case_feedback(CASE_ID)
        assert len(entries) == 2

    def test_get_empty(self, svc: FeedbackService):
        assert svc.get_case_feedback(uuid.uuid4()) == []


class TestSummary:
    def test_empty_summary(self, svc: FeedbackService):
        summary = svc.get_summary()
        assert summary.total_entries == 0

    def test_summary_aggregation(self, svc: FeedbackService):
        svc.submit_feedback(
            CASE_ID,
            USER,
            FeedbackEntryCreate(
                category=FeedbackCategory.RULE_ACCURACY,
                severity=FeedbackSeverity.CRITICAL,
                title="Critical rule issue",
                description="Desc",
                affected_component="rule_engine",
            ),
        )
        svc.submit_feedback(
            CASE_ID,
            USER,
            FeedbackEntryCreate(
                category=FeedbackCategory.RULE_ACCURACY,
                severity=FeedbackSeverity.HIGH,
                title="High rule issue",
                description="Desc",
                affected_component="rule_engine",
            ),
        )
        svc.submit_feedback(
            uuid.uuid4(),
            USER,
            FeedbackEntryCreate(
                category=FeedbackCategory.EVIDENCE_GAP,
                severity=FeedbackSeverity.LOW,
                title="Minor gap",
                description="Desc",
                affected_component="evidence",
            ),
        )
        summary = svc.get_summary()
        assert summary.total_entries == 3
        assert summary.by_category["rule_accuracy"] == 2
        assert summary.by_category["evidence_gap"] == 1
        assert summary.by_component["rule_engine"] == 2
        assert summary.by_component["evidence"] == 1
        assert len(summary.top_issues) == 3
        # Critical should be first
        assert summary.top_issues[0].severity == FeedbackSeverity.CRITICAL
