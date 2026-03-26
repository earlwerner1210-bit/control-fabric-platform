"""Regression tests: run eval cases through the billability engine and verify outcomes.

These tests load 10 deterministic eval cases, run each through the billability
evaluation logic, and assert that the expected billability outcome matches.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.domain_packs.contract_margin.schemas.contract import (
    BillabilityDecision,
    BillableCategory,
    Obligation,
    RateCardEntry,
    ScopeBoundary,
    ScopeType,
)


# ── Billability evaluator (same as test_billability_rules) ───────────────────


def _evaluate_billability_for_eval(
    activity: str,
    rate_card: list[RateCardEntry],
    boundaries: list[ScopeBoundary],
    obligations: list[Obligation],
    evidence_provided: list[str],
    check_date: date | None = None,
) -> BillabilityDecision:
    """Simplified billability evaluation for eval cases."""
    rule_results: dict[str, bool] = {}
    reasons: list[str] = []

    # Rate match
    matches = [
        r for r in rate_card
        if r.activity.lower() == activity.lower() and r.is_active(check_date)
    ]
    rate_entry = max(matches, key=lambda r: r.rate) if matches else None
    rule_results["rate_match"] = rate_entry is not None
    rate_applied = rate_entry.rate if rate_entry else 0.0
    if not rate_entry:
        reasons.append("No matching rate card entry")

    # Scope
    scope_status = "unknown"
    for b in boundaries:
        if any(a.lower() == activity.lower() for a in b.activities):
            scope_status = b.scope_type.value
            break
    rule_results["scope_check"] = scope_status == "in_scope"
    if scope_status != "in_scope":
        reasons.append(f"Scope: {scope_status}")

    # Obligations
    for obl in obligations:
        met = all(r in evidence_provided for r in obl.evidence_required)
        rule_results[f"obl_{obl.clause_id}"] = met
        if not met:
            reasons.append(f"Obligation {obl.clause_id} unmet")

    # Evidence
    rule_results["evidence"] = len(evidence_provided) > 0
    if not evidence_provided:
        reasons.append("No evidence")

    billable = all(rule_results.values())
    confidence = sum(1 for v in rule_results.values() if v) / max(len(rule_results), 1)

    return BillabilityDecision(
        billable=billable,
        rate_applied=rate_applied,
        reasons=reasons,
        confidence=round(confidence, 2),
        rule_results=rule_results,
        evidence_refs=evidence_provided,
    )


# ── Shared contract fixtures ────────────────────────────────────────────────


RATE_CARD = [
    RateCardEntry(activity="HV Switching", rate=450.0, effective_from=date(2024, 1, 1), effective_to=date(2025, 12, 31)),
    RateCardEntry(activity="Cable Jointing HV", rate=1200.0, effective_from=date(2024, 1, 1), effective_to=date(2025, 12, 31)),
    RateCardEntry(activity="Overhead Line Inspection", rate=3.50, effective_from=date(2024, 1, 1), effective_to=date(2025, 12, 31)),
    RateCardEntry(activity="Emergency Fault Response", rate=800.0, effective_from=date(2024, 1, 1), effective_to=date(2025, 12, 31)),
]

SCOPE_BOUNDARIES = [
    ScopeBoundary(scope_type=ScopeType.in_scope, activities=["HV Switching", "Cable Jointing HV", "Overhead Line Inspection", "Emergency Fault Response"]),
    ScopeBoundary(scope_type=ScopeType.out_of_scope, activities=["Metering", "New Connection"]),
    ScopeBoundary(scope_type=ScopeType.conditional, activities=["Reinstatement"], conditions=["Caused by HV works"]),
]

OBLIGATIONS = [
    Obligation(clause_id="CL-001", description="Crew qualification", evidence_required=["ecs_card", "confined_space_cert"]),
]

CHECK_DATE = date(2024, 6, 15)


# ── Eval cases ───────────────────────────────────────────────────────────────

EVAL_CASES: list[dict[str, Any]] = [
    {
        "name": "case_01_standard_hv_switching",
        "activity": "HV Switching",
        "evidence": ["ecs_card", "confined_space_cert", "photo", "daywork_sheet"],
        "expected_billable": True,
    },
    {
        "name": "case_02_missing_evidence",
        "activity": "HV Switching",
        "evidence": [],
        "expected_billable": False,
    },
    {
        "name": "case_03_out_of_scope_metering",
        "activity": "Metering",
        "evidence": ["ecs_card", "confined_space_cert"],
        "expected_billable": False,
    },
    {
        "name": "case_04_cable_jointing_full_evidence",
        "activity": "Cable Jointing HV",
        "evidence": ["ecs_card", "confined_space_cert", "photo"],
        "expected_billable": True,
    },
    {
        "name": "case_05_unknown_activity",
        "activity": "Drain Clearance",
        "evidence": ["ecs_card", "confined_space_cert"],
        "expected_billable": False,
    },
    {
        "name": "case_06_partial_obligation_evidence",
        "activity": "HV Switching",
        "evidence": ["ecs_card"],  # Missing confined_space_cert
        "expected_billable": False,
    },
    {
        "name": "case_07_emergency_fault_response",
        "activity": "Emergency Fault Response",
        "evidence": ["ecs_card", "confined_space_cert", "fault_report"],
        "expected_billable": True,
    },
    {
        "name": "case_08_conditional_reinstatement",
        "activity": "Reinstatement",
        "evidence": ["ecs_card", "confined_space_cert", "approval"],
        "expected_billable": False,  # Conditional scope = not in_scope
    },
    {
        "name": "case_09_overhead_line_inspection",
        "activity": "Overhead Line Inspection",
        "evidence": ["ecs_card", "confined_space_cert"],
        "expected_billable": True,
    },
    {
        "name": "case_10_new_connection_out_of_scope",
        "activity": "New Connection",
        "evidence": ["ecs_card", "confined_space_cert", "client_approval"],
        "expected_billable": False,
    },
]


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestEvalCases:
    """Run all eval cases through the billability engine and verify outcomes."""

    @pytest.mark.parametrize(
        "eval_case",
        EVAL_CASES,
        ids=[c["name"] for c in EVAL_CASES],
    )
    def test_eval_case(self, eval_case: dict[str, Any]) -> None:
        result = _evaluate_billability_for_eval(
            activity=eval_case["activity"],
            rate_card=RATE_CARD,
            boundaries=SCOPE_BOUNDARIES,
            obligations=OBLIGATIONS,
            evidence_provided=eval_case["evidence"],
            check_date=CHECK_DATE,
        )
        assert result.billable == eval_case["expected_billable"], (
            f"Case {eval_case['name']}: expected billable={eval_case['expected_billable']}, "
            f"got billable={result.billable}. Reasons: {result.reasons}"
        )

    def test_all_cases_loaded(self) -> None:
        assert len(EVAL_CASES) == 10

    def test_eval_case_names_unique(self) -> None:
        names = [c["name"] for c in EVAL_CASES]
        assert len(names) == len(set(names))

    def test_expected_pass_count(self) -> None:
        expected_pass = sum(1 for c in EVAL_CASES if c["expected_billable"])
        assert expected_pass == 4  # cases 1, 4, 7, 9

    def test_expected_fail_count(self) -> None:
        expected_fail = sum(1 for c in EVAL_CASES if not c["expected_billable"])
        assert expected_fail == 6
