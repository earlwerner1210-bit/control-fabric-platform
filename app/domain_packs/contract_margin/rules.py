"""Contract & Margin business rules – billability, leakage, penalty."""

from __future__ import annotations

import uuid
from typing import Any

from app.domain_packs.contract_margin.schemas import (
    BillabilityDecision,
    BillableCategory,
    BillableEvent,
    BillingGate,
    BillingPrerequisite,
    LeakageTrigger,
    NonBillableReason,
    RateCardEntry,
    ReattendanceRule,
    SPENRateCard,
    ServiceCreditRule,
    WorkCategory,
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

        # Rule 5: Missing daywork sheet — work completed but no signed daywork sheet
        for work in work_history:
            if (
                work.get("category") == "daywork"
                and work.get("status") == "completed"
                and not work.get("daywork_sheet_signed")
            ):
                triggers.append(
                    LeakageTrigger(
                        trigger_type="missing_daywork_sheet",
                        description=(
                            f"Daywork '{work.get('activity', 'unknown')}' completed "
                            "but daywork sheet not signed — cannot invoice"
                        ),
                        severity="error",
                        estimated_impact=str(work.get("estimated_value", "unknown")),
                    )
                )

        # Rule 6: Rate escalation missed — contract allows annual escalation but rates not updated
        for work in work_history:
            if work.get("escalation_due") and not work.get("escalation_applied"):
                delta = (
                    work.get("contract_rate", 0) * work.get("escalation_percentage", 0) / 100
                )
                triggers.append(
                    LeakageTrigger(
                        trigger_type="rate_escalation_missed",
                        description=(
                            f"Annual rate escalation not applied for '{work.get('activity', 'unknown')}' — "
                            f"under-recovery of approx {delta:.2f} per {work.get('unit', 'unit')}"
                        ),
                        severity="warning",
                        estimated_impact_value=delta * work.get("volume", 1),
                    )
                )

        # Rule 7: Abortive visit not claimed
        for work in work_history:
            if (
                work.get("abortive") is True
                and not work.get("abortive_claimed")
            ):
                triggers.append(
                    LeakageTrigger(
                        trigger_type="abortive_visit_not_claimed",
                        description=(
                            f"Abortive visit for '{work.get('activity', 'unknown')}' "
                            "(customer no-access) not claimed"
                        ),
                        severity="warning",
                        estimated_impact=str(work.get("abortive_value", "unknown")),
                    )
                )

        # Rule 8: Variation work without change order
        for work in work_history:
            if (
                work.get("is_variation") is True
                and not work.get("variation_order_ref")
            ):
                triggers.append(
                    LeakageTrigger(
                        trigger_type="variation_work_no_change_order",
                        description=(
                            f"Variation work '{work.get('activity', 'unknown')}' "
                            "performed without formal variation order — non-billable"
                        ),
                        severity="error",
                        estimated_impact=str(work.get("estimated_value", "unknown")),
                    )
                )

        # Rule 9: Permit cost not recovered (NRSWA)
        for work in work_history:
            if work.get("permit_cost") and not work.get("permit_cost_recovered"):
                triggers.append(
                    LeakageTrigger(
                        trigger_type="permit_cost_not_recovered",
                        description=(
                            f"NRSWA permit cost £{work.get('permit_cost', 0):.2f} for "
                            f"'{work.get('activity', 'unknown')}' not passed through to client"
                        ),
                        severity="warning",
                        estimated_impact_value=float(work.get("permit_cost", 0)),
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


# ---------------------------------------------------------------------------
# SPEN / Vodafone — billability engine
# ---------------------------------------------------------------------------

# Default re-attendance rules for SPEN managed services
_DEFAULT_REATTENDANCE_RULES: list[ReattendanceRule] = [
    ReattendanceRule(
        trigger="provider_fault",
        billable=False,
        rate_modifier=0.0,
        evidence_required=["root_cause_report", "quality_nonconformance"],
        description="Provider-fault re-attendance is non-billable",
    ),
    ReattendanceRule(
        trigger="customer_fault",
        billable=True,
        rate_modifier=1.0,
        evidence_required=["customer_confirmation", "site_attendance_record"],
        description="Customer-fault re-attendance is billable at standard rate",
    ),
    ReattendanceRule(
        trigger="dno_fault",
        billable=True,
        rate_modifier=1.0,
        evidence_required=["dno_instruction", "network_event_log"],
        description="DNO-fault re-attendance is billable at standard rate",
    ),
    ReattendanceRule(
        trigger="third_party",
        billable=True,
        rate_modifier=1.0,
        evidence_required=["third_party_incident_ref", "site_report"],
        description="Third-party-caused re-attendance is billable at standard rate",
    ),
    ReattendanceRule(
        trigger="weather",
        billable=True,
        rate_modifier=1.0,
        evidence_required=["weather_event_record", "risk_assessment"],
        description="Weather-related re-attendance is billable if weather event documented",
    ),
]


class SPENBillabilityEngine:
    """Determine billability for SPEN electricity distribution managed services.

    Applies SPEN-specific rules including work-category rate lookup, billing-gate
    verification, re-attendance logic, and time-of-day multipliers.
    """

    def __init__(
        self,
        reattendance_rules: list[ReattendanceRule] | None = None,
    ) -> None:
        self._reattendance_rules = reattendance_rules or _DEFAULT_REATTENDANCE_RULES

    def evaluate(
        self,
        activity: str,
        work_category: str,
        rate_card: list[SPENRateCard],
        billing_gates: list[BillingGate],
        is_reattendance: bool = False,
        reattendance_trigger: str = "",
        time_of_day: str = "normal",
    ) -> BillabilityDecision:
        """Evaluate billability of a SPEN work activity.

        Parameters
        ----------
        activity:
            Activity code or description (matched against ``SPENRateCard.activity_code``).
        work_category:
            The ``WorkCategory`` value (e.g. ``"cable_jointing"``).
        rate_card:
            Applicable SPEN rate card entries.
        billing_gates:
            The set of billing prerequisite gates for this job.
        is_reattendance:
            Whether this is a repeat visit.
        reattendance_trigger:
            Reason for re-attendance (e.g. ``"provider_fault"``).
        time_of_day:
            One of ``"normal"``, ``"emergency"``, ``"overtime"``, ``"weekend"``.

        Returns
        -------
        BillabilityDecision
        """
        results: list[RuleResult] = []
        applied_rate: float | None = None
        billable = True

        # ------------------------------------------------------------------
        # Rule 1: Has matching rate in the SPEN rate card
        # ------------------------------------------------------------------
        matching_rate = self._find_matching_rate(activity, work_category, rate_card)
        if matching_rate is None:
            results.append(RuleResult(
                rule_name="has_matching_rate",
                passed=False,
                message=f"No SPEN rate found for activity '{activity}' in category '{work_category}'",
                severity="error",
            ))
            billable = False
        else:
            applied_rate = matching_rate.base_rate
            results.append(RuleResult(
                rule_name="has_matching_rate",
                passed=True,
                message=(
                    f"Rate matched: {matching_rate.activity_code} — "
                    f"£{matching_rate.base_rate:.2f}/{matching_rate.unit}"
                ),
                severity="info",
            ))

        # ------------------------------------------------------------------
        # Rule 2: All billing gates satisfied
        # ------------------------------------------------------------------
        unsatisfied_gates = [g for g in billing_gates if not g.satisfied]
        gates_ok = len(unsatisfied_gates) == 0
        if not gates_ok:
            gate_names = ", ".join(g.gate_type.value for g in unsatisfied_gates)
            results.append(RuleResult(
                rule_name="billing_gates_satisfied",
                passed=False,
                message=f"Unsatisfied billing gates: {gate_names}",
                severity="error",
            ))
            billable = False
        else:
            results.append(RuleResult(
                rule_name="billing_gates_satisfied",
                passed=True,
                message="All billing gates satisfied",
                severity="info",
            ))

        # ------------------------------------------------------------------
        # Rule 3: Re-attendance check
        # ------------------------------------------------------------------
        if is_reattendance:
            reat_rule = self._find_reattendance_rule(reattendance_trigger)
            if reat_rule is None:
                results.append(RuleResult(
                    rule_name="reattendance_check",
                    passed=False,
                    message=f"Unknown re-attendance trigger: '{reattendance_trigger}'",
                    severity="warning",
                ))
                billable = False
            elif not reat_rule.billable:
                results.append(RuleResult(
                    rule_name="reattendance_check",
                    passed=False,
                    message=f"Re-attendance non-billable: {reat_rule.description}",
                    severity="error",
                ))
                billable = False
                applied_rate = 0.0
            else:
                if applied_rate is not None:
                    applied_rate *= reat_rule.rate_modifier
                results.append(RuleResult(
                    rule_name="reattendance_check",
                    passed=True,
                    message=f"Re-attendance billable: {reat_rule.description}",
                    severity="info",
                ))
        else:
            results.append(RuleResult(
                rule_name="reattendance_check",
                passed=True,
                message="Not a re-attendance",
                severity="info",
            ))

        # ------------------------------------------------------------------
        # Rule 4: Time-of-day multiplier
        # ------------------------------------------------------------------
        if matching_rate is not None and applied_rate is not None and applied_rate > 0:
            multiplier = self._get_time_multiplier(time_of_day, matching_rate)
            applied_rate *= multiplier
            results.append(RuleResult(
                rule_name="time_of_day_modifier",
                passed=True,
                message=(
                    f"Time-of-day modifier applied: {time_of_day} -> {multiplier}x "
                    f"(effective rate £{applied_rate:.2f})"
                ),
                severity="info",
            ))
        else:
            results.append(RuleResult(
                rule_name="time_of_day_modifier",
                passed=True,
                message="No time-of-day modifier applicable",
                severity="info",
            ))

        # ------------------------------------------------------------------
        # Rule 5: Approval threshold
        # ------------------------------------------------------------------
        if (
            matching_rate is not None
            and matching_rate.requires_approval_above is not None
            and applied_rate is not None
            and applied_rate > matching_rate.requires_approval_above
        ):
            has_approval = any(
                g.gate_type == BillingPrerequisite.prior_approval and g.satisfied
                for g in billing_gates
            )
            if not has_approval:
                results.append(RuleResult(
                    rule_name="approval_threshold",
                    passed=False,
                    message=(
                        f"Effective rate £{applied_rate:.2f} exceeds approval threshold "
                        f"£{matching_rate.requires_approval_above:.2f} — prior approval required"
                    ),
                    severity="error",
                ))
                billable = False
            else:
                results.append(RuleResult(
                    rule_name="approval_threshold",
                    passed=True,
                    message="Prior approval obtained for value above threshold",
                    severity="info",
                ))
        else:
            results.append(RuleResult(
                rule_name="approval_threshold",
                passed=True,
                message="No approval threshold applicable",
                severity="info",
            ))

        # ------------------------------------------------------------------
        # Build decision
        # ------------------------------------------------------------------
        confidence = sum(1 for r in results if r.passed) / max(len(results), 1)

        return BillabilityDecision(
            billable=billable,
            confidence=confidence,
            reasons=[r.message for r in results if not r.passed],
            rate_applied=applied_rate,
            category=BillableCategory.daywork if time_of_day == "normal" else BillableCategory.emergency_callout,
            rule_results=[{"rule": r.rule_name, "passed": r.passed, "message": r.message} for r in results],
        )

    # -- helpers -----------------------------------------------------------

    def _find_matching_rate(
        self,
        activity: str,
        work_category: str,
        rate_card: list[SPENRateCard],
    ) -> SPENRateCard | None:
        """Find the best-matching rate card entry by work category + activity code."""
        activity_lower = activity.lower().strip()
        category_lower = work_category.lower().strip()

        # Exact match on both fields
        for rc in rate_card:
            if (
                rc.work_category.value == category_lower
                and rc.activity_code.lower() == activity_lower
            ):
                return rc

        # Fuzzy: match on activity_code substring
        for rc in rate_card:
            if rc.work_category.value == category_lower and (
                activity_lower in rc.activity_code.lower()
                or rc.activity_code.lower() in activity_lower
            ):
                return rc

        # Fallback: match on work_category only (first entry)
        for rc in rate_card:
            if rc.work_category.value == category_lower:
                return rc

        return None

    def _find_reattendance_rule(self, trigger: str) -> ReattendanceRule | None:
        trigger_lower = trigger.lower().strip()
        for rule in self._reattendance_rules:
            if rule.trigger.lower() == trigger_lower:
                return rule
        return None

    @staticmethod
    def _get_time_multiplier(time_of_day: str, rate: SPENRateCard) -> float:
        mapping = {
            "emergency": rate.emergency_multiplier,
            "overtime": rate.overtime_multiplier,
            "weekend": rate.weekend_multiplier,
        }
        return mapping.get(time_of_day.lower(), 1.0)


# ---------------------------------------------------------------------------
# SPEN / Vodafone — service credit engine
# ---------------------------------------------------------------------------


class ServiceCreditEngine:
    """Calculate service credits for SLA breaches under SPEN/Vodafone contracts."""

    def evaluate(
        self,
        sla_performance: dict[str, float],
        credit_rules: list[ServiceCreditRule],
        monthly_invoice_value: float = 0.0,
    ) -> list[dict]:
        """Evaluate SLA performance against service credit rules.

        Parameters
        ----------
        sla_performance:
            Mapping of SLA metric name to actual performance value.
            Example: ``{"response_time": 3.5, "first_time_fix": 0.82}``.
        credit_rules:
            The contractual service credit rules to evaluate.
        monthly_invoice_value:
            Total monthly invoice value — used to apply the cap.

        Returns
        -------
        list[dict]
            One entry per rule evaluated, including whether a credit is triggered.
        """
        results: list[dict] = []

        for rule in credit_rules:
            actual_value = sla_performance.get(rule.sla_metric)
            if actual_value is None:
                results.append({
                    "sla_metric": rule.sla_metric,
                    "threshold": rule.threshold_value,
                    "actual": None,
                    "breached": False,
                    "credit_percentage": 0.0,
                    "credit_value": 0.0,
                    "capped": False,
                    "note": "No performance data available for this metric",
                })
                continue

            # Determine breach: for time-based metrics, actual > threshold = breach;
            # for percentage metrics (e.g. first_time_fix), actual < threshold = breach.
            is_time_metric = rule.sla_metric in ("response_time", "resolution_time")
            breached = (
                actual_value > rule.threshold_value
                if is_time_metric
                else actual_value < rule.threshold_value
            )

            credit_pct = rule.credit_percentage if breached else 0.0
            credit_value = monthly_invoice_value * (credit_pct / 100.0) if breached else 0.0

            # Apply cap
            cap_value = monthly_invoice_value * (rule.cap_percentage / 100.0)
            capped = credit_value > cap_value > 0
            if capped:
                credit_value = cap_value

            results.append({
                "sla_metric": rule.sla_metric,
                "threshold": rule.threshold_value,
                "actual": actual_value,
                "breached": breached,
                "credit_percentage": credit_pct,
                "credit_value": round(credit_value, 2),
                "capped": capped,
                "cap_percentage": rule.cap_percentage,
                "measurement_period": rule.measurement_period,
                "exclusions": rule.exclusions,
                "note": (
                    f"SLA breached: actual {actual_value} vs threshold {rule.threshold_value}"
                    if breached
                    else "SLA met"
                ),
            })

        return results
