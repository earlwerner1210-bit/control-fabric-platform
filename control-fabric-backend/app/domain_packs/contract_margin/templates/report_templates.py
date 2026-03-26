"""
Report rendering templates for the contract margin domain pack.

Transforms a MarginDiagnosisResult into a structured report dict suitable
for PDF generation, dashboard display, or API response.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain_packs.contract_margin.schemas.contract import (
    BillabilityDecision,
    CommercialEvidenceBundle,
    CommercialRecoveryRecommendation,
    LeakageTrigger,
    MarginDiagnosisResult,
    ParsedContract,
    PriorityLevel,
)


class MarginReportTemplate:
    """Render a margin diagnosis result into a structured report dict."""

    def render(
        self,
        diagnosis_result: MarginDiagnosisResult,
        contract: ParsedContract | None = None,
    ) -> dict[str, Any]:
        """Return a dict with named report sections.

        Sections
        --------
        - executive_summary
        - contract_overview
        - billability_assessment
        - leakage_analysis
        - penalty_exposure
        - recovery_plan
        - evidence_chain
        - audit_trail
        """
        return {
            "executive_summary": self._render_executive_summary(diagnosis_result),
            "contract_overview": self._render_contract_overview(contract),
            "billability_assessment": self._render_billability(diagnosis_result.billability),
            "leakage_analysis": self._render_leakage(diagnosis_result.leakage_triggers),
            "penalty_exposure": self._render_penalty_exposure(diagnosis_result),
            "recovery_plan": self._render_recovery_plan(diagnosis_result.recovery_recommendations),
            "evidence_chain": self._render_evidence_chain(diagnosis_result.evidence_bundle),
            "audit_trail": self._render_audit_trail(diagnosis_result),
        }

    # ------------------------------------------------------------------
    # Section renderers
    # ------------------------------------------------------------------

    @staticmethod
    def _render_executive_summary(result: MarginDiagnosisResult) -> dict[str, Any]:
        total_leakage = sum(t.estimated_impact_value for t in result.leakage_triggers)
        total_recovery = sum(r.estimated_recovery_value for r in result.recovery_recommendations)
        critical_triggers = [
            t
            for t in result.leakage_triggers
            if t.severity in (PriorityLevel.critical, PriorityLevel.high)
        ]
        return {
            "verdict": result.verdict,
            "confidence": result.confidence,
            "summary_text": result.executive_summary or "No executive summary available.",
            "total_leakage_value": round(total_leakage, 2),
            "total_recovery_potential": round(total_recovery, 2),
            "penalty_exposure": round(result.penalty_exposure, 2),
            "critical_trigger_count": len(critical_triggers),
            "recommendation_count": len(result.recovery_recommendations),
            "evidence_completeness": result.evidence_bundle.completeness_score(),
        }

    @staticmethod
    def _render_contract_overview(contract: ParsedContract | None) -> dict[str, Any]:
        if contract is None:
            return {
                "available": False,
                "title": "",
                "parties": [],
                "contract_type": "",
                "effective_date": None,
                "expiry_date": None,
                "clause_count": 0,
                "sla_count": 0,
                "rate_card_count": 0,
            }
        return {
            "available": True,
            "title": contract.title,
            "parties": contract.parties,
            "contract_type": contract.contract_type.value,
            "effective_date": contract.effective_date.isoformat()
            if contract.effective_date
            else None,
            "expiry_date": contract.expiry_date.isoformat() if contract.expiry_date else None,
            "governing_law": contract.governing_law,
            "payment_terms": contract.payment_terms,
            "clause_count": len(contract.clauses),
            "sla_count": len(contract.sla_table),
            "rate_card_count": len(contract.rate_card),
            "obligation_count": len(contract.obligations),
            "penalty_count": len(contract.penalties),
            "scope_boundary_count": len(contract.scope_boundaries),
        }

    @staticmethod
    def _render_billability(decision: BillabilityDecision) -> dict[str, Any]:
        return {
            "billable": decision.billable,
            "category": decision.category.value,
            "rate_applied": decision.rate_applied,
            "confidence": decision.confidence,
            "reasons": decision.reasons,
            "rule_results": {
                rule: {"passed": passed, "status": "PASS" if passed else "FAIL"}
                for rule, passed in decision.rule_results.items()
            },
            "evidence_refs": decision.evidence_refs,
            "rules_passed": sum(1 for v in decision.rule_results.values() if v),
            "rules_total": len(decision.rule_results),
        }

    @staticmethod
    def _render_leakage(triggers: list[LeakageTrigger]) -> dict[str, Any]:
        by_severity: dict[str, list[dict[str, Any]]] = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
        }
        total_impact = 0.0
        for t in triggers:
            entry = {
                "trigger_type": t.trigger_type,
                "description": t.description,
                "estimated_impact": t.estimated_impact_value,
                "clause_refs": t.clause_refs,
                "evidence": t.evidence,
            }
            by_severity.get(t.severity.value, by_severity["medium"]).append(entry)
            total_impact += t.estimated_impact_value

        return {
            "total_triggers": len(triggers),
            "total_impact_value": round(total_impact, 2),
            "by_severity": by_severity,
            "trigger_types": list({t.trigger_type for t in triggers}),
        }

    @staticmethod
    def _render_penalty_exposure(result: MarginDiagnosisResult) -> dict[str, Any]:
        return {
            "total_exposure": round(result.penalty_exposure, 2),
            "trigger_count": len(
                [
                    t
                    for t in result.leakage_triggers
                    if t.trigger_type == "penalty_exposure_unmitigated"
                ]
            ),
            "at_risk": result.penalty_exposure > 0,
        }

    @staticmethod
    def _render_recovery_plan(
        recommendations: list[CommercialRecoveryRecommendation],
    ) -> dict[str, Any]:
        by_type: dict[str, list[dict[str, Any]]] = {}
        total_value = 0.0
        for rec in recommendations:
            entry = {
                "description": rec.description,
                "estimated_value": rec.estimated_recovery_value,
                "priority": rec.priority.value,
                "confidence": rec.confidence,
                "evidence_refs": rec.evidence_clause_refs,
            }
            key = rec.recommendation_type.value
            by_type.setdefault(key, []).append(entry)
            total_value += rec.estimated_recovery_value

        return {
            "total_recommendations": len(recommendations),
            "total_recovery_value": round(total_value, 2),
            "by_type": by_type,
            "top_3": [
                {
                    "type": r.recommendation_type.value,
                    "description": r.description[:120],
                    "value": r.estimated_recovery_value,
                }
                for r in recommendations[:3]
            ],
        }

    @staticmethod
    def _render_evidence_chain(bundle: CommercialEvidenceBundle) -> dict[str, Any]:
        return {
            "completeness_score": bundle.completeness_score(),
            "contract_evidence": bundle.contract_evidence,
            "work_order_evidence": bundle.work_order_evidence,
            "execution_evidence": bundle.execution_evidence,
            "billing_evidence": bundle.billing_evidence,
            "gaps": bundle.gaps,
            "gap_count": len(bundle.gaps),
            "total_items": (
                len(bundle.contract_evidence)
                + len(bundle.work_order_evidence)
                + len(bundle.execution_evidence)
                + len(bundle.billing_evidence)
            ),
        }

    @staticmethod
    def _render_audit_trail(result: MarginDiagnosisResult) -> dict[str, Any]:
        return {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "verdict": result.verdict,
            "confidence": result.confidence,
            "rules_evaluated": list(result.billability.rule_results.keys()),
            "leakage_triggers_detected": len(result.leakage_triggers),
            "recommendations_generated": len(result.recovery_recommendations),
            "evidence_gaps": result.evidence_bundle.gaps,
        }
