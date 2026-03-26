"""
Recovery recommendation engine for the contract margin domain pack.

Maps detected leakage triggers to actionable commercial recovery
recommendations with estimated values, evidence references, and priorities.
"""

from __future__ import annotations

from typing import Any

from app.domain_packs.contract_margin.schemas.contract import (
    CommercialRecoveryRecommendation,
    LeakageTrigger,
    ParsedContract,
    PriorityLevel,
    RateCardEntry,
    RecoveryType,
)

# ---------------------------------------------------------------------------
# Mapping from trigger types to recovery strategies
# ---------------------------------------------------------------------------

_TRIGGER_RECOVERY_MAP: dict[str, dict[str, Any]] = {
    "unbilled_completed_work": {
        "recovery_type": RecoveryType.backbill,
        "template": (
            "Submit backbill claim for {count} unbilled completed work orders "
            "totalling an estimated {value:.2f}. Attach completion records and "
            "work order references as supporting evidence."
        ),
        "priority": PriorityLevel.high,
        "confidence": 0.9,
    },
    "rate_below_contract": {
        "recovery_type": RecoveryType.rate_adjustment,
        "template": (
            "Raise a rate adjustment claim for activity '{activity}'. The billed "
            "rate is below the contracted rate, resulting in under-recovery of "
            "approximately {value:.2f}. Reference the rate card schedule."
        ),
        "priority": PriorityLevel.high,
        "confidence": 0.85,
    },
    "scope_creep_unpriced": {
        "recovery_type": RecoveryType.change_order,
        "template": (
            "Initiate a change order to price activity '{activity}' which is not "
            "covered by the existing rate card. Estimated value at risk: {value:.2f}. "
            "Document the scope gap and obtain commercial agreement."
        ),
        "priority": PriorityLevel.high,
        "confidence": 0.75,
    },
    "penalty_exposure_unmitigated": {
        "recovery_type": RecoveryType.evidence_collection,
        "template": (
            "Collect missing evidence to mitigate penalty exposure related to "
            "'{description}'. Missing items: {evidence}. Completing evidence "
            "collection may enable a penalty waiver claim."
        ),
        "priority": PriorityLevel.critical,
        "confidence": 0.8,
    },
    "missing_daywork_sheet": {
        "recovery_type": RecoveryType.evidence_collection,
        "template": (
            "Obtain daywork sheet for activity '{activity}' to support billing "
            "claim of {value:.2f}. Without the daywork sheet the invoice may be "
            "rejected or disputed by the client."
        ),
        "priority": PriorityLevel.medium,
        "confidence": 0.85,
    },
    "time_based_rate_mismatch": {
        "recovery_type": RecoveryType.rate_adjustment,
        "template": (
            "Review time-based billing for activity '{activity}'. A mismatch "
            "between logged hours and billed quantity has been detected, with "
            "an estimated impact of {value:.2f}. Reconcile records."
        ),
        "priority": PriorityLevel.medium,
        "confidence": 0.7,
    },
    "material_cost_passthrough": {
        "recovery_type": RecoveryType.backbill,
        "template": (
            "Submit supplementary invoice for material costs of {value:.2f} "
            "that were not passed through to the client. Attach delivery notes "
            "and material invoices as evidence."
        ),
        "priority": PriorityLevel.medium,
        "confidence": 0.85,
    },
    "subcontractor_margin_leak": {
        "recovery_type": RecoveryType.dispute,
        "template": (
            "Subcontractor costs exceed billed revenue, creating a negative "
            "margin of {value:.2f}. Review subcontractor rates against contract "
            "rate card. Consider raising a dispute or renegotiating terms."
        ),
        "priority": PriorityLevel.critical,
        "confidence": 0.8,
    },
    "mobilisation_not_charged": {
        "recovery_type": RecoveryType.backbill,
        "template": (
            "Mobilisation charge of {value:.2f} was not applied for activity "
            "'{activity}'. The rate card includes a mobilisation rate — submit "
            "a supplementary claim with mobilisation evidence."
        ),
        "priority": PriorityLevel.medium,
        "confidence": 0.9,
    },
    "warranty_period_rework": {
        "recovery_type": RecoveryType.backbill,
        "template": (
            "Rework for '{activity}' was performed after warranty expiry and "
            "should be billable. Estimated recoverable value: {value:.2f}. "
            "Submit a new billing claim with warranty expiry evidence."
        ),
        "priority": PriorityLevel.high,
        "confidence": 0.85,
    },
}


class RecoveryRecommendationEngine:
    """Build recovery recommendations from detected leakage triggers."""

    def build_recommendations(
        self,
        leakage_triggers: list[LeakageTrigger],
        contract_objects: ParsedContract | None = None,
        rate_card: list[RateCardEntry] | None = None,
    ) -> list[CommercialRecoveryRecommendation]:
        """Generate prioritised recovery recommendations.

        Parameters
        ----------
        leakage_triggers:
            Leakage triggers detected by the LeakageRuleEngine.
        contract_objects:
            Parsed contract (used for clause cross-references).
        rate_card:
            Rate card entries (used for value estimation).
        """
        rate_card = rate_card or (contract_objects.rate_card if contract_objects else [])
        recommendations: list[CommercialRecoveryRecommendation] = []

        for trigger in leakage_triggers:
            rec = self._build_single(trigger, rate_card)
            if rec is not None:
                recommendations.append(rec)

        # Sort by priority then by estimated value descending
        priority_order = {
            PriorityLevel.critical: 0,
            PriorityLevel.high: 1,
            PriorityLevel.medium: 2,
            PriorityLevel.low: 3,
        }
        recommendations.sort(
            key=lambda r: (priority_order.get(r.priority, 9), -r.estimated_recovery_value)
        )

        return recommendations

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_single(
        self,
        trigger: LeakageTrigger,
        rate_card: list[RateCardEntry],
    ) -> CommercialRecoveryRecommendation | None:
        """Build a single recommendation from a trigger."""
        mapping = _TRIGGER_RECOVERY_MAP.get(trigger.trigger_type)
        if mapping is None:
            return self._build_fallback(trigger)

        template: str = mapping["template"]
        description = template.format(
            activity=trigger.description[:60],
            value=trigger.estimated_impact_value,
            count=len(trigger.evidence),
            description=trigger.description[:80],
            evidence=", ".join(trigger.evidence) if trigger.evidence else "see details",
        )

        return CommercialRecoveryRecommendation(
            recommendation_type=mapping["recovery_type"],
            description=description,
            estimated_recovery_value=trigger.estimated_impact_value,
            evidence_clause_refs=trigger.clause_refs,
            priority=mapping["priority"],
            confidence=mapping["confidence"],
        )

    @staticmethod
    def _build_fallback(trigger: LeakageTrigger) -> CommercialRecoveryRecommendation:
        """Build a generic recommendation for unrecognised trigger types."""
        return CommercialRecoveryRecommendation(
            recommendation_type=RecoveryType.evidence_collection,
            description=(
                f"Investigate leakage trigger '{trigger.trigger_type}': "
                f"{trigger.description}. Estimated impact: {trigger.estimated_impact_value:.2f}. "
                f"Gather evidence and escalate for commercial review."
            ),
            estimated_recovery_value=trigger.estimated_impact_value,
            evidence_clause_refs=trigger.clause_refs,
            priority=trigger.severity,
            confidence=0.5,
        )
