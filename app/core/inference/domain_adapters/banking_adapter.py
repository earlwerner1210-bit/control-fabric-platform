"""
Banking Domain SLM Adapter

Regulatory coverage:
  - Basel III / CRD V — capital adequacy and operational risk
  - BCBS 239 — risk data aggregation and risk reporting
  - SR 11-7 — Model Risk Management (US Federal Reserve)
  - CCAR / Stress Testing — capital planning
  - PRA SS3/19 — model risk management
  - UK SMCR (Senior Managers and Certification Regime)
  - CRR II (Capital Requirements Regulation)
"""

from __future__ import annotations

import logging

from app.core.inference.slm_router import (
    DomainHypothesisEnrichment,
    DomainSLMAdapter,
    SLMContext,
)

logger = logging.getLogger(__name__)


class BankingSLMAdapter(DomainSLMAdapter):
    adapter_id = "banking-v1"
    domain_name = "banking"
    supported_planes = ["operations", "risk", "compliance", "security"]
    supported_object_types = [
        "regulatory_mandate",
        "risk_control",
        "compliance_requirement",
        "domain_pack_extension",
        "operational_policy",
    ]

    BASEL_MAPPINGS = {
        "capital": (
            "Basel III / CRR II Article 92 — minimum capital requirements; changes to"
            " RWA models require IRB approval from PRA"
        ),
        "operational_risk": (
            "Basel III Operational Risk Framework — losses from inadequate internal"
            " processes must be captured in OR loss database"
        ),
        "model": (
            "Basel III / PRA SS3/19 — material model changes require model risk"
            " governance sign-off before production deployment"
        ),
        "stress_test": (
            "CCAR / Bank of England Stress Testing — scenarios must be documented"
            " and approved; model changes between cycles require disclosure"
        ),
        "rwa": (
            "CRR II Article 143 — internal model approaches require prior permission"
            " from competent authority for material changes"
        ),
        "liquidity": (
            "Basel III LCR / NSFR — liquidity risk models must be approved through"
            " model risk framework before use in regulatory reporting"
        ),
    }

    BCBS239_MAPPINGS = {
        "data": (
            "BCBS 239 Principle 2 — data architecture and IT infrastructure must fully"
            " support risk data aggregation in both normal and stress periods"
        ),
        "aggregation": (
            "BCBS 239 Principle 3 — risk data aggregation capabilities must be accurate,"
            " timely, and adaptable to supervisory requirements"
        ),
        "reporting": (
            "BCBS 239 Principle 6 — risk reports must be accurate and precise; material"
            " errors must be documented and escalated"
        ),
        "reconciliation": (
            "BCBS 239 Principle 4 — risk data must be complete and based on a single"
            " authoritative source; reconciliation evidence required"
        ),
        "timeliness": (
            "BCBS 239 Principle 5 — banks must be able to generate aggregate risk data"
            " on an ad hoc basis; latency must be minimised"
        ),
    }

    SR117_MAPPINGS = {
        "model_change": (
            "SR 11-7 / PRA SS3/19 — model changes must go through full model risk"
            " management process: development, validation, approval, monitoring"
        ),
        "validation": (
            "SR 11-7 Section II — independent model validation required for all material"
            " models before production deployment"
        ),
        "inventory": (
            "SR 11-7 Section IV — comprehensive model inventory must include all models,"
            " their owners, validators, and current status"
        ),
        "model_risk": (
            "SR 11-7 Section I — effective challenge of model conceptual soundness,"
            " ongoing monitoring, and outcome analysis required"
        ),
    }

    SMCR_MAPPINGS = {
        "accountability": (
            "UK SMCR — Senior Manager responsible for material decisions must be"
            " identified and their approval documented"
        ),
        "certification": (
            "FCA SMCR Certification Regime — individuals in certification functions"
            " must be assessed annually as fit and proper"
        ),
        "conduct": (
            "FCA Code of Conduct (COCON) — Senior Managers must take reasonable steps"
            " to ensure compliance with FCA requirements"
        ),
    }

    REQUIRED_EVIDENCE = {
        "model_change": [
            "model_change_request",
            "independent_validation_report",
            "model_risk_committee_approval",
            "backtesting_results",
        ],
        "capital_model": [
            "pra_ird_approval",
            "qis_results",
            "internal_audit_sign_off",
            "stress_test_evidence",
        ],
        "production_release": [
            "change_control_record",
            "senior_manager_approval",
            "technology_risk_assessment",
            "rollback_plan",
        ],
        "risk_report": [
            "data_quality_check",
            "reconciliation_evidence",
            "sign_off_record",
            "variance_analysis",
        ],
        "regulatory_submission": [
            "validation_certificate",
            "senior_manager_attestation",
            "data_lineage_documentation",
        ],
    }

    def can_handle(self, context: SLMContext) -> bool:
        if any(
            r in ["Basel", "BCBS", "SR11-7", "CRD", "CRR", "SMCR", "PRA", "EBA"]
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
            model = loader.load("banking")
            if not model.is_loaded:
                return None

            prompt = (
                f"Assess governance risk for banking operation:\n"
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
                **self.BASEL_MAPPINGS,
                **self.BCBS239_MAPPINGS,
                **self.SR117_MAPPINGS,
            }.items():
                if key in result_lower or key.replace("_", " ") in result_lower:
                    enrichment.regulation_citations.append(citation)

            if enrichment.regulation_citations:
                enrichment.specific_clause = enrichment.regulation_citations[0]
                enrichment.confidence_boost = 0.20

            logger.info("Banking adapter used fine-tuned model for enrichment")
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
            **self.BASEL_MAPPINGS,
            **self.BCBS239_MAPPINGS,
            **self.SR117_MAPPINGS,
            **self.SMCR_MAPPINGS,
        }.items():
            if key in text_lower or key.replace("_", " ") in text_lower:
                enrichment.regulation_citations.append(citation)

        for action_type, evidence_types in self.REQUIRED_EVIDENCE.items():
            if action_type.replace("_", " ") in text_lower:
                enrichment.prescribed_evidence_types.extend(
                    ev for ev in evidence_types if ev not in enrichment.prescribed_evidence_types
                )

        if "model" in text_lower and (
            "change" in text_lower or "update" in text_lower or "release" in text_lower
        ):
            enrichment.domain_specific_risk = (
                "Model changes in regulated banking environments require SR 11-7 / PRA"
                " SS3/19 compliant model risk management. Deploying a changed model without"
                " independent validation and Model Risk Committee approval constitutes a"
                " material control failure."
            )
            enrichment.confidence_boost = 0.20

        if enrichment.regulation_citations:
            enrichment.specific_clause = enrichment.regulation_citations[0]
            primary = enrichment.regulation_citations[0].split(" — ")[0]
            enrichment.remediation_precision = (
                f"Per {primary}: complete"
                f" {', '.join(enrichment.prescribed_evidence_types[:3])} before release."
            )

        return enrichment

    def get_regulatory_context(self, plane: str, object_types: list[str]) -> list[str]:
        return [
            "Basel III",
            "BCBS 239",
            "SR 11-7",
            "CRD V / CRR II",
            "PRA SS3/19",
            "UK SMCR",
        ]
