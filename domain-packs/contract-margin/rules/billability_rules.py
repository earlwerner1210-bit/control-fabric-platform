"""Billability rule engine for evaluating whether work events are billable under a contract.

Each rule evaluates a specific aspect of billability and returns a RuleResult.
The engine aggregates rule results into a BillabilityDecision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas.contract_schemas import (
    BillabilityDecision,
    ParsedContract,
    RuleResult,
)
from ..taxonomy.contract_taxonomy import BillableCategory


@dataclass
class WorkEvent:
    """Represents a work event to evaluate for billability."""

    event_id: str
    description: str
    activity_type: str
    hours: float = 0.0
    role: str = ""
    date: str | None = None
    has_approval: bool = False
    sla_met: bool = True
    amount: float | None = None


class BillabilityRuleEngine:
    """Evaluates whether a work event is billable under a given contract.

    Runs a set of deterministic rules and aggregates the results into a
    BillabilityDecision with a confidence score derived from the ratio
    of passing rules.
    """

    def evaluate(
        self,
        event: WorkEvent,
        contract: ParsedContract,
    ) -> BillabilityDecision:
        """Evaluate all billability rules for an event against a contract.

        Args:
            event: The work event to evaluate.
            contract: The parsed contract containing clauses, rates, and SLA entries.

        Returns:
            A BillabilityDecision with overall billability, confidence, and supporting evidence.
        """
        rules = [
            self._has_valid_rate(event, contract),
            self._within_scope(event, contract),
            self._meets_sla_threshold(event, contract),
            self._has_approval(event, contract),
            self._not_excluded_activity(event, contract),
        ]

        passed_count = sum(1 for r in rules if r.passed)
        total = len(rules)
        critical_failures = [r for r in rules if not r.passed and r.severity == "critical"]

        # If any critical rule fails, event is not billable
        billable = len(critical_failures) == 0 and passed_count >= (total - 1)

        confidence = passed_count / total if total > 0 else 0.0
        if critical_failures:
            confidence = min(confidence, 0.3)

        reasons = [r.message for r in rules if not r.passed]
        evidence_ids = [c.clause_id for c in contract.clauses if c.clause_type.is_financial]

        # Find applicable rate
        applicable_rate = self._find_applicable_rate(event, contract)

        return BillabilityDecision(
            billable=billable,
            confidence=round(confidence, 2),
            evidence_ids=evidence_ids,
            reasons=reasons,
            rule_results=rules,
            category=contract.billing_category,
            applicable_rate=applicable_rate,
        )

    def _has_valid_rate(self, event: WorkEvent, contract: ParsedContract) -> RuleResult:
        """Check that a valid rate exists for the event's role or activity."""
        if not contract.rate_card:
            # Fixed-price or milestone contracts may not need a rate card
            if contract.billing_category in (
                BillableCategory.fixed_price,
                BillableCategory.milestone,
            ):
                return RuleResult(
                    rule_name="has_valid_rate",
                    passed=True,
                    message="Fixed-price/milestone contract; rate card not required.",
                    severity="info",
                )
            return RuleResult(
                rule_name="has_valid_rate",
                passed=False,
                message="No rate card found in contract.",
                severity="critical",
            )

        role_lower = event.role.lower()
        for entry in contract.rate_card:
            if role_lower in entry.role_or_item.lower() or entry.role_or_item.lower() in role_lower:
                return RuleResult(
                    rule_name="has_valid_rate",
                    passed=True,
                    message=f"Valid rate found: {entry.role_or_item} at {entry.currency} {entry.rate}/{entry.rate_unit}.",
                    severity="info",
                )

        return RuleResult(
            rule_name="has_valid_rate",
            passed=False,
            message=f"No matching rate card entry for role '{event.role}'.",
            severity="critical",
        )

    def _within_scope(self, event: WorkEvent, contract: ParsedContract) -> RuleResult:
        """Check that the event's activity falls within the contract scope."""
        scope_clauses = [c for c in contract.clauses if c.clause_type.value == "scope"]
        if not scope_clauses:
            return RuleResult(
                rule_name="within_scope",
                passed=True,
                message="No explicit scope clauses found; assuming in-scope.",
                severity="warning",
            )

        activity_lower = event.activity_type.lower()
        description_lower = event.description.lower()

        for clause in scope_clauses:
            clause_lower = clause.text.lower()
            # Check for explicit out-of-scope mentions
            if re.search(r"out\s+of\s+scope", clause_lower) and (
                activity_lower in clause_lower or description_lower in clause_lower
            ):
                return RuleResult(
                    rule_name="within_scope",
                    passed=False,
                    message=f"Activity '{event.activity_type}' explicitly listed as out of scope in {clause.clause_id}.",
                    severity="critical",
                )

            # Check for in-scope match
            if activity_lower in clause_lower or description_lower in clause_lower:
                return RuleResult(
                    rule_name="within_scope",
                    passed=True,
                    message=f"Activity matches scope definition in {clause.clause_id}.",
                    severity="info",
                )

        return RuleResult(
            rule_name="within_scope",
            passed=True,
            message="Activity not explicitly excluded from scope.",
            severity="info",
        )

    def _meets_sla_threshold(self, event: WorkEvent, contract: ParsedContract) -> RuleResult:
        """Check that any applicable SLA thresholds are met for the event."""
        if not contract.sla_entries:
            return RuleResult(
                rule_name="meets_sla_threshold",
                passed=True,
                message="No SLA entries in contract; SLA check not applicable.",
                severity="info",
            )

        if not event.sla_met:
            return RuleResult(
                rule_name="meets_sla_threshold",
                passed=False,
                message="SLA threshold not met for this event. Billing may be contested.",
                severity="warning",
            )

        return RuleResult(
            rule_name="meets_sla_threshold",
            passed=True,
            message="SLA thresholds met.",
            severity="info",
        )

    def _has_approval(self, event: WorkEvent, contract: ParsedContract) -> RuleResult:
        """Check whether the event has required pre-approval."""
        # Find billable events that require approval
        requires_approval = False
        for be in contract.billable_events:
            if be.requires_approval:
                activity_lower = event.activity_type.lower()
                if activity_lower in be.description.lower():
                    requires_approval = True
                    break

        if not requires_approval:
            return RuleResult(
                rule_name="has_approval",
                passed=True,
                message="No pre-approval required for this activity.",
                severity="info",
            )

        if event.has_approval:
            return RuleResult(
                rule_name="has_approval",
                passed=True,
                message="Required pre-approval is present.",
                severity="info",
            )

        return RuleResult(
            rule_name="has_approval",
            passed=False,
            message="Activity requires pre-approval, but no approval found.",
            severity="critical",
        )

    def _not_excluded_activity(self, event: WorkEvent, contract: ParsedContract) -> RuleResult:
        """Check that the event's activity is not explicitly excluded from billing."""
        activity_lower = event.activity_type.lower()
        description_lower = event.description.lower()

        for be in contract.billable_events:
            for exclusion in be.excluded_activities:
                excl_lower = exclusion.lower()
                if activity_lower in excl_lower or description_lower in excl_lower:
                    return RuleResult(
                        rule_name="not_excluded_activity",
                        passed=False,
                        message=f"Activity '{event.activity_type}' is explicitly excluded from billing.",
                        severity="critical",
                    )

        return RuleResult(
            rule_name="not_excluded_activity",
            passed=True,
            message="Activity is not excluded from billing.",
            severity="info",
        )

    def _find_applicable_rate(self, event: WorkEvent, contract: ParsedContract) -> float | None:
        """Find the applicable rate for the event from the contract rate card."""
        role_lower = event.role.lower()
        for entry in contract.rate_card:
            if role_lower in entry.role_or_item.lower() or entry.role_or_item.lower() in role_lower:
                return entry.rate
        return None
