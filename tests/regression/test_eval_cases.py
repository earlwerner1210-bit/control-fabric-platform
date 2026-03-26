"""Regression tests -- loads eval cases from domain packs and validates expected outcomes.

Tests at least 10 eval cases across all domain packs:
- contract-margin: billability and leakage rules
- utilities-field: readiness rules
- telco-ops: escalation rules
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from domain_packs.contract_margin.rules.billability_rules import (
    BillabilityRuleEngine,
    WorkEvent,
)
from domain_packs.contract_margin.rules.leakage_rules import (
    LeakageRuleEngine,
    WorkHistoryEntry,
)
from domain_packs.contract_margin.schemas.contract_schemas import (
    BillableEvent,
    ExtractedClause,
    ParsedContract,
    RateCardEntry,
    SLAEntry,
)
from domain_packs.contract_margin.taxonomy.contract_taxonomy import (
    BillableCategory,
    ClauseType,
    ContractType,
)
from services.escalation_engine import EscalationRuleEngine
from services.readiness_engine import ReadinessRuleEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_eval_cases(domain: str) -> list[dict[str, Any]]:
    """Load eval cases from a domain pack."""
    path = PROJECT_ROOT / "domain-packs" / domain / "evals" / "eval_cases.json"
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Reference contract for billability/leakage evals
# ---------------------------------------------------------------------------


@pytest.fixture
def reference_contract() -> ParsedContract:
    """Build a reference contract matching the MSA sample data."""
    return ParsedContract(
        contract_type=ContractType.master_services,
        title="Reference MSA",
        parties=["TelcoCorp Inc.", "FieldServices Ltd"],
        billing_category=BillableCategory.time_and_materials,
        clauses=[
            ExtractedClause(
                clause_id="CL-001",
                clause_type=ClauseType.scope,
                text="Services include: network maintenance, equipment installation, emergency repair, scheduled inspections.",
                section_ref="2.1",
            ),
        ],
        rate_card=[
            RateCardEntry(role_or_item="standard_maintenance", rate=125.0, rate_unit="hourly"),
            RateCardEntry(role_or_item="emergency_repair", rate=187.5, rate_unit="hourly"),
            RateCardEntry(role_or_item="equipment_installation", rate=350.0, rate_unit="per_unit"),
            RateCardEntry(role_or_item="inspection", rate=200.0, rate_unit="per_unit"),
        ],
        sla_entries=[
            SLAEntry(metric_name="P1 Resolution", target_value=4, unit="hours"),
            SLAEntry(metric_name="P2 Resolution", target_value=8, unit="hours"),
        ],
        billable_events=[
            BillableEvent(
                description="Standard maintenance and repair services",
                category=BillableCategory.time_and_materials,
                requires_approval=False,
                excluded_activities=["travel", "admin", "internal meetings"],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Contract-margin: Billability eval cases
# ---------------------------------------------------------------------------


class TestContractMarginBillabilityEvals:
    """Run billability eval cases from the contract-margin domain pack."""

    @pytest.fixture
    def eval_cases(self) -> list[dict[str, Any]]:
        cases = load_eval_cases("contract-margin")
        return [c for c in cases if c["rule_type"] == "billability"]

    @pytest.fixture
    def engine(self) -> BillabilityRuleEngine:
        return BillabilityRuleEngine()

    def test_eval_case_count(self, eval_cases: list[dict[str, Any]]):
        """There should be at least 2 billability eval cases."""
        assert len(eval_cases) >= 2

    def test_billable_standard_maintenance(
        self,
        engine: BillabilityRuleEngine,
        reference_contract: ParsedContract,
        eval_cases: list[dict[str, Any]],
    ):
        """eval-cm-001: Standard maintenance should be billable."""
        case = next(c for c in eval_cases if c["id"] == "eval-cm-001")
        event = WorkEvent(**case["input"])
        result = engine.evaluate(event, reference_contract)
        assert result.billable == case["expected"]["billable"]
        if "confidence_min" in case["expected"]:
            assert result.confidence >= case["expected"]["confidence_min"]

    def test_not_billable_excluded(
        self,
        engine: BillabilityRuleEngine,
        reference_contract: ParsedContract,
        eval_cases: list[dict[str, Any]],
    ):
        """eval-cm-002: Travel should not be billable."""
        case = next(c for c in eval_cases if c["id"] == "eval-cm-002")
        event = WorkEvent(**case["input"])
        result = engine.evaluate(event, reference_contract)
        assert result.billable == case["expected"]["billable"]


# ---------------------------------------------------------------------------
# Contract-margin: Leakage eval cases
# ---------------------------------------------------------------------------


class TestContractMarginLeakageEvals:
    """Run leakage eval cases from the contract-margin domain pack."""

    @pytest.fixture
    def eval_cases(self) -> list[dict[str, Any]]:
        cases = load_eval_cases("contract-margin")
        return [c for c in cases if c["rule_type"] == "leakage"]

    @pytest.fixture
    def engine(self) -> LeakageRuleEngine:
        return LeakageRuleEngine()

    def test_eval_case_count(self, eval_cases: list[dict[str, Any]]):
        """There should be at least 2 leakage eval cases."""
        assert len(eval_cases) >= 2

    def test_unbilled_work_leakage(
        self,
        engine: LeakageRuleEngine,
        reference_contract: ParsedContract,
        eval_cases: list[dict[str, Any]],
    ):
        """eval-cm-003: Unbilled work should produce leakage."""
        case = next(c for c in eval_cases if c["id"] == "eval-cm-003")
        history = [WorkHistoryEntry(**e) for e in case["input"]["work_history"]]
        triggers = engine.evaluate(reference_contract, history)
        assert len(triggers) > 0
        drivers = [t.driver.value for t in triggers]
        assert case["expected"]["driver"] in drivers

    def test_rate_erosion_leakage(
        self,
        engine: LeakageRuleEngine,
        reference_contract: ParsedContract,
        eval_cases: list[dict[str, Any]],
    ):
        """eval-cm-004: Rate erosion should produce leakage."""
        case = next(c for c in eval_cases if c["id"] == "eval-cm-004")
        history = [WorkHistoryEntry(**e) for e in case["input"]["work_history"]]
        triggers = engine.evaluate(reference_contract, history)
        assert len(triggers) > 0
        drivers = [t.driver.value for t in triggers]
        assert case["expected"]["driver"] in drivers


# ---------------------------------------------------------------------------
# Utilities-field: Readiness eval cases
# ---------------------------------------------------------------------------


class TestUtilitiesFieldReadinessEvals:
    """Run readiness eval cases from the utilities-field domain pack."""

    @pytest.fixture
    def eval_cases(self) -> list[dict[str, Any]]:
        return load_eval_cases("utilities-field")

    @pytest.fixture
    def engine(self) -> ReadinessRuleEngine:
        return ReadinessRuleEngine()

    def test_eval_case_count(self, eval_cases: list[dict[str, Any]]):
        """There should be at least 3 readiness eval cases."""
        assert len(eval_cases) >= 3

    def test_ready_all_pass(self, engine: ReadinessRuleEngine, eval_cases: list[dict[str, Any]]):
        """eval-uf-001: All checks pass should be ready."""
        case = next(c for c in eval_cases if c["id"] == "eval-uf-001")
        result = engine.evaluate(case["input"])
        assert result.verdict == case["expected"]["verdict"]
        assert result.ready == case["expected"]["ready"]

    def test_blocked_missing_permit(
        self, engine: ReadinessRuleEngine, eval_cases: list[dict[str, Any]]
    ):
        """eval-uf-002: Missing permit should block."""
        case = next(c for c in eval_cases if c["id"] == "eval-uf-002")
        result = engine.evaluate(case["input"])
        assert result.verdict == case["expected"]["verdict"]
        assert result.ready == case["expected"]["ready"]

    def test_blocked_missing_skill(
        self, engine: ReadinessRuleEngine, eval_cases: list[dict[str, Any]]
    ):
        """eval-uf-003: Missing skill should block."""
        case = next(c for c in eval_cases if c["id"] == "eval-uf-003")
        result = engine.evaluate(case["input"])
        assert result.verdict == case["expected"]["verdict"]
        assert result.ready == case["expected"]["ready"]


# ---------------------------------------------------------------------------
# Telco-ops: Escalation eval cases
# ---------------------------------------------------------------------------


class TestTelcoOpsEscalationEvals:
    """Run escalation eval cases from the telco-ops domain pack."""

    @pytest.fixture
    def eval_cases(self) -> list[dict[str, Any]]:
        return load_eval_cases("telco-ops")

    @pytest.fixture
    def engine(self) -> EscalationRuleEngine:
        return EscalationRuleEngine()

    def test_eval_case_count(self, eval_cases: list[dict[str, Any]]):
        """There should be at least 3 escalation eval cases."""
        assert len(eval_cases) >= 3

    def test_p1_auto_escalate(self, engine: EscalationRuleEngine, eval_cases: list[dict[str, Any]]):
        """eval-to-001: P1 should auto-escalate."""
        case = next(c for c in eval_cases if c["id"] == "eval-to-001")
        now = datetime(2024, 3, 14, 14, 10, tzinfo=UTC)
        result = engine.evaluate(case["input"], current_time=now)
        assert result.should_escalate == case["expected"]["should_escalate"]
        if "recommended_level_min" in case["expected"]:
            assert result.recommended_level >= case["expected"]["recommended_level_min"]

    def test_p3_no_escalation(self, engine: EscalationRuleEngine, eval_cases: list[dict[str, Any]]):
        """eval-to-002: P3 should not escalate early."""
        case = next(c for c in eval_cases if c["id"] == "eval-to-002")
        now = datetime(2024, 3, 14, 14, 15, tzinfo=UTC)
        result = engine.evaluate(case["input"], current_time=now)
        assert result.should_escalate == case["expected"]["should_escalate"]

    def test_sla_breach_escalation(
        self, engine: EscalationRuleEngine, eval_cases: list[dict[str, Any]]
    ):
        """eval-to-003: SLA breach should trigger escalation."""
        case = next(c for c in eval_cases if c["id"] == "eval-to-003")
        test_time = case["input"].pop("_test_current_time", "2024-03-14T14:30:00Z")
        now = datetime.fromisoformat(test_time.replace("Z", "+00:00"))
        result = engine.evaluate(case["input"], current_time=now)
        assert result.should_escalate == case["expected"]["should_escalate"]
        if "sla_status" in case["expected"]:
            assert result.sla_status == case["expected"]["sla_status"]
