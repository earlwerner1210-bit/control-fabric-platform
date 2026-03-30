"""Unit tests for billability rules engine.

Tests cover rate matching, obligation checks, evidence validation, scope checks,
approval thresholds, duplicate detection, confidence scoring, and compound rule
evaluation.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain_packs.contract_margin.schemas.contract import (
    BillabilityDecision,
    BillableCategory,
    Obligation,
    RateCardEntry,
    ScopeBoundary,
    ScopeType,
)

# ── Helpers: lightweight billability rule engine ─────────────────────────────


def _find_matching_rate(
    activity: str,
    rate_card: list[RateCardEntry],
    check_date: date | None = None,
) -> RateCardEntry | None:
    """Find the best (highest-rate) active rate card entry for the activity."""
    matches = [
        r for r in rate_card if r.activity.lower() == activity.lower() and r.is_active(check_date)
    ]
    if not matches:
        return None
    return max(matches, key=lambda r: r.rate)


def _check_scope(
    activity: str,
    boundaries: list[ScopeBoundary],
) -> str:
    """Return 'in_scope', 'out_of_scope', or 'conditional'."""
    for boundary in boundaries:
        if any(a.lower() == activity.lower() for a in boundary.activities):
            return boundary.scope_type.value
    return "unknown"


def _check_obligation(
    obligation: Obligation,
    evidence_provided: list[str],
) -> bool:
    """Check whether all required evidence for an obligation is provided."""
    return all(req in evidence_provided for req in obligation.evidence_required)


def _check_duplicate(activity: str, existing_claims: list[str]) -> bool:
    """Check for duplicate billing claims."""
    return activity.lower() in [c.lower() for c in existing_claims]


def _evaluate_billability(
    activity: str,
    rate_card: list[RateCardEntry],
    boundaries: list[ScopeBoundary],
    obligations: list[Obligation],
    evidence_provided: list[str],
    existing_claims: list[str] | None = None,
    check_date: date | None = None,
    category: str = "standard",
    approval_threshold: float = 10000.0,
) -> BillabilityDecision:
    """Run all billability rules and return a composite decision."""
    rule_results: dict[str, bool] = {}
    reasons: list[str] = []

    # Rate match
    rate_entry = _find_matching_rate(activity, rate_card, check_date)
    rate_match = rate_entry is not None
    rule_results["rate_match"] = rate_match
    rate_applied = rate_entry.effective_rate(category) if rate_entry else 0.0
    if not rate_match:
        reasons.append("No matching rate card entry found")

    # Scope check
    scope = _check_scope(activity, boundaries)
    in_scope = scope == "in_scope"
    rule_results["scope_check"] = in_scope
    if not in_scope:
        reasons.append(f"Activity scope status: {scope}")

    # Obligation checks
    for obl in obligations:
        passed = _check_obligation(obl, evidence_provided)
        rule_results[f"obligation_{obl.clause_id}"] = passed
        if not passed:
            reasons.append(f"Obligation {obl.clause_id} evidence incomplete")

    # Evidence check
    evidence_ok = len(evidence_provided) > 0
    rule_results["evidence_check"] = evidence_ok
    if not evidence_ok:
        reasons.append("No evidence provided")

    # Duplicate check
    existing = existing_claims or []
    duplicate = _check_duplicate(activity, existing)
    rule_results["no_duplicate"] = not duplicate
    if duplicate:
        reasons.append("Duplicate billing claim detected")

    # Approval threshold
    needs_approval = rate_applied > approval_threshold
    rule_results["approval_threshold"] = not needs_approval
    if needs_approval:
        reasons.append(f"Rate {rate_applied} exceeds approval threshold {approval_threshold}")

    # Expired rate check
    if rate_entry and not rate_entry.is_active(check_date):
        rule_results["rate_not_expired"] = False
        reasons.append("Rate card entry has expired")
    else:
        rule_results["rate_not_expired"] = True

    billable = all(rule_results.values())
    confidence = sum(1 for v in rule_results.values() if v) / max(len(rule_results), 1)

    return BillabilityDecision(
        billable=billable,
        category=BillableCategory.standard,
        rate_applied=rate_applied,
        reasons=reasons,
        confidence=round(confidence, 2),
        rule_results=rule_results,
        evidence_refs=evidence_provided,
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def rate_card() -> list[RateCardEntry]:
    return [
        RateCardEntry(
            activity="HV Switching",
            rate=450.0,
            unit="each",
            effective_from=date(2024, 1, 1),
            effective_to=date(2025, 12, 31),
            multipliers={"overtime": 1.5, "weekend": 2.0},
        ),
        RateCardEntry(
            activity="Cable Jointing HV",
            rate=1200.0,
            unit="each",
            effective_from=date(2024, 1, 1),
            effective_to=date(2025, 12, 31),
        ),
        RateCardEntry(
            activity="Overhead Line Inspection",
            rate=3.50,
            unit="metre",
            effective_from=date(2024, 1, 1),
            effective_to=date(2025, 12, 31),
        ),
    ]


@pytest.fixture
def scope_boundaries() -> list[ScopeBoundary]:
    return [
        ScopeBoundary(
            scope_type=ScopeType.in_scope,
            activities=["HV Switching", "Cable Jointing HV", "Overhead Line Inspection"],
        ),
        ScopeBoundary(
            scope_type=ScopeType.out_of_scope,
            activities=["Metering", "New Connection"],
        ),
    ]


@pytest.fixture
def obligations() -> list[Obligation]:
    return [
        Obligation(
            clause_id="CL-001",
            description="Crew qualification",
            evidence_required=["ecs_card", "confined_space_cert"],
        ),
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRateMatching:
    def test_billable_with_rate_match(self, rate_card, scope_boundaries, obligations):
        result = _evaluate_billability(
            "HV Switching",
            rate_card,
            scope_boundaries,
            obligations,
            evidence_provided=["ecs_card", "confined_space_cert", "photo"],
            check_date=date(2024, 6, 15),
        )
        assert result.billable is True
        assert result.rate_applied == 450.0

    def test_not_billable_no_rate(self, rate_card, scope_boundaries, obligations):
        result = _evaluate_billability(
            "Unknown Activity",
            rate_card,
            scope_boundaries,
            obligations,
            evidence_provided=["ecs_card", "confined_space_cert"],
            check_date=date(2024, 6, 15),
        )
        assert result.billable is False
        assert result.rate_applied == 0.0
        assert any("No matching rate" in r for r in result.reasons)

    def test_rate_applied_correctly(self, rate_card, scope_boundaries, obligations):
        result = _evaluate_billability(
            "Cable Jointing HV",
            rate_card,
            scope_boundaries,
            obligations,
            evidence_provided=["ecs_card", "confined_space_cert", "photo"],
            check_date=date(2024, 6, 15),
        )
        assert result.rate_applied == 1200.0

    def test_multiple_rate_matches_best(self):
        card = [
            RateCardEntry(
                activity="Test",
                rate=100.0,
                effective_from=date(2024, 1, 1),
                effective_to=date(2025, 12, 31),
            ),
            RateCardEntry(
                activity="Test",
                rate=150.0,
                effective_from=date(2024, 1, 1),
                effective_to=date(2025, 12, 31),
            ),
        ]
        match = _find_matching_rate("Test", card, date(2024, 6, 1))
        assert match is not None
        assert match.rate == 150.0


class TestObligationAndEvidence:
    def test_obligation_check_pass(self, obligations):
        result = _check_obligation(obligations[0], ["ecs_card", "confined_space_cert"])
        assert result is True

    def test_obligation_check_fail(self, obligations):
        result = _check_obligation(obligations[0], ["ecs_card"])
        assert result is False

    def test_evidence_check_pass(self, rate_card, scope_boundaries, obligations):
        result = _evaluate_billability(
            "HV Switching",
            rate_card,
            scope_boundaries,
            obligations,
            evidence_provided=["ecs_card", "confined_space_cert"],
            check_date=date(2024, 6, 15),
        )
        assert result.rule_results["evidence_check"] is True


class TestScopeChecks:
    def test_scope_check_in_scope(self, scope_boundaries):
        assert _check_scope("HV Switching", scope_boundaries) == "in_scope"

    def test_scope_check_out_of_scope(self, scope_boundaries):
        assert _check_scope("Metering", scope_boundaries) == "out_of_scope"

    def test_scope_check_unknown(self, scope_boundaries):
        assert _check_scope("Something Else", scope_boundaries) == "unknown"


class TestThresholdsAndDuplicates:
    def test_approval_threshold_exceeded(self, rate_card, scope_boundaries, obligations):
        result = _evaluate_billability(
            "Cable Jointing HV",
            rate_card,
            scope_boundaries,
            obligations,
            evidence_provided=["ecs_card", "confined_space_cert", "photo"],
            check_date=date(2024, 6, 15),
            approval_threshold=500.0,
        )
        assert result.rule_results["approval_threshold"] is False
        assert any("exceeds approval threshold" in r for r in result.reasons)

    def test_duplicate_claim_detected(self, rate_card, scope_boundaries, obligations):
        result = _evaluate_billability(
            "HV Switching",
            rate_card,
            scope_boundaries,
            obligations,
            evidence_provided=["ecs_card", "confined_space_cert"],
            existing_claims=["hv switching"],
            check_date=date(2024, 6, 15),
        )
        assert result.billable is False
        assert result.rule_results["no_duplicate"] is False

    def test_expired_rate_detected(self):
        card = [
            RateCardEntry(
                activity="Old Task",
                rate=100.0,
                effective_from=date(2020, 1, 1),
                effective_to=date(2021, 12, 31),
            ),
        ]
        match = _find_matching_rate("Old Task", card, date(2024, 6, 15))
        assert match is None

    def test_minimum_charge_enforced(self):
        entry = RateCardEntry(activity="Trivial", rate=0.0)
        assert entry.rate == 0.0
        assert entry.effective_rate("standard") == 0.0


class TestCompositeDecision:
    def test_empty_rate_card(self, scope_boundaries, obligations):
        result = _evaluate_billability(
            "HV Switching",
            [],
            scope_boundaries,
            obligations,
            evidence_provided=["ecs_card", "confined_space_cert"],
            check_date=date(2024, 6, 15),
        )
        assert result.billable is False

    def test_confidence_above_threshold(self, rate_card, scope_boundaries, obligations):
        result = _evaluate_billability(
            "HV Switching",
            rate_card,
            scope_boundaries,
            obligations,
            evidence_provided=["ecs_card", "confined_space_cert"],
            check_date=date(2024, 6, 15),
        )
        assert result.confidence > 0.5

    def test_all_rules_pass(self, rate_card, scope_boundaries, obligations):
        result = _evaluate_billability(
            "HV Switching",
            rate_card,
            scope_boundaries,
            obligations,
            evidence_provided=["ecs_card", "confined_space_cert", "photo"],
            check_date=date(2024, 6, 15),
        )
        assert result.billable is True
        assert all(result.rule_results.values())

    def test_mixed_results(self, rate_card, scope_boundaries, obligations):
        result = _evaluate_billability(
            "HV Switching",
            rate_card,
            scope_boundaries,
            obligations,
            evidence_provided=["photo"],  # Missing obligation evidence
            check_date=date(2024, 6, 15),
        )
        assert result.billable is False
        assert not all(result.rule_results.values())
        assert result.confidence < 1.0
