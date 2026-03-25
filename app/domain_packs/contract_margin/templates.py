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
        diagnosis_result: dict,
        contract_summary: dict,
        reconciliation_data: dict | None = None,
        audit_events: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Render a comprehensive margin diagnosis report.

        Returns dict with sections:
        - executive_summary
        - contract_overview (parties, dates, type)
        - billability_assessment
        - leakage_analysis (triggers with severity/impact)
        - penalty_exposure (conditions, breaches, financial impact)
        - recovery_plan (recommendations with estimated values, priorities)
        - evidence_chain (completeness status per evidence type)
        - reconciliation_findings (cross-pack links, conflicts)
        - audit_trail (key events timeline)
        - appendix (raw evidence references)
        """
        # --- Extract from diagnosis_result ---
        verdict = diagnosis_result.get("verdict", "unknown")
        leakage_triggers = diagnosis_result.get("leakage_triggers", [])
        penalty_exposure = diagnosis_result.get("penalty_exposure", [])
        recovery_recommendations = diagnosis_result.get("recovery_recommendations", [])
        billability = diagnosis_result.get("billability_assessment", {})
        evidence_ids = diagnosis_result.get("evidence_ids", [])
        executive_summary = diagnosis_result.get("executive_summary", "")
        total_at_risk = diagnosis_result.get("total_at_risk_value", 0.0)

        # --- Leakage analysis ---
        leakage_by_severity: dict[str, int] = {}
        total_leakage_impact = 0.0
        for trigger in leakage_triggers:
            sev = trigger.get("severity", "unknown")
            leakage_by_severity[sev] = leakage_by_severity.get(sev, 0) + 1
            total_leakage_impact += trigger.get("estimated_impact_value", 0.0)

        # --- Penalty exposure ---
        total_penalty_exposure = 0.0
        active_breaches = 0
        for pen in penalty_exposure:
            cap = pen.get("cap")
            if cap and isinstance(cap, (int, float)):
                total_penalty_exposure += cap
            if pen.get("trigger"):
                active_breaches += 1

        # --- Recovery plan ---
        total_estimated_recovery = 0.0
        recovery_by_priority: dict[str, int] = {}
        for rec in recovery_recommendations:
            total_estimated_recovery += rec.get("estimated_recovery_value", 0.0)
            pri = rec.get("priority", "medium")
            recovery_by_priority[pri] = recovery_by_priority.get(pri, 0) + 1

        # --- Evidence chain ---
        evidence_types = ["contract", "invoice", "completion_cert", "daywork_sheet",
                          "approval", "site_report", "as_built"]
        evidence_chain: dict[str, str] = {}
        provided_evidence = {str(e) for e in evidence_ids}
        for etype in evidence_types:
            evidence_chain[etype] = (
                "present" if any(etype in str(e) for e in provided_evidence)
                else "missing"
            )

        # --- Reconciliation findings ---
        reconciliation_findings: dict[str, Any] = {}
        if reconciliation_data:
            reconciliation_findings = {
                "cross_pack_links": reconciliation_data.get("cross_pack_links", []),
                "conflicts": reconciliation_data.get("conflicts", []),
                "conflict_count": len(reconciliation_data.get("conflicts", [])),
                "status": reconciliation_data.get("status", "pending"),
            }

        # --- Audit trail ---
        audit_trail: list[dict] = []
        if audit_events:
            for event in audit_events:
                audit_trail.append({
                    "timestamp": event.get("timestamp", ""),
                    "event_type": event.get("event_type", ""),
                    "description": event.get("description", ""),
                    "actor": event.get("actor", ""),
                })

        return {
            "report_type": "margin_diagnosis",
            "executive_summary": executive_summary,
            "contract_overview": {
                "title": contract_summary.get("title", ""),
                "parties": contract_summary.get("parties", []),
                "contract_type": contract_summary.get("contract_type", ""),
                "effective_date": contract_summary.get("effective_date"),
                "expiry_date": contract_summary.get("expiry_date"),
                "clause_count": contract_summary.get("clause_count", 0),
            },
            "billability_assessment": {
                "verdict": verdict,
                "billable": billability.get("billable", False),
                "confidence": billability.get("confidence", 0.0),
                "reasons": billability.get("reasons", []),
                "rate_applied": billability.get("rate_applied"),
                "category": billability.get("category"),
            },
            "leakage_analysis": {
                "total_triggers": len(leakage_triggers),
                "by_severity": leakage_by_severity,
                "total_estimated_impact": total_leakage_impact,
                "triggers": leakage_triggers,
            },
            "penalty_exposure": {
                "total_penalties": len(penalty_exposure),
                "active_breaches": active_breaches,
                "total_financial_exposure": total_penalty_exposure,
                "total_at_risk_value": total_at_risk,
                "conditions": penalty_exposure,
            },
            "recovery_plan": {
                "total_recommendations": len(recovery_recommendations),
                "total_estimated_recovery": total_estimated_recovery,
                "by_priority": recovery_by_priority,
                "recommendations": recovery_recommendations,
            },
            "evidence_chain": evidence_chain,
            "reconciliation_findings": reconciliation_findings,
            "audit_trail": audit_trail,
            "appendix": {
                "evidence_ids": [str(e) for e in evidence_ids],
                "raw_evidence_count": len(evidence_ids),
            },
        }

    @staticmethod
    def render_simple(
        verdict: str,
        leakage_drivers: list[str],
        recommendations: list[str],
        executive_summary: str,
    ) -> dict[str, Any]:
        """Backward-compatible simple render for legacy callers."""
        return {
            "report_type": "margin_diagnosis",
            "verdict": verdict,
            "leakage_driver_count": len(leakage_drivers),
            "leakage_drivers": leakage_drivers,
            "recommendation_count": len(recommendations),
            "recovery_recommendations": recommendations,
            "executive_summary": executive_summary,
        }
