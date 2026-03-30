"""Reconciler service -- margin reconciliation between contract terms and execution data."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class _ReconciliationStore:
    """In-memory reconciliation result store (replaced by DB in production)."""

    def __init__(self) -> None:
        self._results: dict[UUID, dict[str, Any]] = {}

    def save(self, case_id: UUID, result: dict[str, Any]) -> None:
        self._results[case_id] = result

    def get(self, case_id: UUID, tenant_id: UUID) -> dict[str, Any] | None:
        result = self._results.get(case_id)
        if result and result.get("tenant_id") == tenant_id:
            return result
        return None


class ReconcilerService:
    """Reconciles contract obligations / rate cards against actual work orders and incidents."""

    def __init__(self) -> None:
        self._store = _ReconciliationStore()

    def run_margin_reconciliation(
        self,
        tenant_id: UUID,
        contract: dict[str, Any],
        work_orders: list[dict[str, Any]],
        incidents: list[dict[str, Any]],
        rate_card: dict[str, Any] | None = None,
        obligations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute the margin reconciliation pipeline.

        Steps (stub implementation):
        1. Match work-order line items against rate-card entries.
        2. Flag items that lack contractual backing (leakage candidates).
        3. Check SLA / obligation compliance for incidents.
        4. Compute overall margin verdict.
        """
        leakage_drivers: list[str] = []
        recovery_recommendations: list[str] = []
        billability_details: dict[str, Any] = {}
        penalty_exposure: dict[str, Any] = {}

        # --- 1. Rate-card matching ---
        rc_items = (rate_card or {}).get("items", [])
        rc_lookup: dict[str, dict[str, Any]] = {
            item.get("code", ""): item for item in rc_items if item.get("code")
        }

        total_billed = 0.0
        total_unbacked = 0.0
        for wo in work_orders:
            for line in wo.get("line_items", []):
                code = line.get("rate_code", "")
                amount = float(line.get("amount", 0))
                if code in rc_lookup:
                    total_billed += amount
                else:
                    total_unbacked += amount
                    leakage_drivers.append(f"Work-order line '{code}' has no rate-card match")

        billability_details["total_billed"] = total_billed
        billability_details["total_unbacked"] = total_unbacked

        # --- 2. Obligation / SLA checks ---
        obligation_list = obligations or contract.get("obligations", [])
        breached_obligations: list[str] = []
        for obl in obligation_list:
            obl_id = obl.get("id", obl.get("label", "unknown"))
            target = obl.get("target")
            # Simple stub: check if any incident references this obligation
            for inc in incidents:
                if inc.get("obligation_ref") == obl_id and not inc.get("resolved_within_sla", True):
                    breached_obligations.append(str(obl_id))
                    penalty_exposure[str(obl_id)] = obl.get("penalty_amount", "unknown")

        if breached_obligations:
            leakage_drivers.append(
                f"SLA breaches on obligations: {', '.join(breached_obligations)}"
            )
            recovery_recommendations.append(
                "Review breached obligations for penalty negotiation or evidence of force majeure"
            )

        if total_unbacked > 0:
            recovery_recommendations.append(
                f"Investigate {total_unbacked:.2f} in unbacked charges for potential recovery"
            )

        # --- 3. Determine verdict ---
        if breached_obligations and total_unbacked > 0:
            verdict = "penalty_risk"
        elif total_unbacked > 0:
            verdict = "under_recovery"
        elif breached_obligations:
            verdict = "penalty_risk"
        elif total_billed > 0:
            verdict = "billable"
        else:
            verdict = "unknown"

        result: dict[str, Any] = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            "verdict": verdict,
            "leakage_drivers": leakage_drivers,
            "recovery_recommendations": recovery_recommendations,
            "billability_details": billability_details,
            "penalty_exposure": penalty_exposure,
            "executive_summary": (
                f"Reconciliation complete: verdict={verdict}, "
                f"billed={total_billed:.2f}, unbacked={total_unbacked:.2f}, "
                f"breaches={len(breached_obligations)}"
            ),
            "created_at": _now(),
        }

        logger.info(
            "reconciler.run: tenant=%s verdict=%s leakage_drivers=%d",
            tenant_id,
            verdict,
            len(leakage_drivers),
        )
        return result

    def persist_reconciliation_results(
        self,
        case_id: UUID,
        results: dict[str, Any],
    ) -> None:
        """Persist reconciliation results keyed by workflow case ID."""
        self._store.save(case_id, results)
        logger.info("reconciler.persist: case=%s", case_id)

    def get_reconciliation_result(
        self,
        case_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, Any] | None:
        """Retrieve persisted reconciliation results."""
        return self._store.get(case_id, tenant_id)


# Singleton
reconciler_service = ReconcilerService()
