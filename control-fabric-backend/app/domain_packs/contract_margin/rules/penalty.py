"""
Penalty exposure analysis for the contract margin domain pack.

Analyses SLA performance data against penalty conditions to calculate
total exposure, identify active breaches, and suggest mitigation actions.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.domain_packs.contract_margin.schemas.contract import (
    PenaltyCondition,
    PriorityLevel,
)


class PenaltyExposureSummary(BaseModel):
    """Summary of penalty exposure for a contract or period."""
    total_penalties: float = Field(default=0.0, ge=0.0, description="Total penalty value")
    active_breaches: int = Field(default=0, ge=0, description="Number of active breaches")
    breach_details: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Details of each breach: clause_id, description, penalty_value, breach_type, mitigated",
    )
    capped: bool = Field(default=False, description="Whether a penalty cap has been applied")
    cap_value: float = Field(default=0.0, ge=0.0, description="Cap value applied")
    mitigation_actions: list[str] = Field(
        default_factory=list,
        description="Recommended mitigation actions",
    )


class PenaltyExposureAnalyzer:
    """Analyse penalty exposure against SLA performance data."""

    def analyze(
        self,
        penalty_conditions: list[PenaltyCondition],
        sla_performance: list[dict[str, Any]],
        monthly_invoice_value: float = 0.0,
    ) -> PenaltyExposureSummary:
        """Calculate penalty exposure.

        Parameters
        ----------
        penalty_conditions:
            Penalty conditions extracted from the contract.
        sla_performance:
            List of dicts with ``clause_id`` or ``trigger``, ``breached`` (bool),
            ``breach_days`` (int, days since breach), ``severity``,
            ``current_value`` (actual performance metric).
        monthly_invoice_value:
            Monthly invoice value used to compute percentage-based penalties.
        """
        breach_details: list[dict[str, Any]] = []
        total_penalty_value = 0.0
        overall_cap: Optional[float] = None
        mitigation_actions: list[str] = []

        perf_index = self._build_performance_index(sla_performance)

        for condition in penalty_conditions:
            perf = self._find_matching_performance(condition, perf_index)
            if perf is None:
                continue

            breached = perf.get("breached", False)
            if not breached:
                continue

            breach_days = int(perf.get("breach_days", 0))

            # Check grace period
            if breach_days <= condition.grace_period_days:
                mitigation_actions.append(
                    f"Breach of '{condition.description[:60]}' is within grace period "
                    f"({breach_days}/{condition.grace_period_days} days). No penalty yet."
                )
                continue

            # Check cure period
            in_cure_period = (
                condition.cure_period_days > 0
                and breach_days <= (condition.grace_period_days + condition.cure_period_days)
            )
            if in_cure_period:
                mitigation_actions.append(
                    f"Breach of '{condition.description[:60]}' is within cure period. "
                    f"Remediate within {condition.cure_period_days} days to avoid penalty."
                )

            # Calculate penalty value
            penalty_value = self._calculate_penalty_value(
                condition, monthly_invoice_value
            )

            # Apply per-condition cap
            if condition.cap is not None and condition.cap > 0:
                if penalty_value > condition.cap:
                    penalty_value = condition.cap
                if overall_cap is None or condition.cap > overall_cap:
                    overall_cap = condition.cap

            breach_details.append({
                "clause_id": condition.clause_id,
                "description": condition.description,
                "penalty_value": round(penalty_value, 2),
                "penalty_type": condition.penalty_type,
                "breach_type": condition.trigger,
                "breach_days": breach_days,
                "in_cure_period": in_cure_period,
                "mitigated": in_cure_period,
            })

            total_penalty_value += penalty_value

            # Mitigation suggestions
            if not in_cure_period:
                mitigation_actions.append(
                    f"Penalty active for '{condition.description[:60]}': "
                    f"value {penalty_value:.2f}. Consider negotiating a cure or waiver."
                )

        # Apply overall cap if present
        capped = False
        cap_applied = 0.0
        if overall_cap is not None and total_penalty_value > overall_cap:
            total_penalty_value = overall_cap
            capped = True
            cap_applied = overall_cap
            mitigation_actions.append(
                f"Total penalties capped at {overall_cap:.2f} per contract terms."
            )

        if not breach_details:
            mitigation_actions.append("No active penalty breaches detected.")

        return PenaltyExposureSummary(
            total_penalties=round(total_penalty_value, 2),
            active_breaches=len(breach_details),
            breach_details=breach_details,
            capped=capped,
            cap_value=cap_applied,
            mitigation_actions=mitigation_actions,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_performance_index(
        sla_performance: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Build a lookup from clause_id/trigger to performance data."""
        index: dict[str, dict[str, Any]] = {}
        for perf in sla_performance:
            clause_id = perf.get("clause_id", "")
            trigger = perf.get("trigger", "")
            if clause_id:
                index[clause_id] = perf
            if trigger:
                index[trigger.lower().strip()] = perf
        return index

    @staticmethod
    def _find_matching_performance(
        condition: PenaltyCondition,
        perf_index: dict[str, dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        """Find the performance record that matches a penalty condition."""
        if condition.clause_id in perf_index:
            return perf_index[condition.clause_id]
        trigger_lower = condition.trigger.lower().strip()
        if trigger_lower in perf_index:
            return perf_index[trigger_lower]
        for key, perf in perf_index.items():
            if trigger_lower in key or key in trigger_lower:
                return perf
        return None

    @staticmethod
    def _calculate_penalty_value(
        condition: PenaltyCondition,
        monthly_invoice_value: float,
    ) -> float:
        """Calculate the monetary penalty value for a condition."""
        if condition.penalty_type == "percentage":
            return (condition.penalty_amount / 100.0) * monthly_invoice_value
        if condition.penalty_type == "fixed":
            return condition.penalty_amount
        if condition.penalty_type == "service_credit":
            return (condition.penalty_amount / 100.0) * monthly_invoice_value
        if condition.penalty_type == "liquidated_damages":
            return condition.penalty_amount
        return condition.penalty_amount
