"""
Leakage detection rule engine for the contract margin domain pack.

Identifies revenue leakage by comparing executed work against rate cards,
obligations, and work order records.  Each rule detects a specific leakage
pattern commonly found in telecom field-service contracts.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional, Sequence

from app.domain_packs.contract_margin.schemas.contract import (
    LeakageTrigger,
    Obligation,
    PriorityLevel,
    RateCardEntry,
)


class LeakageRuleEngine:
    """Detect revenue leakage across work orders, rate cards, and obligations."""

    def detect(
        self,
        activity: dict[str, Any],
        rate_card: list[RateCardEntry],
        work_orders: list[dict[str, Any]],
        obligations: list[Obligation],
        incidents: Optional[list[dict[str, Any]]] = None,
    ) -> list[LeakageTrigger]:
        """Run all leakage rules and return detected triggers.

        Parameters
        ----------
        activity:
            Dict with keys: ``name``, ``status``, ``billed`` (bool),
            ``billed_rate``, ``category``, ``hours``, ``materials_cost``,
            ``subcontractor_cost``, ``mobilisation_charged`` (bool),
            ``warranty_expiry`` (date str), ``daywork_sheet`` (bool).
        rate_card:
            Rate card entries for the contract.
        work_orders:
            List of work-order dicts with ``activity``, ``status``,
            ``billed``, ``date``, ``value``.
        obligations:
            Extracted contract obligations.
        incidents:
            Optional list of incident dicts with ``activity``,
            ``cause``, ``resolution``.
        """
        incidents = incidents or []
        triggers: list[LeakageTrigger] = []

        checks = [
            self._rule_unbilled_completed_work,
            self._rule_rate_below_contract,
            self._rule_scope_creep_unpriced,
            self._rule_penalty_exposure_unmitigated,
            self._rule_missing_daywork_sheet,
            self._rule_time_based_rate_mismatch,
            self._rule_material_cost_passthrough,
            self._rule_subcontractor_margin_leak,
            self._rule_mobilisation_not_charged,
            self._rule_warranty_period_rework,
        ]

        for check in checks:
            result = check(activity, rate_card, work_orders, obligations, incidents)
            if result is not None:
                triggers.append(result)

        return triggers

    # ------------------------------------------------------------------
    # Individual leakage rules
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_unbilled_completed_work(
        activity: dict[str, Any],
        rate_card: list[RateCardEntry],
        work_orders: list[dict[str, Any]],
        obligations: list[Obligation],
        incidents: list[dict[str, Any]],
    ) -> Optional[LeakageTrigger]:
        """Detect completed work orders that have not been billed."""
        unbilled_value = 0.0
        unbilled_refs: list[str] = []
        for wo in work_orders:
            if wo.get("status", "").lower() == "completed" and not wo.get("billed", False):
                unbilled_value += float(wo.get("value", 0.0))
                unbilled_refs.append(str(wo.get("reference", wo.get("activity", "unknown"))))
        if unbilled_value > 0:
            return LeakageTrigger(
                trigger_type="unbilled_completed_work",
                description=f"{len(unbilled_refs)} completed work order(s) totalling {unbilled_value:.2f} have not been billed",
                severity=PriorityLevel.high if unbilled_value > 5000 else PriorityLevel.medium,
                estimated_impact_value=unbilled_value,
                clause_refs=[],
                evidence=unbilled_refs,
            )
        return None

    @staticmethod
    def _rule_rate_below_contract(
        activity: dict[str, Any],
        rate_card: list[RateCardEntry],
        work_orders: list[dict[str, Any]],
        obligations: list[Obligation],
        incidents: list[dict[str, Any]],
    ) -> Optional[LeakageTrigger]:
        """Detect when billed rate is below the contracted rate."""
        activity_name = activity.get("name", "").lower().strip()
        billed_rate = float(activity.get("billed_rate", 0.0))
        if billed_rate <= 0:
            return None

        for entry in rate_card:
            if entry.activity.lower().strip() == activity_name or activity_name in entry.activity.lower():
                contract_rate = entry.rate
                if billed_rate < contract_rate:
                    diff = contract_rate - billed_rate
                    quantity = float(activity.get("quantity", 1))
                    impact = round(diff * quantity, 2)
                    return LeakageTrigger(
                        trigger_type="rate_below_contract",
                        description=(
                            f"Activity '{activity.get('name')}' billed at {billed_rate:.2f} "
                            f"but contract rate is {contract_rate:.2f} (under-recovery of {diff:.2f} per unit)"
                        ),
                        severity=PriorityLevel.high,
                        estimated_impact_value=impact,
                        clause_refs=[],
                        evidence=[f"rate_card:{entry.activity}"],
                    )
                break
        return None

    @staticmethod
    def _rule_scope_creep_unpriced(
        activity: dict[str, Any],
        rate_card: list[RateCardEntry],
        work_orders: list[dict[str, Any]],
        obligations: list[Obligation],
        incidents: list[dict[str, Any]],
    ) -> Optional[LeakageTrigger]:
        """Detect activities performed that have no matching rate card entry."""
        activity_name = activity.get("name", "").lower().strip()
        if not activity_name:
            return None

        for entry in rate_card:
            entry_lower = entry.activity.lower().strip()
            if activity_name == entry_lower or activity_name in entry_lower or entry_lower in activity_name:
                return None

        estimated = float(activity.get("value", 0.0)) or float(activity.get("hours", 0)) * 50.0
        return LeakageTrigger(
            trigger_type="scope_creep_unpriced",
            description=f"Activity '{activity.get('name')}' has no rate card entry — potential scope creep performed without commercial agreement",
            severity=PriorityLevel.high,
            estimated_impact_value=estimated,
            clause_refs=[],
            evidence=["no_rate_card_match"],
        )

    @staticmethod
    def _rule_penalty_exposure_unmitigated(
        activity: dict[str, Any],
        rate_card: list[RateCardEntry],
        work_orders: list[dict[str, Any]],
        obligations: list[Obligation],
        incidents: list[dict[str, Any]],
    ) -> Optional[LeakageTrigger]:
        """Detect obligations with evidence requirements that are unfulfilled."""
        activity_name = activity.get("name", "").lower()
        activity_evidence = set(e.lower() for e in activity.get("evidence", []))

        for ob in obligations:
            if activity_name not in ob.description.lower() and ob.owner != "provider":
                continue
            required = set(r.lower() for r in ob.evidence_required)
            missing = required - activity_evidence
            if missing:
                return LeakageTrigger(
                    trigger_type="penalty_exposure_unmitigated",
                    description=(
                        f"Obligation '{ob.description[:80]}' has unmet evidence requirements: "
                        f"{', '.join(sorted(missing))}. This may expose the provider to penalties."
                    ),
                    severity=PriorityLevel.high,
                    estimated_impact_value=0.0,
                    clause_refs=[ob.clause_id],
                    evidence=list(sorted(missing)),
                )
        return None

    @staticmethod
    def _rule_missing_daywork_sheet(
        activity: dict[str, Any],
        rate_card: list[RateCardEntry],
        work_orders: list[dict[str, Any]],
        obligations: list[Obligation],
        incidents: list[dict[str, Any]],
    ) -> Optional[LeakageTrigger]:
        """Detect activities missing a daywork sheet when one is likely required."""
        has_daywork = activity.get("daywork_sheet", False)
        category = activity.get("category", "").lower()
        hours = float(activity.get("hours", 0))

        if not has_daywork and (category in ("standard", "overtime", "emergency") and hours > 0):
            hourly_rate = 0.0
            activity_name = activity.get("name", "").lower()
            for entry in rate_card:
                if entry.activity.lower() in activity_name or activity_name in entry.activity.lower():
                    hourly_rate = entry.rate
                    break
            impact = round(hours * hourly_rate, 2) if hourly_rate > 0 else 0.0
            return LeakageTrigger(
                trigger_type="missing_daywork_sheet",
                description=f"Activity '{activity.get('name')}' ({hours}h) has no daywork sheet — billing evidence is incomplete",
                severity=PriorityLevel.medium,
                estimated_impact_value=impact,
                clause_refs=[],
                evidence=["daywork_sheet_missing"],
            )
        return None

    @staticmethod
    def _rule_time_based_rate_mismatch(
        activity: dict[str, Any],
        rate_card: list[RateCardEntry],
        work_orders: list[dict[str, Any]],
        obligations: list[Obligation],
        incidents: list[dict[str, Any]],
    ) -> Optional[LeakageTrigger]:
        """Detect time-based billing where hours exceed or don't align with the rate unit."""
        activity_name = activity.get("name", "").lower()
        hours = float(activity.get("hours", 0))
        if hours <= 0:
            return None

        for entry in rate_card:
            if entry.activity.lower() not in activity_name and activity_name not in entry.activity.lower():
                continue
            unit_lower = entry.unit.lower()
            if unit_lower in ("day", "days"):
                expected_days = hours / 8.0
                billed_quantity = float(activity.get("quantity", expected_days))
                if abs(billed_quantity - expected_days) > 0.5:
                    diff_value = abs(billed_quantity - expected_days) * entry.rate
                    return LeakageTrigger(
                        trigger_type="time_based_rate_mismatch",
                        description=(
                            f"Activity '{activity.get('name')}' logged {hours}h ({expected_days:.1f} days) "
                            f"but billed for {billed_quantity} days — mismatch of {abs(billed_quantity - expected_days):.1f} days"
                        ),
                        severity=PriorityLevel.medium,
                        estimated_impact_value=round(diff_value, 2),
                        clause_refs=[],
                        evidence=[f"hours:{hours}", f"billed_qty:{billed_quantity}"],
                    )
            break
        return None

    @staticmethod
    def _rule_material_cost_passthrough(
        activity: dict[str, Any],
        rate_card: list[RateCardEntry],
        work_orders: list[dict[str, Any]],
        obligations: list[Obligation],
        incidents: list[dict[str, Any]],
    ) -> Optional[LeakageTrigger]:
        """Detect material costs not passed through to the client."""
        materials_cost = float(activity.get("materials_cost", 0.0))
        if materials_cost <= 0:
            return None

        billed_materials = float(activity.get("billed_materials", 0.0))
        if billed_materials < materials_cost:
            diff = round(materials_cost - billed_materials, 2)
            return LeakageTrigger(
                trigger_type="material_cost_passthrough",
                description=(
                    f"Material costs of {materials_cost:.2f} incurred but only {billed_materials:.2f} "
                    f"billed — {diff:.2f} not passed through"
                ),
                severity=PriorityLevel.medium if diff < 2000 else PriorityLevel.high,
                estimated_impact_value=diff,
                clause_refs=[],
                evidence=["material_invoice", "billing_record"],
            )
        return None

    @staticmethod
    def _rule_subcontractor_margin_leak(
        activity: dict[str, Any],
        rate_card: list[RateCardEntry],
        work_orders: list[dict[str, Any]],
        obligations: list[Obligation],
        incidents: list[dict[str, Any]],
    ) -> Optional[LeakageTrigger]:
        """Detect subcontractor costs exceeding the billed rate (negative margin)."""
        subcontractor_cost = float(activity.get("subcontractor_cost", 0.0))
        if subcontractor_cost <= 0:
            return None

        billed_rate = float(activity.get("billed_rate", 0.0))
        quantity = float(activity.get("quantity", 1))
        billed_total = billed_rate * quantity

        if subcontractor_cost > billed_total and billed_total > 0:
            leak = round(subcontractor_cost - billed_total, 2)
            return LeakageTrigger(
                trigger_type="subcontractor_margin_leak",
                description=(
                    f"Subcontractor cost {subcontractor_cost:.2f} exceeds billed revenue "
                    f"{billed_total:.2f} — negative margin of {leak:.2f}"
                ),
                severity=PriorityLevel.critical,
                estimated_impact_value=leak,
                clause_refs=[],
                evidence=["subcontractor_invoice", "billing_record"],
            )
        return None

    @staticmethod
    def _rule_mobilisation_not_charged(
        activity: dict[str, Any],
        rate_card: list[RateCardEntry],
        work_orders: list[dict[str, Any]],
        obligations: list[Obligation],
        incidents: list[dict[str, Any]],
    ) -> Optional[LeakageTrigger]:
        """Detect when mobilisation was required but not charged."""
        mobilisation_charged = activity.get("mobilisation_charged", True)
        if mobilisation_charged:
            return None

        mob_rate = 0.0
        for entry in rate_card:
            if "mobilisation" in entry.activity.lower() or "mobilization" in entry.activity.lower():
                mob_rate = entry.rate
                break

        if mob_rate > 0:
            return LeakageTrigger(
                trigger_type="mobilisation_not_charged",
                description=(
                    f"Mobilisation for activity '{activity.get('name')}' was not charged. "
                    f"Contract rate card includes mobilisation at {mob_rate:.2f}."
                ),
                severity=PriorityLevel.medium,
                estimated_impact_value=mob_rate,
                clause_refs=[],
                evidence=["mobilisation_rate_card"],
            )
        return None

    @staticmethod
    def _rule_warranty_period_rework(
        activity: dict[str, Any],
        rate_card: list[RateCardEntry],
        work_orders: list[dict[str, Any]],
        obligations: list[Obligation],
        incidents: list[dict[str, Any]],
    ) -> Optional[LeakageTrigger]:
        """Detect rework performed outside warranty period that should be billable."""
        warranty_expiry_raw = activity.get("warranty_expiry")
        if not warranty_expiry_raw:
            return None

        try:
            if isinstance(warranty_expiry_raw, date):
                warranty_expiry = warranty_expiry_raw
            else:
                from datetime import datetime as dt
                warranty_expiry = dt.strptime(str(warranty_expiry_raw), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

        work_date_raw = activity.get("work_date")
        try:
            if isinstance(work_date_raw, date):
                work_date = work_date_raw
            else:
                from datetime import datetime as dt
                work_date = dt.strptime(str(work_date_raw), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            work_date = date.today()

        if work_date > warranty_expiry:
            activity_name = activity.get("name", "")
            activity_lower = activity_name.lower()
            rate_val = 0.0
            for entry in rate_card:
                if entry.activity.lower() in activity_lower or activity_lower in entry.activity.lower():
                    rate_val = entry.rate
                    break
            quantity = float(activity.get("quantity", 1))
            impact = round(rate_val * quantity, 2)
            return LeakageTrigger(
                trigger_type="warranty_period_rework",
                description=(
                    f"Rework for '{activity_name}' performed on {work_date.isoformat()} "
                    f"but warranty expired on {warranty_expiry.isoformat()} — work should be billable"
                ),
                severity=PriorityLevel.high,
                estimated_impact_value=impact,
                clause_refs=[],
                evidence=["warranty_expiry_date", "work_completion_record"],
            )
        return None
