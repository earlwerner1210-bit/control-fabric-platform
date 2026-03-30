"""
Billability rule engine for the contract margin domain pack.

Evaluates whether a work activity is billable under a given contract by
running a sequence of deterministic rules against the rate card, obligations,
scope, evidence, and prior claims.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.domain_packs.contract_margin.schemas.contract import (
    BillabilityDecision,
    BillableCategory,
    Obligation,
    RateCardEntry,
)


class BillabilityRuleEngine:
    """Run deterministic billability rules and produce a BillabilityDecision."""

    def evaluate(
        self,
        activity: dict[str, Any],
        rate_card: list[RateCardEntry],
        obligations: list[Obligation],
        prior_claims: list[dict[str, Any]] | None = None,
        work_date: date | None = None,
        has_approval: bool = False,
        approval_threshold: float = 0.0,
    ) -> BillabilityDecision:
        """Evaluate all billability rules for a single activity.

        Parameters
        ----------
        activity:
            Dict with at least ``name`` (str) and optionally ``category``,
            ``evidence``, ``scope``, ``value``, ``quantity``, ``unit``.
        rate_card:
            Applicable rate card entries from the parsed contract.
        obligations:
            Contract obligations that may affect billability.
        prior_claims:
            Previously submitted claims (list of dicts with ``activity``,
            ``date``, ``reference``).
        work_date:
            Date the work was executed.  Defaults to today.
        has_approval:
            Whether the work has been approved / authorised.
        approval_threshold:
            Value above which explicit approval is required.
        """
        work_date = work_date or date.today()
        prior_claims = prior_claims or []

        rule_results: dict[str, bool] = {}
        reasons: list[str] = []
        evidence_refs: list[str] = []

        activity_name = activity.get("name", "")
        activity_value = float(activity.get("value", 0.0))
        activity_evidence = activity.get("evidence", [])
        activity_scope = activity.get("scope", "in_scope")
        activity_category = activity.get("category", "standard")
        activity_quantity = float(activity.get("quantity", 1))

        # --- Rule 1: Rate card match ---
        matched_entry, rc_passed, rc_reason = self._rule_rate_card_match(activity_name, rate_card)
        rule_results["rate_card_match"] = rc_passed
        if not rc_passed:
            reasons.append(rc_reason)

        # --- Rule 2: Obligation check ---
        ob_passed, ob_reason = self._rule_obligation_check(activity_name, obligations)
        rule_results["obligation_check"] = ob_passed
        if not ob_passed:
            reasons.append(ob_reason)

        # --- Rule 3: Evidence check ---
        ev_passed, ev_reason, ev_refs = self._rule_evidence_check(
            activity_name, activity_evidence, obligations
        )
        rule_results["evidence_check"] = ev_passed
        evidence_refs.extend(ev_refs)
        if not ev_passed:
            reasons.append(ev_reason)

        # --- Rule 4: Scope check ---
        sc_passed, sc_reason = self._rule_scope_check(activity_scope)
        rule_results["scope_check"] = sc_passed
        if not sc_passed:
            reasons.append(sc_reason)

        # --- Rule 5: Approval threshold check ---
        ap_passed, ap_reason = self._rule_approval_threshold_check(
            activity_value, has_approval, approval_threshold
        )
        rule_results["approval_threshold_check"] = ap_passed
        if not ap_passed:
            reasons.append(ap_reason)

        # --- Rule 6: Duplicate claim check ---
        dc_passed, dc_reason = self._rule_duplicate_claim_check(
            activity_name, work_date, prior_claims
        )
        rule_results["duplicate_claim_check"] = dc_passed
        if not dc_passed:
            reasons.append(dc_reason)

        # --- Rule 7: Expired rate check ---
        er_passed, er_reason = self._rule_expired_rate_check(matched_entry, work_date)
        rule_results["expired_rate_check"] = er_passed
        if not er_passed:
            reasons.append(er_reason)

        # --- Rule 8: Minimum charge enforcement ---
        mc_passed, mc_reason = self._rule_minimum_charge_enforcement(
            matched_entry, activity_quantity
        )
        rule_results["minimum_charge_enforcement"] = mc_passed
        if not mc_passed:
            reasons.append(mc_reason)

        # Aggregate decision
        all_passed = all(rule_results.values())
        critical_rules = {"rate_card_match", "scope_check", "expired_rate_check"}
        critical_passed = all(rule_results.get(r, True) for r in critical_rules)

        billable = all_passed
        rate_applied = 0.0
        category = BillableCategory.standard

        if matched_entry is not None:
            try:
                category = BillableCategory(activity_category)
            except ValueError:
                category = BillableCategory.standard
            rate_applied = matched_entry.effective_rate(category.value)

        if not critical_passed:
            billable = False
            rate_applied = 0.0

        if billable:
            reasons.insert(
                0,
                f"Activity '{activity_name}' is billable at {rate_applied} per {matched_entry.unit if matched_entry else 'unit'}",
            )
        else:
            reasons.insert(0, f"Activity '{activity_name}' is NOT billable")

        passed_count = sum(1 for v in rule_results.values() if v)
        total_count = len(rule_results)
        confidence = round(passed_count / max(total_count, 1), 2)

        return BillabilityDecision(
            billable=billable,
            category=category,
            rate_applied=rate_applied,
            reasons=reasons,
            confidence=confidence,
            rule_results=rule_results,
            evidence_refs=evidence_refs,
        )

    # ------------------------------------------------------------------
    # Individual rules
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_rate_card_match(
        activity_name: str,
        rate_card: list[RateCardEntry],
    ) -> tuple[RateCardEntry | None, bool, str]:
        """Check that the activity matches an entry in the rate card."""
        activity_lower = activity_name.lower().strip()
        for entry in rate_card:
            entry_lower = entry.activity.lower().strip()
            if activity_lower == entry_lower:
                return entry, True, "Rate card match found (exact)"
            if activity_lower in entry_lower or entry_lower in activity_lower:
                return entry, True, "Rate card match found (partial)"
        return None, False, f"No rate card entry found for activity '{activity_name}'"

    @staticmethod
    def _rule_obligation_check(
        activity_name: str,
        obligations: list[Obligation],
    ) -> tuple[bool, str]:
        """Check that performing this activity does not violate an obligation."""
        activity_lower = activity_name.lower()
        for ob in obligations:
            desc_lower = ob.description.lower()
            if "prohibited" in desc_lower and activity_lower in desc_lower:
                return False, f"Activity conflicts with obligation: {ob.description[:100]}"
            if "not permitted" in desc_lower and activity_lower in desc_lower:
                return False, f"Activity not permitted per obligation: {ob.description[:100]}"
        return True, "No conflicting obligations found"

    @staticmethod
    def _rule_evidence_check(
        activity_name: str,
        provided_evidence: list[str],
        obligations: list[Obligation],
    ) -> tuple[bool, str, list[str]]:
        """Check that all required evidence has been provided."""
        required: set[str] = set()
        activity_lower = activity_name.lower()
        for ob in obligations:
            if activity_lower in ob.description.lower() or ob.owner == "provider":
                required.update(ob.evidence_required)

        if not required:
            return True, "No specific evidence requirements found", list(provided_evidence)

        provided_set = {e.lower().strip() for e in provided_evidence}
        required_lower = {r.lower().strip() for r in required}
        missing = required_lower - provided_set
        if missing:
            return (
                False,
                f"Missing required evidence: {', '.join(sorted(missing))}",
                list(provided_evidence),
            )
        return True, "All required evidence provided", list(provided_evidence)

    @staticmethod
    def _rule_scope_check(activity_scope: str) -> tuple[bool, str]:
        """Check that the activity is within scope."""
        scope_lower = activity_scope.lower().strip()
        if scope_lower == "out_of_scope":
            return False, "Activity is out of scope per contract boundaries"
        if scope_lower == "conditional":
            return False, "Activity has conditional scope — requires manual review"
        if scope_lower == "in_scope":
            return True, "Activity is within contract scope"
        return True, f"Scope status '{activity_scope}' treated as in-scope by default"

    @staticmethod
    def _rule_approval_threshold_check(
        activity_value: float,
        has_approval: bool,
        threshold: float,
    ) -> tuple[bool, str]:
        """Check that work above the threshold has approval."""
        if threshold <= 0:
            return True, "No approval threshold configured"
        if activity_value <= threshold:
            return True, f"Activity value {activity_value} is below threshold {threshold}"
        if has_approval:
            return (
                True,
                f"Activity value {activity_value} exceeds threshold but approval is present",
            )
        return (
            False,
            f"Activity value {activity_value} exceeds threshold {threshold} and no approval found",
        )

    @staticmethod
    def _rule_duplicate_claim_check(
        activity_name: str,
        work_date: date,
        prior_claims: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        """Check that this activity has not already been claimed."""
        activity_lower = activity_name.lower().strip()
        for claim in prior_claims:
            claim_activity = str(claim.get("activity", "")).lower().strip()
            claim_date = claim.get("date")
            if claim_activity == activity_lower:
                if isinstance(claim_date, date) and claim_date == work_date:
                    ref = claim.get("reference", "unknown")
                    return (
                        False,
                        f"Duplicate claim detected — already claimed under reference {ref}",
                    )
                if isinstance(claim_date, str):
                    try:
                        parsed = datetime.strptime(claim_date, "%Y-%m-%d").date()
                        if parsed == work_date:
                            ref = claim.get("reference", "unknown")
                            return (
                                False,
                                f"Duplicate claim detected — already claimed under reference {ref}",
                            )
                    except ValueError:
                        pass
        return True, "No duplicate claims detected"

    @staticmethod
    def _rule_expired_rate_check(
        matched_entry: RateCardEntry | None,
        work_date: date,
    ) -> tuple[bool, str]:
        """Check that the matched rate card entry has not expired."""
        if matched_entry is None:
            return True, "No rate card entry to check expiry against"
        if not matched_entry.is_active(work_date):
            return (
                False,
                f"Rate card entry for '{matched_entry.activity}' is not active on {work_date.isoformat()}",
            )
        return (
            True,
            f"Rate card entry for '{matched_entry.activity}' is active on {work_date.isoformat()}",
        )

    @staticmethod
    def _rule_minimum_charge_enforcement(
        matched_entry: RateCardEntry | None,
        quantity: float,
    ) -> tuple[bool, str]:
        """Ensure that the minimum billable quantity is met.

        Convention: if rate > 0 the minimum billable quantity is 1 unit.
        For time-based rates (hour/day) a fractional quantity >= 0.25 is
        accepted.
        """
        if matched_entry is None:
            return True, "No rate card entry — minimum charge rule skipped"
        if matched_entry.rate <= 0:
            return True, "Zero-rate entry — minimum charge rule not applicable"
        unit_lower = matched_entry.unit.lower()
        if unit_lower in ("hour", "hours", "day", "days"):
            if quantity < 0.25:
                return (
                    False,
                    f"Quantity {quantity} below minimum 0.25 for time-based unit '{matched_entry.unit}'",
                )
        else:
            if quantity < 1:
                return (
                    False,
                    f"Quantity {quantity} below minimum 1 for unit '{matched_entry.unit}'",
                )
        return True, f"Quantity {quantity} meets minimum charge for unit '{matched_entry.unit}'"
