"""Contract & Margin business rules – billability, leakage, penalty."""

from __future__ import annotations

import uuid
from typing import Any

from app.domain_packs.contract_margin.schemas import (
    BillabilityDecision,
    BillableEvent,
    LeakageTrigger,
    RateCardEntry,
)
from app.schemas.validation import RuleResult


class BillabilityRuleEngine:
    """Determine whether a work activity is billable under a contract."""

    def evaluate(
        self,
        activity: str,
        rate_card: list[RateCardEntry],
        obligations: list[dict],
        evidence_ids: list[uuid.UUID] | None = None,
    ) -> BillabilityDecision:
        results: list[RuleResult] = []

        # Rule 1: has valid rate
        matching_rate = self._find_matching_rate(activity, rate_card)
        results.append(
            RuleResult(
                rule_name="has_valid_rate",
                passed=matching_rate is not None,
                message=f"Rate found: {matching_rate.rate}/{matching_rate.unit}" if matching_rate else "No matching rate",
                severity="error" if not matching_rate else "info",
            )
        )

        # Rule 2: within scope
        in_scope = self._is_within_scope(activity, obligations)
        results.append(
            RuleResult(
                rule_name="within_scope",
                passed=in_scope,
                message="Activity is within contract scope" if in_scope else "Activity may be out of scope",
                severity="warning" if not in_scope else "info",
            )
        )

        # Rule 3: not excluded
        excluded = self._is_excluded(activity)
        results.append(
            RuleResult(
                rule_name="not_excluded_activity",
                passed=not excluded,
                message="Activity not excluded" if not excluded else "Activity is on exclusion list",
                severity="error" if excluded else "info",
            )
        )

        all_passed = all(r.passed for r in results)
        confidence = sum(1 for r in results if r.passed) / max(len(results), 1)

        return BillabilityDecision(
            billable=all_passed,
            confidence=confidence,
            evidence_ids=evidence_ids or [],
            reasons=[r.message for r in results if not r.passed],
            rate_applied=matching_rate.rate if matching_rate else None,
        )

    def _find_matching_rate(self, activity: str, rate_card: list[RateCardEntry]) -> RateCardEntry | None:
        activity_lower = activity.lower().replace(" ", "_")
        for rate in rate_card:
            if rate.activity.lower() == activity_lower:
                return rate
            # Fuzzy match
            if activity_lower in rate.activity.lower() or rate.activity.lower() in activity_lower:
                return rate
        return None

    def _is_within_scope(self, activity: str, obligations: list[dict]) -> bool:
        activity_lower = activity.lower()
        for ob in obligations:
            text = ob.get("text", "").lower() + ob.get("description", "").lower()
            if activity_lower in text or any(kw in text for kw in activity_lower.split("_")):
                return True
        return len(obligations) == 0  # If no obligations defined, assume in scope

    def _is_excluded(self, activity: str) -> bool:
        exclusions = {"internal_meeting", "travel_time_non_billable", "training_non_certified"}
        return activity.lower().replace(" ", "_") in exclusions


class LeakageRuleEngine:
    """Detect potential revenue leakage."""

    def evaluate(
        self,
        contract_objects: list[dict],
        work_history: list[dict] | None = None,
    ) -> list[LeakageTrigger]:
        triggers: list[LeakageTrigger] = []
        work_history = work_history or []

        # Rule 1: Unbilled completed work
        for work in work_history:
            if work.get("status") == "completed" and not work.get("billed"):
                triggers.append(
                    LeakageTrigger(
                        trigger_type="unbilled_completed_work",
                        description=f"Work '{work.get('activity', 'unknown')}' completed but not billed",
                        severity="error",
                        estimated_impact=str(work.get("estimated_value", "unknown")),
                    )
                )

        # Rule 2: Rate below contract
        for work in work_history:
            if work.get("billed_rate") and work.get("contract_rate"):
                if work["billed_rate"] < work["contract_rate"]:
                    triggers.append(
                        LeakageTrigger(
                            trigger_type="rate_below_contract",
                            description=f"Billed rate ${work['billed_rate']} below contract rate ${work['contract_rate']}",
                            severity="warning",
                        )
                    )

        # Rule 3: Scope creep detection
        for work in work_history:
            if work.get("change_order_required") and not work.get("change_order_id"):
                triggers.append(
                    LeakageTrigger(
                        trigger_type="scope_creep_detected",
                        description=f"Out-of-scope work '{work.get('activity')}' without change order",
                        severity="error",
                    )
                )

        # Rule 4: Penalty exposure
        penalty_objects = [o for o in contract_objects if o.get("control_type") == "penalty_condition"]
        for penalty in penalty_objects:
            payload = penalty.get("payload", {})
            if payload.get("breach_detected"):
                triggers.append(
                    LeakageTrigger(
                        trigger_type="penalty_exposure_unmitigated",
                        description=f"Penalty condition '{penalty.get('label', '')}' breach detected without mitigation",
                        severity="critical",
                    )
                )

        return triggers


class PenaltyRuleEngine:
    """Evaluate penalty conditions and exposure."""

    def evaluate(
        self,
        penalty_objects: list[dict],
        sla_performance: dict[str, Any] | None = None,
    ) -> list[RuleResult]:
        results: list[RuleResult] = []
        sla_performance = sla_performance or {}

        for penalty in penalty_objects:
            payload = penalty.get("payload", {})
            label = penalty.get("label", "unknown")

            # Check if SLA is being met
            penalty_text = payload.get("text", "").lower()
            if "sla" in penalty_text or "response time" in penalty_text:
                met = sla_performance.get("sla_met", True)
                results.append(
                    RuleResult(
                        rule_name=f"penalty_exposure_{label}",
                        passed=met,
                        message=f"SLA met for {label}" if met else f"SLA breach risk: {label}",
                        severity="error" if not met else "info",
                    )
                )

        return results
