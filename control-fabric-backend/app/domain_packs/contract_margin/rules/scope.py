"""
Scope conflict detection for the contract margin domain pack.

Compares executed activities against contract scope boundaries to identify
out-of-scope work, unmet conditions, and scope gaps.
"""

from __future__ import annotations

from typing import Any, Sequence

from app.domain_packs.contract_margin.schemas.contract import (
    ScopeBoundary,
    ScopeType,
)


class ScopeConflictDetector:
    """Detect conflicts between executed activities and contract scope boundaries."""

    def detect_conflicts(
        self,
        scope_boundaries: list[ScopeBoundary],
        executed_activities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return a list of conflict dicts for activities that violate scope.

        Each returned dict contains:
            - ``activity``: the activity name
            - ``conflict_type``: one of ``out_of_scope``, ``conditional_unmet``, ``scope_gap``
            - ``severity``: ``high``, ``medium``, or ``low``
            - ``description``: human-readable explanation
        """
        in_scope_activities = self._collect_activities_by_type(
            scope_boundaries, ScopeType.in_scope
        )
        out_of_scope_activities = self._collect_activities_by_type(
            scope_boundaries, ScopeType.out_of_scope
        )
        conditional_boundaries = [
            b for b in scope_boundaries if b.scope_type == ScopeType.conditional
        ]

        conflicts: list[dict[str, Any]] = []

        for executed in executed_activities:
            activity_name = executed.get("name", "").strip()
            activity_lower = activity_name.lower()
            conditions_met = executed.get("conditions_met", [])
            if isinstance(conditions_met, str):
                conditions_met = [conditions_met]
            conditions_met_lower = {c.lower().strip() for c in conditions_met}

            # Check explicit out-of-scope
            if self._activity_matches(activity_lower, out_of_scope_activities):
                conflicts.append({
                    "activity": activity_name,
                    "conflict_type": "out_of_scope",
                    "severity": "high",
                    "description": (
                        f"Activity '{activity_name}' is explicitly listed as out of scope "
                        f"in the contract boundaries."
                    ),
                })
                continue

            # Check conditional scope
            conditional_conflict = self._check_conditional(
                activity_lower, activity_name, conditional_boundaries, conditions_met_lower
            )
            if conditional_conflict is not None:
                conflicts.append(conditional_conflict)
                continue

            # Check scope gap (activity not listed anywhere)
            if not self._activity_matches(activity_lower, in_scope_activities):
                is_conditional_listed = any(
                    self._activity_matches(activity_lower, [a.lower() for a in b.activities])
                    for b in conditional_boundaries
                )
                if not is_conditional_listed:
                    conflicts.append({
                        "activity": activity_name,
                        "conflict_type": "scope_gap",
                        "severity": "medium",
                        "description": (
                            f"Activity '{activity_name}' is not listed in any scope boundary "
                            f"(in-scope, out-of-scope, or conditional). This may indicate "
                            f"scope creep or an incomplete contract schedule."
                        ),
                    })

        return conflicts

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_activities_by_type(
        boundaries: list[ScopeBoundary],
        scope_type: ScopeType,
    ) -> list[str]:
        """Collect all activity names for a given scope type (lowered)."""
        result: list[str] = []
        for b in boundaries:
            if b.scope_type == scope_type:
                result.extend(a.lower().strip() for a in b.activities)
        return result

    @staticmethod
    def _activity_matches(activity_lower: str, activity_list: list[str]) -> bool:
        """Check if an activity matches any entry in a list (exact or substring)."""
        for listed in activity_list:
            if activity_lower == listed:
                return True
            if activity_lower in listed or listed in activity_lower:
                return True
        return False

    def _check_conditional(
        self,
        activity_lower: str,
        activity_name: str,
        conditional_boundaries: list[ScopeBoundary],
        conditions_met_lower: set[str],
    ) -> dict[str, Any] | None:
        """Check if a conditional scope boundary applies and conditions are unmet."""
        for boundary in conditional_boundaries:
            boundary_activities = [a.lower().strip() for a in boundary.activities]
            if not self._activity_matches(activity_lower, boundary_activities):
                continue

            required_conditions = {c.lower().strip() for c in boundary.conditions}
            if not required_conditions:
                continue

            unmet = required_conditions - conditions_met_lower
            if unmet:
                return {
                    "activity": activity_name,
                    "conflict_type": "conditional_unmet",
                    "severity": "high",
                    "description": (
                        f"Activity '{activity_name}' is conditionally in scope but the "
                        f"following conditions are not met: {', '.join(sorted(unmet))}. "
                        f"Scope boundary description: {boundary.description}"
                    ),
                }
        return None
