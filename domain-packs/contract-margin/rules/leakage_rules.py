"""Leakage rule engine for detecting margin leakage in telecom contracts.

Evaluates contract data and work history to identify instances where margin
is being lost due to unbilled work, rate erosion, scope creep, missing change
orders, or unmitigated penalty exposure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from ..schemas.contract_schemas import (
    LeakageDriver,
    MarginLeakageDiagnosis,
    ParsedContract,
    PenaltyCondition,
    RecoveryRecommendation,
)


@dataclass
class WorkHistoryEntry:
    """A record of work performed against a contract."""

    entry_id: str
    description: str
    role: str
    hours: float
    actual_rate: float
    date: str
    billed: bool = False
    change_order_ref: Optional[str] = None
    in_original_scope: bool = True


@dataclass
class LeakageTrigger:
    """A single identified instance of margin leakage."""

    driver: LeakageDriver
    description: str
    estimated_impact: float = 0.0
    currency: str = "USD"
    evidence_ids: list[str] = field(default_factory=list)
    severity: str = "medium"


class LeakageRuleEngine:
    """Detects margin leakage by comparing contract terms to actual work history.

    Each rule method examines a specific leakage vector and returns any
    triggered findings.
    """

    def evaluate(
        self,
        contract: ParsedContract,
        work_history: list[WorkHistoryEntry],
    ) -> list[LeakageTrigger]:
        """Run all leakage detection rules and return triggered findings.

        Args:
            contract: The parsed contract with rates, scope, and penalties.
            work_history: List of work history entries to check against.

        Returns:
            A list of LeakageTrigger instances, one per detected leakage.
        """
        triggers: list[LeakageTrigger] = []
        triggers.extend(self._unbilled_completed_work(contract, work_history))
        triggers.extend(self._rate_below_contract(contract, work_history))
        triggers.extend(self._scope_creep_detected(contract, work_history))
        triggers.extend(self._missing_change_order(contract, work_history))
        triggers.extend(self._penalty_exposure_unmitigated(contract))
        return triggers

    def diagnose(
        self,
        contract: ParsedContract,
        work_history: list[WorkHistoryEntry],
    ) -> MarginLeakageDiagnosis:
        """Produce a full margin leakage diagnosis including recovery recommendations.

        Args:
            contract: The parsed contract.
            work_history: Work history entries.

        Returns:
            A MarginLeakageDiagnosis with verdict, drivers, and recommendations.
        """
        triggers = self.evaluate(contract, work_history)

        drivers = list({t.driver for t in triggers})
        total_leakage = sum(t.estimated_impact for t in triggers)
        evidence_ids = []
        for t in triggers:
            evidence_ids.extend(t.evidence_ids)

        # Determine verdict
        if not triggers:
            verdict = "healthy"
        elif total_leakage < 5000:
            verdict = "at_risk"
        elif total_leakage < 50000:
            verdict = "leaking"
        else:
            verdict = "critical"

        recommendations = self._generate_recommendations(triggers)

        summary_parts = []
        if triggers:
            summary_parts.append(f"Identified {len(triggers)} leakage trigger(s) across {len(drivers)} driver(s).")
            summary_parts.append(f"Estimated total leakage: {contract.currency} {total_leakage:,.2f}.")
            if recommendations:
                summary_parts.append(f"Generated {len(recommendations)} recovery recommendation(s).")
        else:
            summary_parts.append("No margin leakage detected. Contract performance is healthy.")

        return MarginLeakageDiagnosis(
            verdict=verdict,
            leakage_drivers=drivers,
            recovery_recommendations=recommendations,
            evidence_ids=list(set(evidence_ids)),
            executive_summary=" ".join(summary_parts),
            total_estimated_leakage=total_leakage if total_leakage > 0 else None,
            currency=contract.currency,
        )

    def _unbilled_completed_work(
        self,
        contract: ParsedContract,
        work_history: list[WorkHistoryEntry],
    ) -> list[LeakageTrigger]:
        """Detect completed work that has not been billed."""
        triggers: list[LeakageTrigger] = []
        unbilled_entries = [e for e in work_history if not e.billed]
        if not unbilled_entries:
            return triggers

        total_unbilled_hours = sum(e.hours for e in unbilled_entries)
        total_unbilled_value = sum(e.hours * e.actual_rate for e in unbilled_entries)

        triggers.append(
            LeakageTrigger(
                driver=LeakageDriver.unbilled_work,
                description=(
                    f"{len(unbilled_entries)} work entries ({total_unbilled_hours:.1f} hours) "
                    f"completed but not billed. Estimated value: {contract.currency} {total_unbilled_value:,.2f}."
                ),
                estimated_impact=total_unbilled_value,
                currency=contract.currency,
                evidence_ids=[e.entry_id for e in unbilled_entries],
                severity="critical" if total_unbilled_value > 10000 else "high",
            )
        )
        return triggers

    def _rate_below_contract(
        self,
        contract: ParsedContract,
        work_history: list[WorkHistoryEntry],
    ) -> list[LeakageTrigger]:
        """Detect work billed at rates below the contracted rate card."""
        triggers: list[LeakageTrigger] = []
        if not contract.rate_card:
            return triggers

        # Build a role-to-rate lookup
        rate_lookup: dict[str, float] = {}
        for rc in contract.rate_card:
            rate_lookup[rc.role_or_item.lower()] = rc.rate

        for entry in work_history:
            role_lower = entry.role.lower()
            contracted_rate: Optional[float] = None
            for role_key, rate in rate_lookup.items():
                if role_lower in role_key or role_key in role_lower:
                    contracted_rate = rate
                    break

            if contracted_rate is not None and entry.actual_rate < contracted_rate:
                delta = (contracted_rate - entry.actual_rate) * entry.hours
                triggers.append(
                    LeakageTrigger(
                        driver=LeakageDriver.rate_erosion,
                        description=(
                            f"Entry '{entry.entry_id}': role '{entry.role}' billed at "
                            f"{entry.actual_rate}/hr vs contracted {contracted_rate}/hr. "
                            f"Delta: {contract.currency} {delta:,.2f}."
                        ),
                        estimated_impact=delta,
                        currency=contract.currency,
                        evidence_ids=[entry.entry_id],
                        severity="high" if delta > 1000 else "medium",
                    )
                )
        return triggers

    def _scope_creep_detected(
        self,
        contract: ParsedContract,
        work_history: list[WorkHistoryEntry],
    ) -> list[LeakageTrigger]:
        """Detect work performed outside the original contract scope without a change order."""
        triggers: list[LeakageTrigger] = []
        out_of_scope = [
            e for e in work_history
            if not e.in_original_scope and not e.change_order_ref
        ]
        if not out_of_scope:
            return triggers

        total_hours = sum(e.hours for e in out_of_scope)
        total_value = sum(e.hours * e.actual_rate for e in out_of_scope)

        triggers.append(
            LeakageTrigger(
                driver=LeakageDriver.scope_creep,
                description=(
                    f"{len(out_of_scope)} work entries ({total_hours:.1f} hours) performed "
                    f"outside original scope without change orders. "
                    f"Estimated unrecoverable cost: {contract.currency} {total_value:,.2f}."
                ),
                estimated_impact=total_value,
                currency=contract.currency,
                evidence_ids=[e.entry_id for e in out_of_scope],
                severity="critical" if total_value > 20000 else "high",
            )
        )
        return triggers

    def _missing_change_order(
        self,
        contract: ParsedContract,
        work_history: list[WorkHistoryEntry],
    ) -> list[LeakageTrigger]:
        """Detect out-of-scope work that lacks a formal change order."""
        triggers: list[LeakageTrigger] = []
        missing_co = [
            e for e in work_history
            if not e.in_original_scope and e.change_order_ref is None
        ]
        if not missing_co:
            return triggers

        # Only add if not already covered by scope_creep
        for entry in missing_co:
            triggers.append(
                LeakageTrigger(
                    driver=LeakageDriver.missing_change_order,
                    description=(
                        f"Work entry '{entry.entry_id}' is out of scope but has no "
                        f"change order reference. Risk of dispute or non-payment."
                    ),
                    estimated_impact=entry.hours * entry.actual_rate,
                    currency=contract.currency,
                    evidence_ids=[entry.entry_id],
                    severity="high",
                )
            )
        return triggers

    def _penalty_exposure_unmitigated(
        self,
        contract: ParsedContract,
    ) -> list[LeakageTrigger]:
        """Flag penalties with no mitigation strategy or capped amount."""
        triggers: list[LeakageTrigger] = []
        for penalty in contract.penalties:
            if penalty.cap is None and penalty.amount is None and penalty.amount_formula:
                triggers.append(
                    LeakageTrigger(
                        driver=LeakageDriver.penalty_exposure,
                        description=(
                            f"Penalty '{penalty.penalty_id}' has formula-based calculation "
                            f"('{penalty.amount_formula}') with no cap. Exposure is unbounded."
                        ),
                        estimated_impact=0.0,
                        currency=penalty.currency,
                        evidence_ids=penalty.linked_clause_ids,
                        severity="critical",
                    )
                )
            elif penalty.amount and penalty.amount > 50000:
                triggers.append(
                    LeakageTrigger(
                        driver=LeakageDriver.penalty_exposure,
                        description=(
                            f"Penalty '{penalty.penalty_id}' has high fixed amount: "
                            f"{penalty.currency} {penalty.amount:,.2f}."
                        ),
                        estimated_impact=penalty.amount,
                        currency=penalty.currency,
                        evidence_ids=penalty.linked_clause_ids,
                        severity="high",
                    )
                )
        return triggers

    def _generate_recommendations(
        self,
        triggers: list[LeakageTrigger],
    ) -> list[RecoveryRecommendation]:
        """Generate recovery recommendations based on identified leakage triggers."""
        recommendations: list[RecoveryRecommendation] = []

        driver_actions: dict[LeakageDriver, tuple[str, str]] = {
            LeakageDriver.unbilled_work: (
                "Submit retrospective invoices for all unbilled completed work with supporting evidence.",
                "high",
            ),
            LeakageDriver.rate_erosion: (
                "Renegotiate billing rates to match contracted rate card. Apply corrections to future invoices.",
                "high",
            ),
            LeakageDriver.scope_creep: (
                "Raise change orders for all out-of-scope work. Establish scope change approval workflow.",
                "critical",
            ),
            LeakageDriver.missing_change_order: (
                "Create and obtain approval for retroactive change orders to formalise out-of-scope work.",
                "high",
            ),
            LeakageDriver.penalty_exposure: (
                "Negotiate penalty caps and establish SLA monitoring to prevent breaches.",
                "medium",
            ),
            LeakageDriver.unrecovered_cost: (
                "Review cost allocation and identify pass-through or reimbursable items.",
                "medium",
            ),
        }

        seen_drivers: set[LeakageDriver] = set()
        for trigger in triggers:
            if trigger.driver in seen_drivers:
                continue
            seen_drivers.add(trigger.driver)

            action, priority = driver_actions.get(
                trigger.driver,
                ("Review and remediate identified leakage.", "medium"),
            )

            # Sum estimated impact for this driver
            total_for_driver = sum(
                t.estimated_impact for t in triggers if t.driver == trigger.driver
            )

            recommendations.append(
                RecoveryRecommendation(
                    driver=trigger.driver,
                    action=action,
                    estimated_recovery=total_for_driver if total_for_driver > 0 else None,
                    currency=trigger.currency,
                    priority=priority,
                    evidence_ids=trigger.evidence_ids,
                )
            )

        return recommendations
