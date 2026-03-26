"""Unit tests for scope detection logic.

Tests cover in-scope, out-of-scope, conditional, gap detection, case
insensitivity, partial matching, and empty boundary handling.
"""

from __future__ import annotations

import pytest

from app.domain_packs.contract_margin.schemas.contract import (
    ScopeBoundary,
    ScopeType,
)

# ── Scope detector ───────────────────────────────────────────────────────────


class ScopeDetector:
    """Determine scope classification for an activity given contract boundaries."""

    def __init__(self, boundaries: list[ScopeBoundary]) -> None:
        self.boundaries = boundaries

    def classify(self, activity: str) -> dict:
        """Return {'scope_type': ..., 'boundary': ..., 'conditions': [...]}."""
        for boundary in self.boundaries:
            for act in boundary.activities:
                if act.lower() == activity.lower():
                    return {
                        "scope_type": boundary.scope_type.value,
                        "boundary": boundary.description,
                        "conditions": boundary.conditions,
                    }
        return {
            "scope_type": "unknown",
            "boundary": None,
            "conditions": [],
        }

    def classify_partial(self, activity: str) -> dict:
        """Partial matching -- activity substring match."""
        for boundary in self.boundaries:
            for act in boundary.activities:
                if act.lower() in activity.lower() or activity.lower() in act.lower():
                    return {
                        "scope_type": boundary.scope_type.value,
                        "boundary": boundary.description,
                        "conditions": boundary.conditions,
                    }
        return {
            "scope_type": "unknown",
            "boundary": None,
            "conditions": [],
        }

    def detect_gaps(self, activities: list[str]) -> list[str]:
        """Return activities that don't match any scope boundary."""
        known = set()
        for boundary in self.boundaries:
            known.update(a.lower() for a in boundary.activities)
        return [a for a in activities if a.lower() not in known]


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def detector() -> ScopeDetector:
    boundaries = [
        ScopeBoundary(
            scope_type=ScopeType.in_scope,
            description="Core HV maintenance",
            activities=["HV Switching", "Cable Jointing HV", "Overhead Line Inspection"],
        ),
        ScopeBoundary(
            scope_type=ScopeType.out_of_scope,
            description="Excluded activities",
            activities=["Metering", "New Connection"],
        ),
        ScopeBoundary(
            scope_type=ScopeType.conditional,
            description="Conditional on HV works",
            activities=["Reinstatement"],
            conditions=["Directly caused by in-scope HV works", "Approved by project manager"],
        ),
    ]
    return ScopeDetector(boundaries)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestScopeDetector:
    def test_out_of_scope_detected(self, detector):
        result = detector.classify("Metering")
        assert result["scope_type"] == "out_of_scope"

    def test_in_scope_no_conflict(self, detector):
        result = detector.classify("HV Switching")
        assert result["scope_type"] == "in_scope"
        assert result["boundary"] == "Core HV maintenance"

    def test_scope_gap(self, detector):
        gaps = detector.detect_gaps(["HV Switching", "Drain Clearance", "Metering", "Landscaping"])
        assert "Drain Clearance" in gaps
        assert "Landscaping" in gaps
        assert "HV Switching" not in gaps
        assert "Metering" not in gaps

    def test_conditional_unmet(self, detector):
        result = detector.classify("Reinstatement")
        assert result["scope_type"] == "conditional"
        assert len(result["conditions"]) == 2

    def test_empty_boundaries(self):
        detector = ScopeDetector([])
        result = detector.classify("HV Switching")
        assert result["scope_type"] == "unknown"

    def test_multiple_activities(self, detector):
        results = [
            detector.classify(a)
            for a in ["HV Switching", "Cable Jointing HV", "Overhead Line Inspection"]
        ]
        assert all(r["scope_type"] == "in_scope" for r in results)

    def test_case_insensitive(self, detector):
        result = detector.classify("hv switching")
        assert result["scope_type"] == "in_scope"
        result2 = detector.classify("METERING")
        assert result2["scope_type"] == "out_of_scope"

    def test_partial_match(self, detector):
        result = detector.classify_partial("HV Switching Operation")
        assert result["scope_type"] == "in_scope"
