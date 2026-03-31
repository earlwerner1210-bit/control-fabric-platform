"""
Semiconductor / High-Tech Domain SLM Adapter

Regulatory coverage:
  - ITAR (International Traffic in Arms Regulations) — 22 CFR Parts 120-130
  - EAR (Export Administration Regulations) — 15 CFR Parts 730-774
  - SEMI S2/S10 — Equipment Safety and Risk Assessment
  - JEDEC Standards — reliability and qualification
  - US CHIPS Act 2022 — funding guardrails
  - EU Chips Act 2023/1781
  - IP protection — trade secrets, patents, NDA compliance
"""

from __future__ import annotations

import logging

from app.core.inference.slm_router import (
    DomainHypothesisEnrichment,
    DomainSLMAdapter,
    SLMContext,
)

logger = logging.getLogger(__name__)


class SemiconductorSLMAdapter(DomainSLMAdapter):
    adapter_id = "semiconductor-v1"
    domain_name = "semiconductor"
    supported_planes = [
        "operations",
        "compliance",
        "security",
        "supply_chain",
        "ip_governance",
        "export_control",
    ]
    supported_object_types = [
        "technical_control",
        "regulatory_mandate",
        "compliance_requirement",
        "risk_control",
        "domain_pack_extension",
    ]

    ITAR_MAPPINGS = {
        "export": (
            "ITAR 22 CFR Part 120 — defence articles and services require State Department"
            " authorisation before export, re-export, or transfer to foreign persons"
        ),
        "technical_data": (
            "ITAR 22 CFR 120.33 — technical data controlled under ITAR must not be disclosed"
            " to foreign nationals without licence or applicable exemption"
        ),
        "deemed_export": (
            "ITAR 22 CFR 120.54 — release of controlled technical data to a foreign national"
            " in the US constitutes a deemed export requiring authorisation"
        ),
        "retransfer": (
            "ITAR 22 CFR 123.9 — retransfer of ITAR-controlled items or data to third"
            " countries requires prior written approval from State Department"
        ),
        "record_keeping": (
            "ITAR 22 CFR 122.5 — records of exports, re-exports, and disclosures must be"
            " retained for 5 years"
        ),
    }

    EAR_MAPPINGS = {
        "eccn": (
            "EAR 15 CFR Part 774 — items on the Commerce Control List require export licence"
            " based on ECCN and destination; classification must be current"
        ),
        "denied_party": (
            "EAR 15 CFR Part 744 — exports, re-exports, and transfers to denied parties,"
            " entities, and unverified persons are prohibited; screening required"
        ),
        "technology_transfer": (
            "EAR 15 CFR 734.13 — release of controlled technology to foreign nationals"
            " requires authorisation; deemed export rules apply"
        ),
        "de_minimis": (
            "EAR 15 CFR 734.4 — de minimis rule: foreign-made products incorporating US"
            " content above threshold subject to EAR"
        ),
    }

    SEMI_MAPPINGS = {
        "equipment_change": (
            "SEMI S2 Section 6 — changes to semiconductor equipment must be assessed for"
            " environmental health and safety impact before installation"
        ),
        "chemical": (
            "SEMI S2 Section 10 — chemical management: changes to chemicals used in process"
            " must be assessed; SDS review and exposure assessment required"
        ),
        "risk_assessment": (
            "SEMI S10 — risk assessment must be performed and documented for new or changed"
            " semiconductor manufacturing equipment"
        ),
        "esd": (
            "ANSI/ESD S20.20 — ESD control programme: changes to process or handling must"
            " be assessed for ESD impact; requalification may be required"
        ),
    }

    JEDEC_MAPPINGS = {
        "qualification": (
            "JEDEC JEP001 / JESD47 — component and process changes require qualification"
            " testing; change notification to customers may be required"
        ),
        "reliability": (
            "JEDEC JESD94 — application-specific qualification standard: reliability tests"
            " must be completed before production use of changed process"
        ),
        "pcn": (
            "JEDEC JEP671 — product change notification required before implementing"
            " changes that affect form, fit, or function of qualified components"
        ),
        "die_change": (
            "JEDEC JESD47 — die revision changes require full qualification unless waiver"
            " approved; customer approval for controlled changes"
        ),
    }

    IP_MAPPINGS = {
        "trade_secret": (
            "Defend Trade Secrets Act / UK Trade Secrets Regulations 2018 — technical IP"
            " must be protected; disclosure controls required before release"
        ),
        "patent": (
            "USPTO / EPO filing requirements — public disclosure before patent filing"
            " creates prior art; IP review required before any public release"
        ),
        "nda": (
            "NDA compliance — technical data shared with third parties must be covered"
            " by active NDA; disclosure tracking required"
        ),
        "open_source": (
            "Open source licence compliance — any code incorporating GPL/LGPL must be"
            " reviewed before product release; licence obligations must be met"
        ),
    }

    CHIPS_ACT_MAPPINGS = {
        "funding": (
            "US CHIPS Act Section 9902 — recipients of CHIPS funding must not expand"
            " semiconductor manufacturing capacity in countries of concern for 10 years"
        ),
        "technology_sharing": (
            "US CHIPS Act guardrail provisions — technology sharing agreements with"
            " covered entities require notification to Commerce Department"
        ),
        "eu_chips": (
            "EU Chips Act Article 7 — first-of-a-kind facilities receiving state aid must"
            " notify Commission of significant production changes"
        ),
    }

    REQUIRED_EVIDENCE = {
        "export": [
            "export_licence_or_exemption",
            "ecn_classification_record",
            "denied_party_screening",
            "transaction_record",
        ],
        "technical_disclosure": [
            "itar_ear_review",
            "ip_clearance",
            "nda_in_place",
            "deemed_export_assessment",
        ],
        "process_change": [
            "semi_s2_assessment",
            "jedec_pcn_if_required",
            "customer_notification",
            "qualification_data",
        ],
        "equipment_change": [
            "semi_s10_risk_assessment",
            "ehs_review",
            "installation_qualification",
            "safety_sign_off",
        ],
        "ip_release": [
            "patent_clearance",
            "trade_secret_review",
            "nda_signed",
            "export_control_check",
        ],
        "chips_funding": [
            "guardrail_compliance_check",
            "country_of_concern_review",
            "commerce_notification_if_required",
        ],
    }

    def can_handle(self, context: SLMContext) -> bool:
        if any(
            r in ["ITAR", "EAR", "SEMI", "JEDEC", "CHIPS", "EAR99", "ECCN"]
            for r in context.regulatory_context
        ):
            return True
        if context.operational_plane in ["export_control", "ip_governance"]:
            return True
        return super().can_handle(context)

    def enrich_hypothesis(
        self,
        hypothesis_text: str,
        context: SLMContext,
        control_objects: list[dict],
    ) -> DomainHypothesisEnrichment:
        ft_enrichment = self._try_finetuned_model(hypothesis_text, context)
        if ft_enrichment is not None:
            return ft_enrichment

        return self._rule_based_enrichment(hypothesis_text, context)

    def _try_finetuned_model(
        self,
        hypothesis_text: str,
        context: SLMContext,
    ) -> DomainHypothesisEnrichment | None:
        try:
            from app.core.inference.domain_adapters.model_loader import DomainModelLoader

            loader = DomainModelLoader.instance()
            model = loader.load("semiconductor")
            if not model.is_loaded:
                return None

            prompt = (
                f"Assess governance risk for semiconductor operation:\n"
                f"Plane: {context.operational_plane}\n"
                f"Hypothesis: {hypothesis_text}\n"
                f"Identify: regulatory citations, required evidence,"
                f" risk level, remediation steps."
            )
            result = loader.generate(model, prompt, max_tokens=512)
            if result is None:
                return None

            enrichment = DomainHypothesisEnrichment()
            result_lower = result.lower()

            for key, citation in {
                **self.ITAR_MAPPINGS,
                **self.EAR_MAPPINGS,
                **self.JEDEC_MAPPINGS,
            }.items():
                if key in result_lower or key.replace("_", " ") in result_lower:
                    enrichment.regulation_citations.append(citation)

            if enrichment.regulation_citations:
                enrichment.specific_clause = enrichment.regulation_citations[0]
                enrichment.confidence_boost = 0.25

            logger.info("Semiconductor adapter used fine-tuned model for enrichment")
            return enrichment
        except Exception as e:
            logger.warning("Fine-tuned model failed, falling back to rules: %s", e)
            return None

    def _rule_based_enrichment(
        self,
        hypothesis_text: str,
        context: SLMContext,
    ) -> DomainHypothesisEnrichment:
        enrichment = DomainHypothesisEnrichment()
        text_lower = hypothesis_text.lower()

        for key, citation in {
            **self.ITAR_MAPPINGS,
            **self.EAR_MAPPINGS,
            **self.SEMI_MAPPINGS,
            **self.JEDEC_MAPPINGS,
            **self.IP_MAPPINGS,
            **self.CHIPS_ACT_MAPPINGS,
        }.items():
            if key in text_lower or key.replace("_", " ") in text_lower:
                enrichment.regulation_citations.append(citation)

        for action_type, evidence_types in self.REQUIRED_EVIDENCE.items():
            if action_type.replace("_", " ") in text_lower:
                enrichment.prescribed_evidence_types.extend(
                    ev for ev in evidence_types if ev not in enrichment.prescribed_evidence_types
                )

        if "export" in text_lower or "foreign" in text_lower or "transfer" in text_lower:
            enrichment.domain_specific_risk = (
                "Export control violations under ITAR and EAR carry severe penalties: up to"
                " $1M per violation and criminal prosecution. Deemed export rules mean even"
                " showing controlled technical data to a foreign national on US soil requires"
                " authorisation. Immediate export control review required."
            )
            enrichment.confidence_boost = 0.25

        if (
            "ip" in text_lower or "patent" in text_lower or "trade secret" in text_lower
        ) and "release" in text_lower:
            enrichment.domain_specific_risk = (
                "Public disclosure of technical information before patent filing creates"
                " prior art and destroys patent rights in most jurisdictions. Trade secret"
                " disclosure without NDA coverage can permanently destroy trade secret"
                " protection under UK Trade Secrets Regulations 2018."
            )
            enrichment.confidence_boost = 0.22

        if enrichment.regulation_citations:
            enrichment.specific_clause = enrichment.regulation_citations[0]
            primary = enrichment.regulation_citations[0].split(" — ")[0]
            enrichment.remediation_precision = (
                f"Per {primary}: complete"
                f" {', '.join(enrichment.prescribed_evidence_types[:3])}"
                f" before this action proceeds. Export control and IP reviews"
                f" are non-negotiable."
            )

        return enrichment

    def get_regulatory_context(self, plane: str, object_types: list[str]) -> list[str]:
        return [
            "ITAR 22 CFR",
            "EAR 15 CFR",
            "SEMI S2/S10",
            "JEDEC JESD47",
            "US CHIPS Act",
            "EU Chips Act 2023",
        ]
