"""Unit tests for RecoveryRecommendationEngine.

Tests cover backbill recommendations, rate adjustments, evidence collection,
priority scoring, confidence, and empty input handling.
"""

from __future__ import annotations

import pytest

from app.domain_packs.contract_margin.schemas.contract import (
    CommercialRecoveryRecommendation,
    LeakageTrigger,
    PriorityLevel,
    RecoveryType,
)

# ── Recovery recommendation engine ───────────────────────────────────────────


class RecoveryRecommendationEngine:
    """Generate commercial recovery recommendations from leakage triggers."""

    TRIGGER_TO_RECOVERY: dict[str, RecoveryType] = {
        "unbilled_completed_work": RecoveryType.backbill,
        "rate_below_contract": RecoveryType.rate_adjustment,
        "scope_creep": RecoveryType.change_order,
        "missing_daywork_sheet": RecoveryType.evidence_collection,
        "time_rate_mismatch": RecoveryType.backbill,
        "material_passthrough": RecoveryType.backbill,
        "subcontractor_leak": RecoveryType.rate_adjustment,
        "mobilisation_not_charged": RecoveryType.backbill,
    }

    def recommend(
        self,
        triggers: list[LeakageTrigger],
    ) -> list[CommercialRecoveryRecommendation]:
        """Generate recovery recommendations for each leakage trigger."""
        recommendations: list[CommercialRecoveryRecommendation] = []

        for trigger in triggers:
            recovery_type = self.TRIGGER_TO_RECOVERY.get(
                trigger.trigger_type, RecoveryType.evidence_collection
            )
            confidence = self._compute_confidence(trigger)
            recommendations.append(
                CommercialRecoveryRecommendation(
                    recommendation_type=recovery_type,
                    description=f"Recovery action for: {trigger.description}",
                    estimated_recovery_value=trigger.estimated_impact_value,
                    evidence_clause_refs=trigger.clause_refs,
                    priority=trigger.severity,
                    confidence=confidence,
                )
            )

        return recommendations

    def _compute_confidence(self, trigger: LeakageTrigger) -> float:
        """Confidence based on severity and evidence availability."""
        base = 0.7
        if trigger.severity == PriorityLevel.critical:
            base = 0.95
        elif trigger.severity == PriorityLevel.high:
            base = 0.85
        elif trigger.severity == PriorityLevel.medium:
            base = 0.75
        if trigger.evidence:
            base = min(base + 0.05 * len(trigger.evidence), 1.0)
        return round(base, 2)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def engine() -> RecoveryRecommendationEngine:
    return RecoveryRecommendationEngine()


@pytest.fixture
def sample_triggers() -> list[LeakageTrigger]:
    return [
        LeakageTrigger(
            trigger_type="unbilled_completed_work",
            description="HV Switching not billed",
            severity=PriorityLevel.high,
            estimated_impact_value=450.0,
            clause_refs=["CL-001"],
            evidence=["daywork_sheet", "photo"],
        ),
        LeakageTrigger(
            trigger_type="rate_below_contract",
            description="Cable Jointing billed below rate",
            severity=PriorityLevel.high,
            estimated_impact_value=200.0,
        ),
        LeakageTrigger(
            trigger_type="missing_daywork_sheet",
            description="Missing daywork sheet for WO-123",
            severity=PriorityLevel.medium,
        ),
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRecoveryRecommendationEngine:
    def test_backbill_recommendation(self, engine, sample_triggers):
        recs = engine.recommend([sample_triggers[0]])
        assert len(recs) == 1
        assert recs[0].recommendation_type == RecoveryType.backbill

    def test_rate_adjustment_recommendation(self, engine, sample_triggers):
        recs = engine.recommend([sample_triggers[1]])
        assert recs[0].recommendation_type == RecoveryType.rate_adjustment

    def test_evidence_collection_recommendation(self, engine, sample_triggers):
        recs = engine.recommend([sample_triggers[2]])
        assert recs[0].recommendation_type == RecoveryType.evidence_collection

    def test_estimated_recovery_value(self, engine, sample_triggers):
        recs = engine.recommend([sample_triggers[0]])
        assert recs[0].estimated_recovery_value == 450.0

    def test_priority_preserved(self, engine, sample_triggers):
        recs = engine.recommend([sample_triggers[0]])
        assert recs[0].priority == PriorityLevel.high

    def test_confidence_with_evidence(self, engine, sample_triggers):
        recs = engine.recommend([sample_triggers[0]])
        assert recs[0].confidence > 0.85

    def test_confidence_without_evidence(self, engine, sample_triggers):
        recs = engine.recommend([sample_triggers[1]])
        assert recs[0].confidence == 0.85

    def test_empty_triggers(self, engine):
        recs = engine.recommend([])
        assert recs == []

    def test_unknown_trigger_type_defaults(self, engine):
        trigger = LeakageTrigger(
            trigger_type="totally_new_trigger",
            description="Something novel",
            severity=PriorityLevel.low,
        )
        recs = engine.recommend([trigger])
        assert recs[0].recommendation_type == RecoveryType.evidence_collection
