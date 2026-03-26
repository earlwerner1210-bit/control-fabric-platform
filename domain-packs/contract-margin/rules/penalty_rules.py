"""Penalty rule engine for evaluating penalty exposure and mitigation status.

Assesses current and potential penalty exposure across a contract by
evaluating SLA compliance, obligation fulfilment, and penalty conditions.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas.contract_schemas import (
    ParsedContract,
    PenaltyCondition,
    PenaltyExposureSummary,
    RuleResult,
    SLAEntry,
)


@dataclass
class SLAPerformance:
    """Actual SLA performance data for evaluation against contract targets."""

    metric_name: str
    actual_value: float
    measurement_period: str = "monthly"


@dataclass
class ObligationStatus:
    """Current status of a contractual obligation."""

    obligation_id: str
    fulfilled: bool = False
    overdue: bool = False
    days_overdue: int = 0


@dataclass
class PenaltyEvaluation:
    """Result of evaluating a single penalty condition."""

    penalty: PenaltyCondition
    triggered: bool
    reason: str
    estimated_amount: float | None = None
    mitigated: bool = False
    mitigation_notes: str = ""


class PenaltyRuleEngine:
    """Evaluates penalty exposure by checking SLA performance, obligation status,
    and penalty trigger conditions against a parsed contract.
    """

    def evaluate(
        self,
        contract: ParsedContract,
        sla_performance: list[SLAPerformance] | None = None,
        obligation_statuses: list[ObligationStatus] | None = None,
    ) -> PenaltyExposureSummary:
        """Evaluate all penalty conditions and produce an exposure summary.

        Args:
            contract: Parsed contract with penalties and SLA entries.
            sla_performance: Actual SLA performance metrics.
            obligation_statuses: Current fulfilment status of obligations.

        Returns:
            PenaltyExposureSummary with categorised penalties.
        """
        sla_performance = sla_performance or []
        obligation_statuses = obligation_statuses or []

        evaluations = []
        evaluations.extend(self._evaluate_sla_penalties(contract, sla_performance))
        evaluations.extend(self._evaluate_obligation_penalties(contract, obligation_statuses))
        evaluations.extend(self._evaluate_uncapped_penalties(contract))

        triggered = [e for e in evaluations if e.triggered]
        mitigated = [e for e in evaluations if e.mitigated]
        unmitigated = [e for e in triggered if not e.mitigated]

        total_exposure = sum(
            e.estimated_amount for e in triggered if e.estimated_amount is not None
        )

        # Find highest risk penalty
        highest_risk: PenaltyCondition | None = None
        highest_amount = 0.0
        for e in triggered:
            amt = e.estimated_amount or 0.0
            if amt > highest_amount:
                highest_amount = amt
                highest_risk = e.penalty

        return PenaltyExposureSummary(
            contract_id=contract.contract_id,
            total_penalties=len(contract.penalties),
            total_exposure_amount=total_exposure if total_exposure > 0 else None,
            currency=contract.currency,
            unmitigated_penalties=[e.penalty for e in unmitigated],
            mitigated_penalties=[e.penalty for e in mitigated],
            highest_risk_penalty=highest_risk,
        )

    def evaluate_rules(
        self,
        contract: ParsedContract,
        sla_performance: list[SLAPerformance] | None = None,
    ) -> list[RuleResult]:
        """Return individual rule results for audit logging.

        Args:
            contract: Parsed contract.
            sla_performance: Actual SLA performance metrics.

        Returns:
            List of RuleResult for each penalty-related check.
        """
        results: list[RuleResult] = []
        sla_performance = sla_performance or []

        # Rule: all penalties have caps
        uncapped = [p for p in contract.penalties if p.cap is None and p.amount is None]
        results.append(
            RuleResult(
                rule_name="penalties_have_caps",
                passed=len(uncapped) == 0,
                message=(
                    f"{len(uncapped)} penalty condition(s) have no cap or fixed amount."
                    if uncapped
                    else "All penalty conditions have caps or fixed amounts."
                ),
                severity="critical" if uncapped else "info",
            )
        )

        # Rule: SLA targets are being met
        sla_lookup = {s.metric_name.lower(): s for s in contract.sla_entries}
        breached_slas = 0
        for perf in sla_performance:
            sla = sla_lookup.get(perf.metric_name.lower())
            if sla and perf.actual_value < sla.target_value:
                breached_slas += 1

        results.append(
            RuleResult(
                rule_name="sla_targets_met",
                passed=breached_slas == 0,
                message=(
                    f"{breached_slas} SLA target(s) breached."
                    if breached_slas
                    else "All monitored SLA targets are being met."
                ),
                severity="critical" if breached_slas > 0 else "info",
            )
        )

        # Rule: penalty-to-contract-value ratio
        if contract.total_value and contract.total_value > 0:
            total_penalty_amount = sum(p.amount for p in contract.penalties if p.amount is not None)
            ratio = total_penalty_amount / contract.total_value
            results.append(
                RuleResult(
                    rule_name="penalty_ratio_acceptable",
                    passed=ratio < 0.15,
                    message=(
                        f"Total penalty amounts ({contract.currency} {total_penalty_amount:,.2f}) "
                        f"represent {ratio:.1%} of contract value."
                    ),
                    severity="warning" if ratio >= 0.10 else "info",
                )
            )

        return results

    def _evaluate_sla_penalties(
        self,
        contract: ParsedContract,
        sla_performance: list[SLAPerformance],
    ) -> list[PenaltyEvaluation]:
        """Check if any SLA-linked penalties are triggered by performance data."""
        evaluations: list[PenaltyEvaluation] = []
        sla_lookup = {s.metric_name.lower(): s for s in contract.sla_entries}

        for perf in sla_performance:
            sla = sla_lookup.get(perf.metric_name.lower())
            if not sla:
                continue

            if perf.actual_value < sla.target_value:
                # Find linked penalty
                linked_penalty = self._find_sla_penalty(contract, sla)
                if linked_penalty:
                    evaluations.append(
                        PenaltyEvaluation(
                            penalty=linked_penalty,
                            triggered=True,
                            reason=(
                                f"SLA '{sla.metric_name}' breached: actual {perf.actual_value}{sla.unit} "
                                f"vs target {sla.target_value}{sla.unit}."
                            ),
                            estimated_amount=linked_penalty.amount,
                        )
                    )

        return evaluations

    def _evaluate_obligation_penalties(
        self,
        contract: ParsedContract,
        obligation_statuses: list[ObligationStatus],
    ) -> list[PenaltyEvaluation]:
        """Check if overdue obligations trigger penalty conditions."""
        evaluations: list[PenaltyEvaluation] = []
        overdue = [o for o in obligation_statuses if o.overdue]

        for status in overdue:
            # Look for penalties linked to obligations
            for penalty in contract.penalties:
                if any(
                    status.obligation_id in cid or cid in status.obligation_id
                    for cid in penalty.linked_clause_ids
                ):
                    evaluations.append(
                        PenaltyEvaluation(
                            penalty=penalty,
                            triggered=True,
                            reason=(
                                f"Obligation '{status.obligation_id}' is {status.days_overdue} "
                                f"days overdue, triggering penalty."
                            ),
                            estimated_amount=penalty.amount,
                        )
                    )

        return evaluations

    def _evaluate_uncapped_penalties(
        self,
        contract: ParsedContract,
    ) -> list[PenaltyEvaluation]:
        """Flag penalties that have no cap and could represent unlimited exposure."""
        evaluations: list[PenaltyEvaluation] = []
        for penalty in contract.penalties:
            if penalty.cap is None and penalty.amount is None:
                evaluations.append(
                    PenaltyEvaluation(
                        penalty=penalty,
                        triggered=False,
                        reason="Penalty has no cap or fixed amount. Exposure is potentially unlimited.",
                        estimated_amount=None,
                        mitigated=False,
                        mitigation_notes="Recommend negotiating a cap on this penalty.",
                    )
                )
        return evaluations

    def _find_sla_penalty(
        self,
        contract: ParsedContract,
        sla: SLAEntry,
    ) -> PenaltyCondition | None:
        """Find a penalty condition linked to a specific SLA entry."""
        if sla.penalty_on_breach:
            # Try to match penalty by description
            for penalty in contract.penalties:
                if (
                    sla.metric_name.lower() in penalty.trigger_condition.lower()
                    or sla.penalty_on_breach.lower() in penalty.trigger_condition.lower()
                ):
                    return penalty

        # Fallback: return first penalty linked to an SLA clause
        for penalty in contract.penalties:
            if sla.clause_ref and sla.clause_ref in penalty.linked_clause_ids:
                return penalty

        return contract.penalties[0] if contract.penalties else None
