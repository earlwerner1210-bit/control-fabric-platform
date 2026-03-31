"""
Insurance Domain SLM Adapter

Regulatory coverage:
  - Solvency II Directive 2009/138/EC — Pillar 1/2/3
  - Lloyd's Minimum Standards — LMA/LCM requirements
  - FCA ICOBS (Insurance Conduct of Business Sourcebook)
  - IFRS 17 — Insurance Contracts (accounting standard)
  - PRA Supervisory Statement SS19/15 — internal model approval
  - Insurance Distribution Directive (IDD) 2016/97
"""

from __future__ import annotations

import logging

from app.core.inference.slm_router import (
    DomainHypothesisEnrichment,
    DomainSLMAdapter,
    SLMContext,
)

logger = logging.getLogger(__name__)


class InsuranceSLMAdapter(DomainSLMAdapter):
    adapter_id = "insurance-v1"
    domain_name = "insurance"
    supported_planes = ["compliance", "risk", "operations", "actuarial"]
    supported_object_types = [
        "regulatory_mandate",
        "risk_control",
        "compliance_requirement",
        "domain_pack_extension",
        "operational_policy",
    ]

    SOLVENCY2_MAPPINGS = {
        "scr": (
            "Solvency II Article 101 — Solvency Capital Requirement must be recalculated"
            " after material changes to risk profile; PRA notification required"
        ),
        "orsa": (
            "Solvency II Article 45 — Own Risk and Solvency Assessment must reflect any"
            " material change to risk profile within the assessment period"
        ),
        "internal_model": (
            "Solvency II Article 112 — material model changes require PRA pre-approval;"
            " major model change policy must be approved by Board"
        ),
        "governance": (
            "Solvency II Article 41 — effective system of governance required; key function"
            " holders must be notified of material changes"
        ),
        "reporting": (
            "Solvency II Articles 35/51 — supervisory reporting (RSR/QRT) must be accurate;"
            " material errors require immediate correction and disclosure"
        ),
        "reinsurance": (
            "Solvency II Articles 210-214 — reinsurance contracts must be assessed for"
            " risk transfer effectiveness; credit risk must be captured in SCR"
        ),
        "outsourcing": (
            "Solvency II Article 49 — material outsourcing arrangements require board"
            " approval and PRA notification; exit strategy must exist"
        ),
    }

    LLOYDS_MAPPINGS = {
        "syndicate": (
            "Lloyd's Minimum Standards MS7 — material changes to syndicate business plan"
            " require Lloyd's approval via Approval of Plan process"
        ),
        "delegated": (
            "Lloyd's Minimum Standards MS14 — delegated authority arrangements require"
            " Lloyd's approval; coverholder audits must be current"
        ),
        "underwriting": (
            "Lloyd's Minimum Standards MS1 — underwriting controls must be documented;"
            " appetite changes require Board and Lloyd's sign-off"
        ),
        "claims": (
            "Lloyd's Minimum Standards MS2 — claims handling changes must be documented;"
            " material procedure changes require managing agent approval"
        ),
    }

    ICOBS_MAPPINGS = {
        "product": (
            "FCA ICOBS 2.5 / PS20/16 — product governance: products must deliver fair"
            " value to target market; annual review required"
        ),
        "disclosure": (
            "FCA ICOBS 6 — information about the insurance product must be provided to"
            " customers before conclusion of the contract"
        ),
        "claims_handling": (
            "FCA ICOBS 8 — claims must be handled promptly and fairly; delays must be"
            " justified and communicated to policyholders"
        ),
        "renewal": (
            "FCA ICOBS 2.6 — renewal pricing transparency required; customers must be"
            " informed of price history at renewal"
        ),
    }

    IFRS17_MAPPINGS = {
        "measurement": (
            "IFRS 17 — insurance contract measurement must reflect current estimates;"
            " changes to assumptions require disclosure"
        ),
        "csm": (
            "IFRS 17 Contractual Service Margin — CSM adjustments require documented"
            " basis changes approved through actuarial governance"
        ),
    }

    REQUIRED_EVIDENCE = {
        "model_change": [
            "major_model_change_assessment",
            "pra_pre_approval_if_required",
            "board_approval",
            "independent_validation",
        ],
        "product_change": [
            "product_governance_review",
            "fair_value_assessment",
            "target_market_review",
            "distribution_review",
        ],
        "outsourcing": [
            "outsourcing_risk_assessment",
            "board_approval",
            "pra_notification_if_material",
            "exit_strategy_document",
        ],
        "regulatory_reporting": [
            "data_quality_sign_off",
            "actuarial_certification",
            "cfo_attestation",
            "reconciliation_evidence",
        ],
        "claims_procedure": [
            "procedure_change_record",
            "fair_treatment_assessment",
            "compliance_sign_off",
        ],
    }

    def can_handle(self, context: SLMContext) -> bool:
        if any(
            r in ["Solvency", "Lloyd's", "ICOBS", "IFRS17", "IDD", "IAIS"]
            for r in context.regulatory_context
        ):
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
            model = loader.load("insurance")
            if not model.is_loaded:
                return None

            prompt = (
                f"Assess governance risk for insurance operation:\n"
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
                **self.SOLVENCY2_MAPPINGS,
                **self.LLOYDS_MAPPINGS,
            }.items():
                if key in result_lower or key.replace("_", " ") in result_lower:
                    enrichment.regulation_citations.append(citation)

            if enrichment.regulation_citations:
                enrichment.specific_clause = enrichment.regulation_citations[0]
                enrichment.confidence_boost = 0.22

            logger.info("Insurance adapter used fine-tuned model for enrichment")
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
            **self.SOLVENCY2_MAPPINGS,
            **self.LLOYDS_MAPPINGS,
            **self.ICOBS_MAPPINGS,
            **self.IFRS17_MAPPINGS,
        }.items():
            if key in text_lower or key.replace("_", " ") in text_lower:
                enrichment.regulation_citations.append(citation)

        for action_type, evidence_types in self.REQUIRED_EVIDENCE.items():
            if action_type.replace("_", " ") in text_lower:
                enrichment.prescribed_evidence_types.extend(
                    ev for ev in evidence_types if ev not in enrichment.prescribed_evidence_types
                )

        if "internal model" in text_lower or "scr model" in text_lower:
            enrichment.domain_specific_risk = (
                "Changes to the internal model used to calculate SCR under Solvency II"
                " require pre-approval from PRA for major changes. Deploying model changes"
                " without approval constitutes a breach of the Internal Model Approval"
                " Process (IMAP) conditions."
            )
            enrichment.confidence_boost = 0.22

        if enrichment.regulation_citations:
            enrichment.specific_clause = enrichment.regulation_citations[0]
            primary = enrichment.regulation_citations[0].split(" — ")[0]
            enrichment.remediation_precision = (
                f"Per {primary}: provide"
                f" {', '.join(enrichment.prescribed_evidence_types[:3])}"
                f" before this action proceeds."
            )

        return enrichment

    def get_regulatory_context(self, plane: str, object_types: list[str]) -> list[str]:
        return [
            "Solvency II",
            "Lloyd's Minimum Standards",
            "FCA ICOBS",
            "IFRS 17",
            "PRA SS19/15",
        ]
