"""Unit tests for leakage detection rules.

Tests cover detection of unbilled work, below-contract rates, scope creep,
missing evidence, time/rate mismatches, material passthrough, subcontractor
leakage, and mobilisation charges.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain_packs.contract_margin.schemas.contract import (
    LeakageTrigger,
    PriorityLevel,
    RateCardEntry,
    ScopeBoundary,
    ScopeType,
)

# ── Lightweight leakage rule engine ──────────────────────────────────────────


def detect_leakage(
    work_orders: list[dict[str, Any]],
    rate_card: list[RateCardEntry],
    scope_boundaries: list[ScopeBoundary],
) -> list[LeakageTrigger]:
    """Detect revenue leakage triggers from work orders against contract terms."""
    triggers: list[LeakageTrigger] = []

    for wo in work_orders:
        activity = wo.get("activity", "")
        status = wo.get("status", "")
        billed = wo.get("billed", False)
        billed_rate = wo.get("billed_rate", 0.0)
        has_daywork_sheet = wo.get("has_daywork_sheet", False)
        hours_claimed = wo.get("hours_claimed", 0.0)
        hours_worked = wo.get("hours_worked", 0.0)
        includes_materials = wo.get("includes_materials", False)
        materials_charged = wo.get("materials_charged", False)
        is_subcontractor = wo.get("is_subcontractor", False)
        sub_margin_applied = wo.get("sub_margin_applied", False)
        includes_mobilisation = wo.get("includes_mobilisation", False)
        mobilisation_charged = wo.get("mobilisation_charged", False)

        # 1. Unbilled completed work
        if status == "completed" and not billed:
            triggers.append(
                LeakageTrigger(
                    trigger_type="unbilled_completed_work",
                    description=f"Completed work order for '{activity}' has not been billed",
                    severity=PriorityLevel.high,
                    estimated_impact_value=_get_contract_rate(activity, rate_card),
                )
            )

        # 2. Rate below contract
        contract_rate = _get_contract_rate(activity, rate_card)
        if billed and contract_rate > 0 and billed_rate < contract_rate:
            triggers.append(
                LeakageTrigger(
                    trigger_type="rate_below_contract",
                    description=f"Billed rate ({billed_rate}) is below contract rate ({contract_rate}) for '{activity}'",
                    severity=PriorityLevel.high,
                    estimated_impact_value=contract_rate - billed_rate,
                )
            )

        # 3. Scope creep
        for boundary in scope_boundaries:
            if boundary.scope_type == ScopeType.out_of_scope:
                if activity.lower() in [a.lower() for a in boundary.activities]:
                    triggers.append(
                        LeakageTrigger(
                            trigger_type="scope_creep",
                            description=f"Activity '{activity}' is out of scope but work was performed",
                            severity=PriorityLevel.medium,
                        )
                    )

        # 4. Missing daywork sheet
        if status == "completed" and not has_daywork_sheet:
            triggers.append(
                LeakageTrigger(
                    trigger_type="missing_daywork_sheet",
                    description=f"Completed work order for '{activity}' has no daywork sheet",
                    severity=PriorityLevel.medium,
                )
            )

        # 5. Time/rate mismatch
        if hours_claimed > 0 and hours_worked > 0 and hours_claimed < hours_worked * 0.9:
            triggers.append(
                LeakageTrigger(
                    trigger_type="time_rate_mismatch",
                    description=f"Hours claimed ({hours_claimed}) significantly less than worked ({hours_worked})",
                    severity=PriorityLevel.medium,
                    estimated_impact_value=(hours_worked - hours_claimed)
                    * (billed_rate or contract_rate),
                )
            )

        # 6. Material passthrough
        if includes_materials and not materials_charged:
            triggers.append(
                LeakageTrigger(
                    trigger_type="material_passthrough",
                    description=f"Materials used in '{activity}' but not charged through",
                    severity=PriorityLevel.medium,
                )
            )

        # 7. Subcontractor leak
        if is_subcontractor and not sub_margin_applied:
            triggers.append(
                LeakageTrigger(
                    trigger_type="subcontractor_leak",
                    description=f"Subcontractor work for '{activity}' without margin applied",
                    severity=PriorityLevel.high,
                )
            )

        # 8. Mobilisation not charged
        if includes_mobilisation and not mobilisation_charged:
            triggers.append(
                LeakageTrigger(
                    trigger_type="mobilisation_not_charged",
                    description=f"Mobilisation for '{activity}' was not charged",
                    severity=PriorityLevel.low,
                )
            )

    return triggers


def _get_contract_rate(activity: str, rate_card: list[RateCardEntry]) -> float:
    for entry in rate_card:
        if entry.activity.lower() == activity.lower():
            return entry.rate
    return 0.0


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def rate_card() -> list[RateCardEntry]:
    return [
        RateCardEntry(activity="HV Switching", rate=450.0),
        RateCardEntry(activity="Cable Jointing HV", rate=1200.0),
    ]


@pytest.fixture
def scope_boundaries() -> list[ScopeBoundary]:
    return [
        ScopeBoundary(
            scope_type=ScopeType.in_scope, activities=["HV Switching", "Cable Jointing HV"]
        ),
        ScopeBoundary(scope_type=ScopeType.out_of_scope, activities=["Metering", "New Connection"]),
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestLeakageDetection:
    def test_unbilled_completed_work(self, rate_card, scope_boundaries):
        orders = [
            {
                "activity": "HV Switching",
                "status": "completed",
                "billed": False,
                "has_daywork_sheet": True,
            }
        ]
        triggers = detect_leakage(orders, rate_card, scope_boundaries)
        types = [t.trigger_type for t in triggers]
        assert "unbilled_completed_work" in types

    def test_rate_below_contract(self, rate_card, scope_boundaries):
        orders = [
            {
                "activity": "HV Switching",
                "status": "completed",
                "billed": True,
                "billed_rate": 350.0,
                "has_daywork_sheet": True,
            }
        ]
        triggers = detect_leakage(orders, rate_card, scope_boundaries)
        types = [t.trigger_type for t in triggers]
        assert "rate_below_contract" in types

    def test_scope_creep_detected(self, rate_card, scope_boundaries):
        orders = [
            {
                "activity": "Metering",
                "status": "completed",
                "billed": False,
                "has_daywork_sheet": True,
            }
        ]
        triggers = detect_leakage(orders, rate_card, scope_boundaries)
        types = [t.trigger_type for t in triggers]
        assert "scope_creep" in types

    def test_no_leakage_clean(self, rate_card, scope_boundaries):
        orders = [
            {
                "activity": "HV Switching",
                "status": "completed",
                "billed": True,
                "billed_rate": 450.0,
                "has_daywork_sheet": True,
            }
        ]
        triggers = detect_leakage(orders, rate_card, scope_boundaries)
        assert len(triggers) == 0

    def test_missing_daywork_sheet(self, rate_card, scope_boundaries):
        orders = [
            {
                "activity": "HV Switching",
                "status": "completed",
                "billed": True,
                "billed_rate": 450.0,
                "has_daywork_sheet": False,
            }
        ]
        triggers = detect_leakage(orders, rate_card, scope_boundaries)
        types = [t.trigger_type for t in triggers]
        assert "missing_daywork_sheet" in types

    def test_time_rate_mismatch(self, rate_card, scope_boundaries):
        orders = [
            {
                "activity": "HV Switching",
                "status": "completed",
                "billed": True,
                "billed_rate": 450.0,
                "has_daywork_sheet": True,
                "hours_claimed": 4.0,
                "hours_worked": 8.0,
            }
        ]
        triggers = detect_leakage(orders, rate_card, scope_boundaries)
        types = [t.trigger_type for t in triggers]
        assert "time_rate_mismatch" in types

    def test_material_passthrough(self, rate_card, scope_boundaries):
        orders = [
            {
                "activity": "HV Switching",
                "status": "completed",
                "billed": True,
                "billed_rate": 450.0,
                "has_daywork_sheet": True,
                "includes_materials": True,
                "materials_charged": False,
            }
        ]
        triggers = detect_leakage(orders, rate_card, scope_boundaries)
        types = [t.trigger_type for t in triggers]
        assert "material_passthrough" in types

    def test_subcontractor_leak(self, rate_card, scope_boundaries):
        orders = [
            {
                "activity": "HV Switching",
                "status": "completed",
                "billed": True,
                "billed_rate": 450.0,
                "has_daywork_sheet": True,
                "is_subcontractor": True,
                "sub_margin_applied": False,
            }
        ]
        triggers = detect_leakage(orders, rate_card, scope_boundaries)
        types = [t.trigger_type for t in triggers]
        assert "subcontractor_leak" in types

    def test_mobilisation_not_charged(self, rate_card, scope_boundaries):
        orders = [
            {
                "activity": "HV Switching",
                "status": "completed",
                "billed": True,
                "billed_rate": 450.0,
                "has_daywork_sheet": True,
                "includes_mobilisation": True,
                "mobilisation_charged": False,
            }
        ]
        triggers = detect_leakage(orders, rate_card, scope_boundaries)
        types = [t.trigger_type for t in triggers]
        assert "mobilisation_not_charged" in types

    def test_multiple_triggers(self, rate_card, scope_boundaries):
        orders = [
            {
                "activity": "HV Switching",
                "status": "completed",
                "billed": False,
                "has_daywork_sheet": False,
                "includes_materials": True,
                "materials_charged": False,
            }
        ]
        triggers = detect_leakage(orders, rate_card, scope_boundaries)
        assert len(triggers) >= 3
