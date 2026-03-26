"""Contract & Margin business rules – billability, leakage, penalty."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from app.domain_packs.contract_margin.schemas import (
    BillabilityDecision,
    BillableCategory,
    BillingGate,
    BillingPrerequisite,
    CommercialRecoveryRecommendation,
    LeakageTrigger,
    PenaltyCondition,
    PenaltyExposureSummary,
    PriorityLevel,
    RateCardEntry,
    ReattendanceRule,
    RecoveryType,
    ScopeBoundaryObject,
    ScopeType,
    ServiceCreditRule,
    SPENRateCard,
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
        approval_threshold: float = 5000.0,
        has_approval: bool = False,
        prior_claims: list[dict] | None = None,
        work_date: date | None = None,
    ) -> BillabilityDecision:
        results: list[RuleResult] = []

        # Rule 1: has valid rate
        matching_rate = self._find_matching_rate(activity, rate_card)
        results.append(
            RuleResult(
                rule_name="has_valid_rate",
                passed=matching_rate is not None,
                message=f"Rate found: {matching_rate.rate}/{matching_rate.unit}"
                if matching_rate
                else "No matching rate",
                severity="error" if not matching_rate else "info",
            )
        )

        # Rule 2: within scope
        in_scope = self._is_within_scope(activity, obligations)
        results.append(
            RuleResult(
                rule_name="within_scope",
                passed=in_scope,
                message="Activity is within contract scope"
                if in_scope
                else "Activity may be out of scope",
                severity="warning" if not in_scope else "info",
            )
        )

        # Rule 3: not excluded
        excluded = self._is_excluded(activity)
        results.append(
            RuleResult(
                rule_name="not_excluded_activity",
                passed=not excluded,
                message="Activity not excluded"
                if not excluded
                else "Activity is on exclusion list",
                severity="error" if excluded else "info",
            )
        )

        # Rule 4: approval threshold check
        if matching_rate is not None and matching_rate.rate > approval_threshold:
            if not has_approval:
                results.append(
                    RuleResult(
                        rule_name="approval_threshold_check",
                        passed=False,
                        message="Exceeds approval threshold without authorization",
                        severity="error",
                    )
                )
            else:
                results.append(
                    RuleResult(
                        rule_name="approval_threshold_check",
                        passed=True,
                        message="Approval obtained for rate exceeding threshold",
                        severity="info",
                    )
                )
        else:
            results.append(
                RuleResult(
                    rule_name="approval_threshold_check",
                    passed=True,
                    message="Rate within approval threshold",
                    severity="info",
                )
            )

        # Rule 5: duplicate claim check
        duplicate_found = False
        if prior_claims:
            activity_lower = activity.lower().replace(" ", "_")
            for claim in prior_claims:
                claim_activity = claim.get("activity", "").lower().replace(" ", "_")
                claim_date = claim.get("date")
                if claim_activity == activity_lower and claim_date is not None:
                    # Compare dates — support both str and date objects
                    if work_date is not None:
                        claim_date_obj = (
                            claim_date
                            if isinstance(claim_date, date)
                            else date.fromisoformat(str(claim_date))
                        )
                        if claim_date_obj == work_date:
                            duplicate_found = True
                            break
        results.append(
            RuleResult(
                rule_name="duplicate_claim_check",
                passed=not duplicate_found,
                message="No duplicate claims"
                if not duplicate_found
                else "Duplicate claim detected",
                severity="error" if duplicate_found else "info",
            )
        )

        # Rule 6: expired rate check
        rate_expired = False
        if (
            matching_rate is not None
            and matching_rate.effective_to is not None
            and work_date is not None
        ):
            if matching_rate.effective_to < work_date:
                rate_expired = True
        results.append(
            RuleResult(
                rule_name="expired_rate_check",
                passed=not rate_expired,
                message="Rate card valid" if not rate_expired else "Rate card expired",
                severity="error" if rate_expired else "info",
            )
        )

        # Rule 7: minimum charge enforcement (does not affect billability, only rate_applied)
        # Handled when building the decision below

        all_passed = all(r.passed for r in results)
        confidence = sum(1 for r in results if r.passed) / max(len(results), 1)

        rate_applied = matching_rate.rate if matching_rate else None

        # Rule 7: minimum charge enforcement — adjust rate_applied if below minimum
        if (
            matching_rate is not None
            and matching_rate.minimum_charge is not None
            and rate_applied is not None
            and rate_applied < matching_rate.minimum_charge
        ):
            rate_applied = matching_rate.minimum_charge

        return BillabilityDecision(
            billable=all_passed,
            confidence=confidence,
            evidence_ids=evidence_ids or [],
            reasons=[r.message for r in results if not r.passed],
            rate_applied=rate_applied,
        )

    def _find_matching_rate(
        self, activity: str, rate_card: list[RateCardEntry]
    ) -> RateCardEntry | None:
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
        penalty_objects = [
            o for o in contract_objects if o.get("control_type") == "penalty_condition"
        ]
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
                delta = work.get("contract_rate", 0) * work.get("escalation_percentage", 0) / 100
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
            if work.get("abortive") is True and not work.get("abortive_claimed"):
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
            if work.get("is_variation") is True and not work.get("variation_order_ref"):
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

        # Rule 10: Time-based rate mismatch — out-of-hours work billed at standard rate
        triggers.extend(self._check_time_based_rate_mismatch(work_history))

        # Rule 11: Material cost pass-through — materials used but not separately billed
        triggers.extend(self._check_material_cost_passthrough(work_history))

        # Rule 12: Subcontractor margin leak — sub cost > billed rate
        triggers.extend(self._check_subcontractor_margin_leak(work_history))

        # Rule 13: Mobilisation not charged — remote site travel not billed
        triggers.extend(self._check_mobilisation_not_charged(work_history))

        # Rule 14: Warranty period rework — rework within warranty billed as new work
        triggers.extend(self._check_warranty_period_rework(work_history))

        return triggers

    # -- new leakage rule methods -------------------------------------------

    def _check_time_based_rate_mismatch(self, work_history: list[dict]) -> list[LeakageTrigger]:
        """Detect work done outside business hours but billed at standard rate."""
        triggers: list[LeakageTrigger] = []
        for work in work_history:
            time_of_day = work.get("time_of_day", "normal")
            if time_of_day in ("overtime", "weekend", "emergency", "out_of_hours"):
                billed_rate = work.get("billed_rate", 0)
                contract_rate = work.get("contract_rate", 0)
                multiplier = work.get("expected_multiplier", 1.5)
                expected_rate = contract_rate * multiplier
                if billed_rate > 0 and contract_rate > 0 and billed_rate <= contract_rate:
                    delta = expected_rate - billed_rate
                    triggers.append(
                        LeakageTrigger(
                            trigger_type="time_rate_mismatch",
                            description=(
                                f"Work '{work.get('activity', 'unknown')}' performed during "
                                f"{time_of_day} but billed at standard rate "
                                f"(£{billed_rate:.2f} vs expected £{expected_rate:.2f})"
                            ),
                            severity="warning",
                            estimated_impact_value=delta * work.get("hours", 1),
                        )
                    )
        return triggers

    def _check_material_cost_passthrough(self, work_history: list[dict]) -> list[LeakageTrigger]:
        """Detect materials used but not separately billed."""
        triggers: list[LeakageTrigger] = []
        for work in work_history:
            material_cost = work.get("material_cost", 0)
            material_billed = work.get("material_billed", False)
            if material_cost and material_cost > 0 and not material_billed:
                triggers.append(
                    LeakageTrigger(
                        trigger_type="material_cost_not_billed",
                        description=(
                            f"Materials costing £{material_cost:.2f} used for "
                            f"'{work.get('activity', 'unknown')}' but not billed to client"
                        ),
                        severity="warning",
                        estimated_impact_value=float(material_cost),
                    )
                )
        return triggers

    def _check_subcontractor_margin_leak(self, work_history: list[dict]) -> list[LeakageTrigger]:
        """Detect when subcontractor cost exceeds billed rate."""
        triggers: list[LeakageTrigger] = []
        for work in work_history:
            sub_cost = work.get("subcontractor_cost")
            billed_rate = work.get("billed_rate")
            if sub_cost is not None and billed_rate is not None and sub_cost > billed_rate:
                delta = sub_cost - billed_rate
                triggers.append(
                    LeakageTrigger(
                        trigger_type="subcontractor_margin_leak",
                        description=(
                            f"Subcontractor cost £{sub_cost:.2f} exceeds billed rate "
                            f"£{billed_rate:.2f} for '{work.get('activity', 'unknown')}' — "
                            f"negative margin of £{delta:.2f}"
                        ),
                        severity="error",
                        estimated_impact_value=delta * work.get("quantity", 1),
                    )
                )
        return triggers

    def _check_mobilisation_not_charged(self, work_history: list[dict]) -> list[LeakageTrigger]:
        """Detect mobilisation/travel to remote site not billed."""
        triggers: list[LeakageTrigger] = []
        for work in work_history:
            if work.get("remote_site") and work.get("mobilisation_cost", 0) > 0:
                if not work.get("mobilisation_billed", False):
                    triggers.append(
                        LeakageTrigger(
                            trigger_type="mobilisation_not_charged",
                            description=(
                                f"Mobilisation cost £{work['mobilisation_cost']:.2f} to "
                                f"remote site for '{work.get('activity', 'unknown')}' not recovered"
                            ),
                            severity="warning",
                            estimated_impact_value=float(work["mobilisation_cost"]),
                        )
                    )
        return triggers

    def _check_warranty_period_rework(self, work_history: list[dict]) -> list[LeakageTrigger]:
        """Detect rework within warranty period billed as new work (should be non-billable)."""
        triggers: list[LeakageTrigger] = []
        for work in work_history:
            if work.get("is_rework") and work.get("within_warranty_period") and work.get("billed"):
                triggers.append(
                    LeakageTrigger(
                        trigger_type="warranty_rework_billed",
                        description=(
                            f"Rework for '{work.get('activity', 'unknown')}' within warranty "
                            f"period billed as new work — should be non-billable"
                        ),
                        severity="error",
                        estimated_impact_value=float(work.get("billed_rate", 0))
                        * work.get("hours", 1),
                    )
                )
        return triggers


class ScopeConflictDetector:
    """Detect scope conflicts between contracted scope and executed work."""

    def detect_conflicts(
        self,
        scope_boundaries: list[ScopeBoundaryObject],
        executed_activities: list[str],
    ) -> list[dict]:
        """Return list of conflict dicts with: activity, conflict_type, severity, description."""
        conflicts: list[dict] = []

        for activity in executed_activities:
            activity_lower = activity.lower().replace(" ", "_")
            matched = False

            for boundary in scope_boundaries:
                boundary_activities = [a.lower().replace(" ", "_") for a in boundary.activities]
                # Check description-based matching too
                desc_lower = boundary.description.lower()

                if activity_lower in boundary_activities or activity_lower in desc_lower:
                    matched = True
                    if boundary.scope_type == ScopeType.out_of_scope:
                        conflicts.append(
                            {
                                "activity": activity,
                                "conflict_type": "out_of_scope",
                                "severity": "error",
                                "description": (
                                    f"Activity '{activity}' is explicitly out of scope: "
                                    f"{boundary.description}"
                                ),
                            }
                        )
                    elif boundary.scope_type == ScopeType.conditional:
                        # Conditional scope — flag if conditions exist (caller must
                        # verify conditions are met externally; we flag as warning)
                        if boundary.conditions:
                            conflicts.append(
                                {
                                    "activity": activity,
                                    "conflict_type": "conditional_unmet",
                                    "severity": "warning",
                                    "description": (
                                        f"Activity '{activity}' is conditionally in scope. "
                                        f"Conditions: {', '.join(boundary.conditions)}"
                                    ),
                                }
                            )
                    # in_scope => no conflict
                    break  # stop checking further boundaries for this activity

            if not matched:
                conflicts.append(
                    {
                        "activity": activity,
                        "conflict_type": "scope_gap",
                        "severity": "warning",
                        "description": (
                            f"Activity '{activity}' not mentioned in any scope boundary"
                        ),
                    }
                )

        return conflicts


class RecoveryRecommendationEngine:
    """Generate commercial recovery recommendations from leakage triggers."""

    # Mapping from trigger_type to (RecoveryType, description_template, priority)
    _TRIGGER_MAP: dict[str, tuple[RecoveryType, str, PriorityLevel]] = {
        "unbilled_completed_work": (
            RecoveryType.backbill,
            "Backbill for unbilled completed work",
            PriorityLevel.high,
        ),
        "rate_below_contract": (
            RecoveryType.rate_adjustment,
            "Adjust billing rate to contracted rate",
            PriorityLevel.medium,
        ),
        "penalty_exposure_unmitigated": (
            RecoveryType.penalty_waiver,
            "Negotiate penalty waiver or mitigation plan",
            PriorityLevel.high,
        ),
        "scope_creep_detected": (
            RecoveryType.change_order,
            "Raise change order for out-of-scope work",
            PriorityLevel.high,
        ),
        "scope_creep_unpriced": (
            RecoveryType.change_order,
            "Raise change order for unpriced scope creep",
            PriorityLevel.high,
        ),
        "missing_daywork_sheet": (
            RecoveryType.backbill,
            "Obtain signed daywork sheet then backbill",
            PriorityLevel.medium,
        ),
        "rate_escalation_missed": (
            RecoveryType.rate_adjustment,
            "Apply contractual rate escalation and adjust invoices",
            PriorityLevel.medium,
        ),
        "abortive_visit_not_claimed": (
            RecoveryType.backbill,
            "Claim abortive visit charge",
            PriorityLevel.low,
        ),
        "variation_work_no_change_order": (
            RecoveryType.change_order,
            "Raise formal variation order for variation work",
            PriorityLevel.high,
        ),
        "permit_cost_not_recovered": (
            RecoveryType.backbill,
            "Pass through permit cost to client",
            PriorityLevel.low,
        ),
    }

    def build_recommendations(
        self,
        leakage_triggers: list[LeakageTrigger],
        contract_objects: list[dict],
        rate_card: list[RateCardEntry],
    ) -> list[CommercialRecoveryRecommendation]:
        """Build recovery recommendations for each leakage trigger."""
        recommendations: list[CommercialRecoveryRecommendation] = []

        # Build a rate lookup for estimating recovery values
        rate_lookup: dict[str, float] = {}
        for rc in rate_card:
            rate_lookup[rc.activity.lower().replace(" ", "_")] = rc.rate

        for trigger in leakage_triggers:
            mapping = self._TRIGGER_MAP.get(trigger.trigger_type)
            if mapping is None:
                continue

            recovery_type, description, priority = mapping

            # Estimate recovery value from the trigger's estimated_impact_value
            # or from the rate card if available
            estimated_value = trigger.estimated_impact_value
            if estimated_value == 0.0 and trigger.estimated_impact:
                try:
                    estimated_value = float(trigger.estimated_impact)
                except (ValueError, TypeError):
                    estimated_value = 0.0

            # Collect clause refs from contract objects if available
            clause_refs: list[str] = list(trigger.clause_refs)

            recommendations.append(
                CommercialRecoveryRecommendation(
                    recommendation_type=recovery_type,
                    description=f"{description}: {trigger.description}",
                    estimated_recovery_value=estimated_value,
                    evidence_clause_refs=clause_refs,
                    priority=priority,
                    confidence=0.8 if estimated_value > 0 else 0.5,
                )
            )

        return recommendations


class PenaltyExposureAnalyzer:
    """Analyze penalty exposure across SLA performance data."""

    def analyze(
        self,
        penalty_conditions: list[PenaltyCondition],
        sla_performance: dict,
        monthly_invoice_value: float = 0.0,
    ) -> PenaltyExposureSummary:
        """Analyze penalty exposure.

        Parameters
        ----------
        penalty_conditions:
            Contractual penalty conditions.
        sla_performance:
            Dict mapping metric names to actual performance values
            or a dict with keys like ``breach_detected``, ``metric_value``, etc.
        monthly_invoice_value:
            Monthly invoice total, used for percentage-based penalties.

        Returns
        -------
        PenaltyExposureSummary
        """
        breach_details: list[dict] = []
        mitigation_actions: list[str] = []
        total_exposure = 0.0
        active_breaches = 0

        for condition in penalty_conditions:
            trigger_key = condition.trigger.lower().replace(" ", "_") if condition.trigger else ""

            # Determine whether the condition is breached
            breached = False
            if trigger_key and trigger_key in sla_performance:
                # If sla_performance maps trigger to a bool
                val = sla_performance[trigger_key]
                if isinstance(val, bool):
                    breached = val
                elif isinstance(val, (int, float)):
                    # Treat numeric values: breach if below threshold (generic heuristic)
                    breached = val < 1.0  # assume 1.0 = "met"
            elif sla_performance.get("breach_detected"):
                breached = True

            if not breached:
                continue

            # Check grace period
            grace_days = condition.grace_period_days or 0
            remaining_grace = sla_performance.get("days_since_breach", grace_days + 1)
            within_grace = remaining_grace <= grace_days and grace_days > 0

            if within_grace:
                mitigation_actions.append(
                    f"Condition '{condition.description}' breached but within "
                    f"{grace_days}-day grace period — remediate immediately"
                )
                breach_details.append(
                    {
                        "clause_id": condition.clause_id,
                        "description": condition.description,
                        "breached": True,
                        "within_grace_period": True,
                        "financial_exposure": 0.0,
                    }
                )
                continue

            # Calculate financial exposure
            exposure = 0.0
            if condition.penalty_type == "percentage":
                try:
                    pct = float(condition.penalty_amount.replace("%", "").strip())
                    exposure = monthly_invoice_value * (pct / 100.0)
                except (ValueError, AttributeError):
                    exposure = 0.0
            elif condition.penalty_type == "fixed":
                try:
                    exposure = float(
                        condition.penalty_amount.replace("£", "")
                        .replace("$", "")
                        .replace(",", "")
                        .strip()
                    )
                except (ValueError, AttributeError):
                    exposure = 0.0
            elif condition.penalty_type == "per_breach":
                try:
                    per_breach = float(
                        condition.penalty_amount.replace("£", "")
                        .replace("$", "")
                        .replace(",", "")
                        .strip()
                    )
                    breach_count = sla_performance.get("breach_count", 1)
                    exposure = per_breach * breach_count
                except (ValueError, AttributeError):
                    exposure = 0.0

            # Apply cap
            if condition.cap is not None and condition.cap > 0 and exposure > condition.cap:
                exposure = condition.cap

            total_exposure += exposure
            active_breaches += 1

            breach_details.append(
                {
                    "clause_id": condition.clause_id,
                    "description": condition.description,
                    "breached": True,
                    "within_grace_period": False,
                    "financial_exposure": round(exposure, 2),
                    "penalty_type": condition.penalty_type,
                }
            )

            mitigation_actions.append(
                f"Remediate '{condition.description}' — exposure £{exposure:.2f}"
            )

        return PenaltyExposureSummary(
            total_penalties=len(penalty_conditions),
            active_breaches=active_breaches,
            estimated_financial_exposure=round(total_exposure, 2),
            breach_details=breach_details,
            mitigation_actions=mitigation_actions,
        )


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
            results.append(
                RuleResult(
                    rule_name="has_matching_rate",
                    passed=False,
                    message=f"No SPEN rate found for activity '{activity}' in category '{work_category}'",
                    severity="error",
                )
            )
            billable = False
        else:
            applied_rate = matching_rate.base_rate
            results.append(
                RuleResult(
                    rule_name="has_matching_rate",
                    passed=True,
                    message=(
                        f"Rate matched: {matching_rate.activity_code} — "
                        f"£{matching_rate.base_rate:.2f}/{matching_rate.unit}"
                    ),
                    severity="info",
                )
            )

        # ------------------------------------------------------------------
        # Rule 2: All billing gates satisfied
        # ------------------------------------------------------------------
        unsatisfied_gates = [g for g in billing_gates if not g.satisfied]
        gates_ok = len(unsatisfied_gates) == 0
        if not gates_ok:
            gate_names = ", ".join(g.gate_type.value for g in unsatisfied_gates)
            results.append(
                RuleResult(
                    rule_name="billing_gates_satisfied",
                    passed=False,
                    message=f"Unsatisfied billing gates: {gate_names}",
                    severity="error",
                )
            )
            billable = False
        else:
            results.append(
                RuleResult(
                    rule_name="billing_gates_satisfied",
                    passed=True,
                    message="All billing gates satisfied",
                    severity="info",
                )
            )

        # ------------------------------------------------------------------
        # Rule 3: Re-attendance check
        # ------------------------------------------------------------------
        if is_reattendance:
            reat_rule = self._find_reattendance_rule(reattendance_trigger)
            if reat_rule is None:
                results.append(
                    RuleResult(
                        rule_name="reattendance_check",
                        passed=False,
                        message=f"Unknown re-attendance trigger: '{reattendance_trigger}'",
                        severity="warning",
                    )
                )
                billable = False
            elif not reat_rule.billable:
                results.append(
                    RuleResult(
                        rule_name="reattendance_check",
                        passed=False,
                        message=f"Re-attendance non-billable: {reat_rule.description}",
                        severity="error",
                    )
                )
                billable = False
                applied_rate = 0.0
            else:
                if applied_rate is not None:
                    applied_rate *= reat_rule.rate_modifier
                results.append(
                    RuleResult(
                        rule_name="reattendance_check",
                        passed=True,
                        message=f"Re-attendance billable: {reat_rule.description}",
                        severity="info",
                    )
                )
        else:
            results.append(
                RuleResult(
                    rule_name="reattendance_check",
                    passed=True,
                    message="Not a re-attendance",
                    severity="info",
                )
            )

        # ------------------------------------------------------------------
        # Rule 4: Time-of-day multiplier
        # ------------------------------------------------------------------
        if matching_rate is not None and applied_rate is not None and applied_rate > 0:
            multiplier = self._get_time_multiplier(time_of_day, matching_rate)
            applied_rate *= multiplier
            results.append(
                RuleResult(
                    rule_name="time_of_day_modifier",
                    passed=True,
                    message=(
                        f"Time-of-day modifier applied: {time_of_day} -> {multiplier}x "
                        f"(effective rate £{applied_rate:.2f})"
                    ),
                    severity="info",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="time_of_day_modifier",
                    passed=True,
                    message="No time-of-day modifier applicable",
                    severity="info",
                )
            )

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
                results.append(
                    RuleResult(
                        rule_name="approval_threshold",
                        passed=False,
                        message=(
                            f"Effective rate £{applied_rate:.2f} exceeds approval threshold "
                            f"£{matching_rate.requires_approval_above:.2f} — prior approval required"
                        ),
                        severity="error",
                    )
                )
                billable = False
            else:
                results.append(
                    RuleResult(
                        rule_name="approval_threshold",
                        passed=True,
                        message="Prior approval obtained for value above threshold",
                        severity="info",
                    )
                )
        else:
            results.append(
                RuleResult(
                    rule_name="approval_threshold",
                    passed=True,
                    message="No approval threshold applicable",
                    severity="info",
                )
            )

        # ------------------------------------------------------------------
        # Build decision
        # ------------------------------------------------------------------
        confidence = sum(1 for r in results if r.passed) / max(len(results), 1)

        return BillabilityDecision(
            billable=billable,
            confidence=confidence,
            reasons=[r.message for r in results if not r.passed],
            rate_applied=applied_rate,
            category=BillableCategory.daywork
            if time_of_day == "normal"
            else BillableCategory.emergency_callout,
            rule_results=[
                {"rule": r.rule_name, "passed": r.passed, "message": r.message} for r in results
            ],
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
                results.append(
                    {
                        "sla_metric": rule.sla_metric,
                        "threshold": rule.threshold_value,
                        "actual": None,
                        "breached": False,
                        "credit_percentage": 0.0,
                        "credit_value": 0.0,
                        "capped": False,
                        "note": "No performance data available for this metric",
                    }
                )
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

            results.append(
                {
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
                }
            )

        return results
