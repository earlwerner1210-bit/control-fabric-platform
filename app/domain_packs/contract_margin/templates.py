"""Contract & Margin output templates."""

from __future__ import annotations

from typing import Any

from app.domain_packs.contract_margin.schemas import ContractCompileSummary, ParsedContract


class ContractSummaryTemplate:
    @staticmethod
    def render(contract: ParsedContract, control_object_ids: list | None = None) -> dict[str, Any]:
        obligations = [c for c in contract.clauses if c.type.value == "obligation"]
        penalties = [c for c in contract.clauses if c.type.value == "penalty"]

        return {
            "title": contract.title,
            "parties": contract.parties,
            "contract_type": contract.contract_type.value,
            "clause_count": len(contract.clauses),
            "obligation_count": len(obligations),
            "penalty_count": len(penalties),
            "sla_entry_count": len(contract.sla_table),
            "rate_card_entry_count": len(contract.rate_card),
            "control_object_ids": control_object_ids or [],
        }


class MarginReportTemplate:
    @staticmethod
    def render(
        verdict: str,
        leakage_drivers: list[str],
        recommendations: list[str],
        executive_summary: str,
    ) -> dict[str, Any]:
        return {
            "report_type": "margin_diagnosis",
            "verdict": verdict,
            "leakage_driver_count": len(leakage_drivers),
            "leakage_drivers": leakage_drivers,
            "recommendation_count": len(recommendations),
            "recovery_recommendations": recommendations,
            "executive_summary": executive_summary,
        }
