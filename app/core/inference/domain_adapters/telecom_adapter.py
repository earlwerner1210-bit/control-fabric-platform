"""
Telecom Domain SLM Adapter

Enriches governance hypotheses with telecom-specific regulatory knowledge:
  - NIS2 Directive (EU) — cybersecurity risk management for operators
  - Ofcom General Conditions — UK telecom operator obligations
  - 3GPP standards — network release and change management
  - GSMA guidelines — security accreditation for mobile operators
"""

from __future__ import annotations

import logging

from app.core.inference.slm_router import (
    DomainHypothesisEnrichment,
    DomainSLMAdapter,
    SLMContext,
)

logger = logging.getLogger(__name__)


class TelecomSLMAdapter(DomainSLMAdapter):
    adapter_id = "telecom-v1"
    domain_name = "telecommunications"
    supported_planes = ["operations", "security", "network", "compliance"]
    supported_object_types = [
        "domain_pack_extension",
        "technical_control",
        "risk_control",
        "compliance_requirement",
        "regulatory_mandate",
        "security_control",
    ]

    NIS2_MAPPINGS = {
        "network_change": (
            "NIS2 Article 21(2)(b) — incident handling and business continuity for network changes"
        ),
        "security_scan": (
            "NIS2 Article 21(2)(e) — security in network and information systems"
            " acquisition, development and maintenance"
        ),
        "vulnerability": ("NIS2 Article 21(2)(e) — vulnerability handling and disclosure"),
        "access_control": (
            "NIS2 Article 21(2)(i) — use of multi-factor authentication and secure communications"
        ),
        "incident": ("NIS2 Article 23 — reporting obligations for significant incidents"),
        "supply_chain": "NIS2 Article 21(2)(d) — supply chain security",
    }

    OFCOM_MAPPINGS = {
        "network_change": (
            "Ofcom General Condition C4 — network reliability and quality of service obligations"
        ),
        "security": (
            "Ofcom General Condition C5 — security measures"
            " for public electronic communications networks"
        ),
        "incident": (
            "Ofcom Security Breach Reporting — mandatory notification"
            " within 24 hours for significant breaches"
        ),
    }

    REQUIRED_EVIDENCE = {
        "production_release": [
            "ci_result",
            "security_scan",
            "network_impact_assessment",
            "rollback_plan",
        ],
        "network_change": [
            "change_request",
            "network_impact_assessment",
            "maintenance_window_approval",
        ],
        "security_control": [
            "security_scan",
            "penetration_test",
            "remediation_evidence",
        ],
    }

    def can_handle(self, context: SLMContext) -> bool:
        if any(r in ["NIS2", "Ofcom", "3GPP", "GSMA"] for r in context.regulatory_context):
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

        for key, citation in self.NIS2_MAPPINGS.items():
            if key in text_lower or key.replace("_", " ") in text_lower:
                enrichment.regulation_citations.append(citation)

        for key, citation in self.OFCOM_MAPPINGS.items():
            if key in text_lower:
                enrichment.regulation_citations.append(citation)

        for action_type, evidence_types in self.REQUIRED_EVIDENCE.items():
            if action_type in text_lower:
                enrichment.prescribed_evidence_types.extend(evidence_types)

        if "production" in text_lower and "release" in text_lower:
            enrichment.domain_specific_risk = (
                "Production network releases carry NIS2 Article 21 obligations. "
                "A release without documented network impact assessment and"
                " rollback plan constitutes a reportable security incident"
                " if service is disrupted."
            )
            enrichment.confidence_boost = 0.15

        if enrichment.regulation_citations:
            first_ref = enrichment.regulation_citations[0].split("—")[0].strip()
            evidence_list = ", ".join(enrichment.prescribed_evidence_types[:3])
            enrichment.remediation_precision = (
                f"To satisfy {first_ref}: provide {evidence_list}"
                f" as evidence references before submitting to the release gate."
            )
            enrichment.specific_clause = enrichment.regulation_citations[0]

        logger.debug(
            "Telecom adapter enriched hypothesis with %d citations",
            len(enrichment.regulation_citations),
        )
        return enrichment

    def get_regulatory_context(self, plane: str, object_types: list[str]) -> list[str]:
        frameworks = ["NIS2", "Ofcom"]
        if "network" in plane or "operations" in plane:
            frameworks.extend(["3GPP TS 32.600", "GSMA FS.13"])
        return frameworks
