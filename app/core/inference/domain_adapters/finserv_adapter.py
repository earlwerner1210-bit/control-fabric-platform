"""
Financial Services Domain SLM Adapter

Regulatory coverage:
  - FCA SYSC (Senior Management Arrangements, Systems and Controls)
  - PRA Operational Resilience Policy Statement
  - Basel III / CRD V — operational risk requirements
  - MiFID II Article 16 — organisational requirements
  - DORA (Digital Operational Resilience Act) — ICT risk management
"""

from __future__ import annotations

import logging

from app.core.inference.slm_router import (
    DomainHypothesisEnrichment,
    DomainSLMAdapter,
    SLMContext,
)

logger = logging.getLogger(__name__)


class FinServSLMAdapter(DomainSLMAdapter):
    adapter_id = "finserv-v1"
    domain_name = "financial_services"
    supported_planes = ["operations", "compliance", "risk", "security"]
    supported_object_types = [
        "regulatory_mandate",
        "compliance_requirement",
        "risk_control",
        "domain_pack_extension",
        "operational_policy",
    ]

    FCA_MAPPINGS = {
        "change": ("FCA SYSC 8.1 — systems and controls for outsourcing and material changes"),
        "incident": (
            "FCA SYSC 15A — operational resilience — impact tolerances and incident reporting"
        ),
        "access_control": ("FCA SYSC 13.9 — information security controls for regulated firms"),
        "model_risk": ("FCA SS1/23 — model risk management principles for banks"),
        "release": ("FCA SYSC 8.1.1R — adequate arrangements for change management"),
    }

    DORA_MAPPINGS = {
        "release": (
            "DORA Article 8 — ICT risk management framework — change management procedures"
        ),
        "incident": (
            "DORA Article 17 — ICT-related incident management, classification and reporting"
        ),
        "third_party": ("DORA Article 28 — ICT third-party risk management"),
        "resilience": ("DORA Article 11 — business continuity policy for ICT"),
    }

    REQUIRED_EVIDENCE = {
        "production_release": [
            "change_request",
            "impact_assessment",
            "approver_sign_off",
            "rollback_plan",
        ],
        "model_change": [
            "model_validation_report",
            "governance_approval",
            "backtesting_evidence",
        ],
        "access_change": ["access_review_record", "four_eyes_approval"],
    }

    def can_handle(self, context: SLMContext) -> bool:
        if any(r in ["FCA", "PRA", "DORA", "MiFID", "Basel"] for r in context.regulatory_context):
            return True
        return super().can_handle(context)

    def enrich_hypothesis(
        self,
        hypothesis_text: str,
        context: SLMContext,
        control_objects: list[dict],
    ) -> DomainHypothesisEnrichment:
        enrichment = DomainHypothesisEnrichment()
        text_lower = hypothesis_text.lower()

        all_mappings = {**self.FCA_MAPPINGS, **self.DORA_MAPPINGS}
        for key, citation in all_mappings.items():
            if key in text_lower:
                enrichment.regulation_citations.append(citation)

        for action_type, evidence_types in self.REQUIRED_EVIDENCE.items():
            normalised = action_type.replace("_", " ")
            if normalised in text_lower or action_type in text_lower:
                enrichment.prescribed_evidence_types.extend(evidence_types)

        if "release" in text_lower and ("production" in text_lower or "live" in text_lower):
            enrichment.domain_specific_risk = (
                "FCA-regulated firms must demonstrate adequate change management"
                " controls under SYSC 8. DORA Article 8 requires ICT change"
                " management procedures with documented approval chains."
                " A production release without four-eyes approval and impact"
                " assessment may constitute a regulatory breach."
            )
            enrichment.confidence_boost = 0.2

        if enrichment.regulation_citations:
            enrichment.specific_clause = enrichment.regulation_citations[0]
            first_ref = enrichment.regulation_citations[0].split("—")[0].strip()
            evidence_list = ", ".join(enrichment.prescribed_evidence_types[:2])
            enrichment.remediation_precision = (
                f"Per {first_ref}: ensure {evidence_list} are provided"
                f" and linked to this release before submitting"
                f" to the governance gate."
            )

        return enrichment

    def get_regulatory_context(self, plane: str, object_types: list[str]) -> list[str]:
        return ["FCA SYSC", "DORA", "PRA Operational Resilience", "Basel III OpRisk"]
