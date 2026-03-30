"""Tests for contract-margin validation rules."""

from __future__ import annotations

import pytest

from app.domain_packs.contract_margin.rules import (
    BillabilityRuleEngine,
    LeakageRuleEngine,
    PenaltyRuleEngine,
)
from app.domain_packs.contract_margin.schemas import (
    BillabilityDecision,
    RateCardEntry,
)


@pytest.fixture
def billability_engine() -> BillabilityRuleEngine:
    return BillabilityRuleEngine()


@pytest.fixture
def leakage_engine() -> LeakageRuleEngine:
    return LeakageRuleEngine()


@pytest.fixture
def penalty_engine() -> PenaltyRuleEngine:
    return PenaltyRuleEngine()


@pytest.fixture
def sample_rate_card() -> list[RateCardEntry]:
    return [
        RateCardEntry(activity="standard_maintenance", rate=125.0, unit="hour"),
        RateCardEntry(activity="emergency_repair", rate=187.50, unit="hour"),
        RateCardEntry(activity="equipment_installation", rate=350.0, unit="unit"),
    ]


@pytest.fixture
def sample_obligations() -> list[dict]:
    return [
        {"text": "Provider shall deliver all scheduled maintenance", "section": "2.1"},
        {"text": "Network maintenance and equipment installation services", "section": "2.2"},
    ]


class TestContractValidators:
    """Tests for contract margin validation rules."""

    def test_valid_billability_passes(
        self,
        billability_engine: BillabilityRuleEngine,
        sample_rate_card: list[RateCardEntry],
        sample_obligations: list[dict],
    ):
        """A valid activity with matching rate and scope should pass billability."""
        result = billability_engine.evaluate(
            activity="standard_maintenance",
            rate_card=sample_rate_card,
            obligations=sample_obligations,
        )

        assert isinstance(result, BillabilityDecision)
        assert result.billable is True
        assert result.confidence > 0.5
        assert result.rate_applied == 125.0
        assert len(result.reasons) == 0

    def test_billable_without_evidence_fails(
        self,
        billability_engine: BillabilityRuleEngine,
    ):
        """Activity with no matching rate card should not be billable."""
        result = billability_engine.evaluate(
            activity="custom_development",
            rate_card=[],  # no rate card
            obligations=[],
        )

        assert result.billable is False
        assert result.confidence < 1.0
        assert result.rate_applied is None
        assert len(result.reasons) > 0

    def test_margin_diagnosis_verdict_mismatch(
        self,
        billability_engine: BillabilityRuleEngine,
        sample_rate_card: list[RateCardEntry],
    ):
        """An excluded activity should produce a non-billable verdict."""
        result = billability_engine.evaluate(
            activity="internal_meeting",
            rate_card=sample_rate_card,
            obligations=[{"text": "All activities require documentation"}],
        )

        assert result.billable is False
        # Should have a reason about exclusion
        assert any("exclusion" in r.lower() or "excluded" in r.lower() for r in result.reasons)

    def test_recovery_without_evidence_fails(
        self,
        leakage_engine: LeakageRuleEngine,
    ):
        """Leakage engine with no work history should produce no triggers."""
        triggers = leakage_engine.evaluate(
            contract_objects=[],
            work_history=None,
        )

        assert isinstance(triggers, list)
        assert len(triggers) == 0

    def test_conflicting_penalties_detected(
        self,
        penalty_engine: PenaltyRuleEngine,
    ):
        """SLA breach in penalty objects should be detected."""
        penalty_objects = [
            {
                "label": "SLA Breach Penalty",
                "payload": {
                    "text": "Failure to meet SLA response times will incur penalties",
                    "breach_detected": True,
                },
            },
        ]
        sla_performance = {"sla_met": False, "breaches": 3}

        results = penalty_engine.evaluate(
            penalty_objects=penalty_objects,
            sla_performance=sla_performance,
        )

        assert len(results) >= 1
        # At least one rule should detect the SLA breach
        failed_rules = [r for r in results if not r.passed]
        assert len(failed_rules) >= 1
        assert any(
            "sla" in r.message.lower() or "breach" in r.message.lower() for r in failed_rules
        )


class TestLeakageDetection:
    """Tests for leakage rule engine."""

    def test_unbilled_work_detected(self, leakage_engine: LeakageRuleEngine):
        """Completed but unbilled work should trigger leakage."""
        triggers = leakage_engine.evaluate(
            contract_objects=[],
            work_history=[
                {
                    "activity": "emergency_repair",
                    "status": "completed",
                    "billed": False,
                    "estimated_value": 750,
                },
            ],
        )

        assert len(triggers) >= 1
        assert any(t.trigger_type == "unbilled_completed_work" for t in triggers)

    def test_rate_erosion_detected(self, leakage_engine: LeakageRuleEngine):
        """Billed rate below contract rate should trigger leakage."""
        triggers = leakage_engine.evaluate(
            contract_objects=[],
            work_history=[
                {"activity": "maintenance", "billed_rate": 100.0, "contract_rate": 125.0},
            ],
        )

        assert len(triggers) >= 1
        assert any(t.trigger_type == "rate_below_contract" for t in triggers)

    def test_scope_creep_detected(self, leakage_engine: LeakageRuleEngine):
        """Out-of-scope work without change order should be detected."""
        triggers = leakage_engine.evaluate(
            contract_objects=[],
            work_history=[
                {"activity": "custom_work", "change_order_required": True, "change_order_id": None},
            ],
        )

        assert len(triggers) >= 1
        assert any(t.trigger_type == "scope_creep_detected" for t in triggers)

    def test_penalty_exposure_detected(self, leakage_engine: LeakageRuleEngine):
        """Breach of penalty condition should be detected."""
        triggers = leakage_engine.evaluate(
            contract_objects=[
                {
                    "control_type": "penalty_condition",
                    "label": "SLA penalty",
                    "payload": {"breach_detected": True},
                },
            ],
        )

        assert len(triggers) >= 1
        assert any(t.trigger_type == "penalty_exposure_unmitigated" for t in triggers)
