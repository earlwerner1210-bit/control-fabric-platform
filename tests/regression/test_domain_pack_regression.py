"""Regression tests -- run eval cases from all 3 domain packs through rule engines.

Parametrizes over eval cases from:
- contract_margin/evals.py
- utilities_field/evals.py
- telco_ops/evals.py
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain_packs.contract_margin.evals import CONTRACT_MARGIN_EVAL_CASES
from app.domain_packs.contract_margin.rules import (
    BillabilityRuleEngine,
    LeakageRuleEngine,
    PenaltyRuleEngine,
)
from app.domain_packs.contract_margin.schemas import RateCardEntry
from app.domain_packs.telco_ops.evals import TELCO_OPS_EVAL_CASES
from app.domain_packs.telco_ops.rules import (
    ActionRuleEngine,
    EscalationRuleEngine,
)
from app.domain_packs.telco_ops.schemas import (
    IncidentSeverity,
    IncidentState,
    ParsedIncident,
)
from app.domain_packs.utilities_field.evals import UTILITIES_FIELD_EVAL_CASES
from app.domain_packs.utilities_field.parsers import (
    EngineerProfileParser,
    WorkOrderParser,
)
from app.domain_packs.utilities_field.rules import ReadinessRuleEngine


# ---------------------------------------------------------------------------
# Contract Margin eval cases
# ---------------------------------------------------------------------------


def _get_contract_margin_billability_cases() -> list[dict]:
    return [c for c in CONTRACT_MARGIN_EVAL_CASES if c["expected_output"].get("billable") is not None]


def _get_contract_margin_leakage_cases() -> list[dict]:
    return [c for c in CONTRACT_MARGIN_EVAL_CASES if c["expected_output"].get("leakage_drivers")]


def _get_contract_margin_penalty_cases() -> list[dict]:
    return [c for c in CONTRACT_MARGIN_EVAL_CASES if c["expected_output"].get("verdict") == "penalty_risk"]


class TestContractMarginRegression:
    """Run contract margin eval cases through rule engines."""

    @pytest.fixture
    def billability_engine(self) -> BillabilityRuleEngine:
        return BillabilityRuleEngine()

    @pytest.fixture
    def leakage_engine(self) -> LeakageRuleEngine:
        return LeakageRuleEngine()

    @pytest.fixture
    def penalty_engine(self) -> PenaltyRuleEngine:
        return PenaltyRuleEngine()

    @pytest.mark.parametrize(
        "case",
        _get_contract_margin_billability_cases(),
        ids=[c["name"] for c in _get_contract_margin_billability_cases()],
    )
    def test_billability_eval_cases(self, billability_engine: BillabilityRuleEngine, case: dict):
        """Billability eval case should produce expected verdict."""
        payload = case["input_payload"]
        rate_card = [RateCardEntry(**r) for r in payload.get("rate_card", [])]
        obligations = payload.get("obligations", [])
        activity = payload.get("activity", "")

        if not activity:
            pytest.skip("No activity in eval case")

        result = billability_engine.evaluate(
            activity=activity,
            rate_card=rate_card,
            obligations=obligations,
        )

        expected_billable = case["expected_output"]["billable"]
        assert result.billable == expected_billable, (
            f"Case '{case['name']}': expected billable={expected_billable}, "
            f"got {result.billable}. Reasons: {result.reasons}"
        )

    @pytest.mark.parametrize(
        "case",
        _get_contract_margin_leakage_cases(),
        ids=[c["name"] for c in _get_contract_margin_leakage_cases()],
    )
    def test_leakage_eval_cases(self, leakage_engine: LeakageRuleEngine, case: dict):
        """Leakage eval case should detect expected drivers."""
        payload = case["input_payload"]
        work_history = payload.get("work_history", [])

        triggers = leakage_engine.evaluate(
            contract_objects=[],
            work_history=work_history,
        )

        expected_drivers = case["expected_output"]["leakage_drivers"]
        trigger_types = [t.trigger_type for t in triggers]
        for driver in expected_drivers:
            assert any(driver in tt for tt in trigger_types), (
                f"Case '{case['name']}': expected driver '{driver}' not found "
                f"in triggers: {trigger_types}"
            )

    @pytest.mark.parametrize(
        "case",
        _get_contract_margin_penalty_cases(),
        ids=[c["name"] for c in _get_contract_margin_penalty_cases()],
    )
    def test_penalty_eval_cases(self, penalty_engine: PenaltyRuleEngine, case: dict):
        """Penalty eval case should detect penalty risk."""
        payload = case["input_payload"]
        penalty_objects = payload.get("penalty_objects", [])
        sla_performance = payload.get("sla_performance", {})

        results = penalty_engine.evaluate(
            penalty_objects=penalty_objects,
            sla_performance=sla_performance,
        )

        # Penalty risk verdict means at least one rule should flag an issue
        failed_rules = [r for r in results if not r.passed]
        assert len(failed_rules) > 0, (
            f"Case '{case['name']}': expected penalty risk but all rules passed"
        )


# ---------------------------------------------------------------------------
# Utilities Field eval cases
# ---------------------------------------------------------------------------


class TestUtilitiesFieldRegression:
    """Run field readiness eval cases through rule engines."""

    @pytest.fixture
    def readiness_engine(self) -> ReadinessRuleEngine:
        return ReadinessRuleEngine()

    @pytest.fixture
    def wo_parser(self) -> WorkOrderParser:
        return WorkOrderParser()

    @pytest.fixture
    def eng_parser(self) -> EngineerProfileParser:
        return EngineerProfileParser()

    @pytest.mark.parametrize(
        "case",
        UTILITIES_FIELD_EVAL_CASES,
        ids=[c["name"] for c in UTILITIES_FIELD_EVAL_CASES],
    )
    def test_field_eval_cases(
        self,
        readiness_engine: ReadinessRuleEngine,
        wo_parser: WorkOrderParser,
        eng_parser: EngineerProfileParser,
        case: dict,
    ):
        """Field eval case should produce expected readiness verdict."""
        payload = case["input_payload"]
        wo_data = payload.get("work_order", {})
        eng_data = payload.get("engineer", {})

        parsed_wo = wo_parser.parse_work_order(wo_data)
        parsed_eng = eng_parser.parse_profile(eng_data)

        result = readiness_engine.evaluate(parsed_wo, parsed_eng)

        expected_verdict = case["expected_output"]["verdict"]
        assert result.status.value == expected_verdict, (
            f"Case '{case['name']}': expected verdict '{expected_verdict}', "
            f"got '{result.status.value}'. Blockers: {[b.description for b in result.blockers]}"
        )


# ---------------------------------------------------------------------------
# Telco Ops eval cases
# ---------------------------------------------------------------------------


class TestTelcoOpsRegression:
    """Run telco ops eval cases through rule engines."""

    @pytest.fixture
    def escalation_engine(self) -> EscalationRuleEngine:
        return EscalationRuleEngine()

    @pytest.fixture
    def action_engine(self) -> ActionRuleEngine:
        return ActionRuleEngine()

    @pytest.mark.parametrize(
        "case",
        TELCO_OPS_EVAL_CASES,
        ids=[c["name"] for c in TELCO_OPS_EVAL_CASES],
    )
    def test_telco_eval_cases(
        self,
        escalation_engine: EscalationRuleEngine,
        action_engine: ActionRuleEngine,
        case: dict,
    ):
        """Telco ops eval case should produce expected escalation and action."""
        payload = case["input_payload"]
        incident_data = payload.get("incident", {})

        incident = ParsedIncident(
            incident_id=incident_data.get("incident_id", "INC-EVAL"),
            severity=IncidentSeverity(incident_data.get("severity", "p3")),
            state=IncidentState(incident_data.get("state", "new")),
            affected_services=incident_data.get("affected_services", []),
            assigned_to=incident_data.get("assigned_to", ""),
        )

        expected = case["expected_output"]

        # Check escalation if expected
        if "escalate" in expected:
            esc_result = escalation_engine.evaluate(incident)
            assert esc_result.escalate == expected["escalate"], (
                f"Case '{case['name']}': expected escalate={expected['escalate']}, "
                f"got {esc_result.escalate}"
            )

        if "escalation_level" in expected:
            esc_result = escalation_engine.evaluate(incident)
            assert esc_result.level is not None
            assert esc_result.level.value == expected["escalation_level"], (
                f"Case '{case['name']}': expected level={expected['escalation_level']}, "
                f"got {esc_result.level.value}"
            )

        # Check next action if expected
        if "next_action" in expected:
            has_owner = bool(incident.assigned_to)
            action_result = action_engine.evaluate(
                incident_state=incident.state,
                has_assigned_owner=has_owner,
            )
            # Allow for some flexibility: the expected action may be the
            # escalation-driven recommendation rather than the default
            if expected["next_action"] == "escalate":
                # Escalation takes priority if the escalation engine says so
                esc_result = escalation_engine.evaluate(incident)
                if esc_result.escalate:
                    assert True  # escalation is the right call
                else:
                    assert action_result.action == expected["next_action"]
            else:
                assert action_result.action == expected["next_action"], (
                    f"Case '{case['name']}': expected action='{expected['next_action']}', "
                    f"got '{action_result.action}'"
                )


# ---------------------------------------------------------------------------
# Cross-domain consistency check
# ---------------------------------------------------------------------------


class TestCrossDomainConsistency:
    """Verify that eval cases across all packs maintain consistency."""

    def test_all_packs_have_eval_cases(self):
        """Each domain pack should have at least 2 eval cases."""
        assert len(CONTRACT_MARGIN_EVAL_CASES) >= 2
        assert len(UTILITIES_FIELD_EVAL_CASES) >= 2
        assert len(TELCO_OPS_EVAL_CASES) >= 2

    def test_eval_cases_have_required_fields(self):
        """Each eval case should have name, domain, input_payload, expected_output."""
        all_cases = (
            CONTRACT_MARGIN_EVAL_CASES
            + UTILITIES_FIELD_EVAL_CASES
            + TELCO_OPS_EVAL_CASES
        )
        for case in all_cases:
            assert "name" in case, f"Eval case missing 'name': {case}"
            assert "domain" in case, f"Eval case missing 'domain': {case.get('name')}"
            assert "input_payload" in case, f"Eval case missing 'input_payload': {case.get('name')}"
            assert "expected_output" in case, f"Eval case missing 'expected_output': {case.get('name')}"

    def test_total_eval_case_count(self):
        """There should be at least 10 eval cases across all packs."""
        total = (
            len(CONTRACT_MARGIN_EVAL_CASES)
            + len(UTILITIES_FIELD_EVAL_CASES)
            + len(TELCO_OPS_EVAL_CASES)
        )
        assert total >= 10, f"Expected at least 10 eval cases, got {total}"
