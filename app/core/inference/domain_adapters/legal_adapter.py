"""
Legal Domain SLM Adapter

Regulatory coverage:
  - SRA Code of Conduct 2019 (Solicitors Regulation Authority)
  - Money Laundering Regulations 2017 (MLR 2017)
  - Proceeds of Crime Act 2002 (POCA) — AML obligations
  - Legal Services Act 2007 — regulated activities
  - GDPR / Data Protection Act 2018 — client data handling
  - Bar Standards Board (BSB) Handbook — barristers
  - SRA Accounts Rules 2019 — client money handling
  - Solicitor-client confidentiality — legal privilege
"""

from __future__ import annotations

import logging

from app.core.inference.slm_router import (
    DomainHypothesisEnrichment,
    DomainSLMAdapter,
    SLMContext,
)

logger = logging.getLogger(__name__)


class LegalSLMAdapter(DomainSLMAdapter):
    adapter_id = "legal-v1"
    domain_name = "legal_services"
    supported_planes = ["compliance", "operations", "risk", "security"]
    supported_object_types = [
        "regulatory_mandate",
        "compliance_requirement",
        "operational_policy",
        "risk_control",
        "domain_pack_extension",
    ]

    SRA_MAPPINGS = {
        "conflict": (
            "SRA Code of Conduct 2019 Paragraph 6.1 — obligation to identify and manage"
            " conflicts of interest before and during a matter"
        ),
        "supervision": (
            "SRA Code of Conduct 2019 Paragraph 4.2 — obligation to maintain effective"
            " supervision of all work carried out for clients"
        ),
        "client_money": (
            "SRA Accounts Rules 2019 Rule 2.1 — client money must be held in a designated"
            " client account and reconciled monthly"
        ),
        "confidentiality": (
            "SRA Code of Conduct 2019 Paragraph 6.3 — duty to keep client affairs"
            " confidential unless disclosure is required or permitted by law"
        ),
        "disclosure": (
            "SRA Code of Conduct 2019 Paragraph 3.1 — duty to make clients aware of"
            " information material to their matter"
        ),
        "competence": (
            "SRA Code of Conduct 2019 Paragraph 3.2 — obligation to ensure work is completed"
            " by persons with appropriate skills and experience"
        ),
        "cdd": (
            "SRA AML Practice Note — client due diligence must be completed and documented"
            " before acting for a new client"
        ),
        "file": (
            "SRA Quality and Practice Standards — matter files must contain evidence of"
            " supervision and compliance checks"
        ),
    }

    AML_MAPPINGS = {
        "aml": (
            "Money Laundering Regulations 2017 Regulation 27 — mandatory customer due"
            " diligence before establishing business relationship"
        ),
        "source_of_funds": (
            "Money Laundering Regulations 2017 Regulation 28 — enhanced due diligence"
            " required where higher risk of money laundering"
        ),
        "suspicious": (
            "Proceeds of Crime Act 2002 Section 330 — obligation to report known or"
            " suspected money laundering to MLRO"
        ),
        "pep": (
            "Money Laundering Regulations 2017 Regulation 35 — enhanced due diligence"
            " mandatory for politically exposed persons"
        ),
        "sanctions": (
            "UK Financial Sanctions — prohibition on dealing with sanctioned individuals;"
            " must check HM Treasury consolidated sanctions list"
        ),
    }

    GDPR_MAPPINGS = {
        "data": (
            "UK GDPR Article 5 — personal data must be processed lawfully, fairly, and"
            " in a transparent manner"
        ),
        "retention": (
            "UK GDPR Article 5(1)(e) — personal data must not be kept longer than necessary"
            " for the purpose for which it was collected"
        ),
        "dsar": (
            "UK GDPR Article 12 — data subject access requests must be responded to"
            " within one calendar month"
        ),
        "breach": (
            "UK GDPR Article 33 — personal data breaches must be reported to ICO"
            " within 72 hours of becoming aware"
        ),
        "transfer": (
            "UK GDPR Chapter V — personal data transfers outside UK require appropriate safeguards"
        ),
        "consent": (
            "UK GDPR Article 7 — consent must be freely given, specific, informed, and unambiguous"
        ),
    }

    REQUIRED_EVIDENCE = {
        "new_client": [
            "cdd_completion_record",
            "conflict_check_record",
            "client_care_letter",
            "aml_check_record",
        ],
        "client_money": [
            "client_account_reconciliation",
            "ledger_entry",
            "client_authority",
        ],
        "litigation": [
            "disclosure_checklist",
            "privilege_review_record",
            "supervision_sign_off",
        ],
        "data_processing": [
            "privacy_notice_issued",
            "lawful_basis_documented",
            "dpia_if_required",
        ],
        "file_closure": [
            "matter_closure_checklist",
            "client_money_returned",
            "data_retention_applied",
        ],
        "aml": [
            "cdd_completion_record",
            "source_of_funds_evidence",
            "risk_assessment_documented",
        ],
    }

    def can_handle(self, context: SLMContext) -> bool:
        if any(
            r in ["SRA", "AML", "MLR", "BSB", "POCA", "Legal"] for r in context.regulatory_context
        ):
            return True
        return super().can_handle(context)

    def enrich_hypothesis(
        self,
        hypothesis_text: str,
        context: SLMContext,
        control_objects: list[dict],
    ) -> DomainHypothesisEnrichment:
        # Try fine-tuned model first
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
            model = loader.load("legal")
            if not model.is_loaded:
                return None

            prompt = (
                f"Assess governance risk for legal operation:\n"
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

            for key, citation in {**self.SRA_MAPPINGS, **self.AML_MAPPINGS}.items():
                if key in result_lower or key.replace("_", " ") in result_lower:
                    enrichment.regulation_citations.append(citation)

            if enrichment.regulation_citations:
                enrichment.specific_clause = enrichment.regulation_citations[0]
                enrichment.confidence_boost = 0.20

            logger.info("Legal adapter used fine-tuned model for enrichment")
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
            **self.SRA_MAPPINGS,
            **self.AML_MAPPINGS,
            **self.GDPR_MAPPINGS,
        }.items():
            if key in text_lower or key.replace("_", " ") in text_lower:
                enrichment.regulation_citations.append(citation)

        for action_type, evidence_types in self.REQUIRED_EVIDENCE.items():
            if action_type.replace("_", " ") in text_lower or action_type in text_lower:
                enrichment.prescribed_evidence_types.extend(
                    ev for ev in evidence_types if ev not in enrichment.prescribed_evidence_types
                )

        if "new client" in text_lower or "new matter" in text_lower or "retainer" in text_lower:
            enrichment.domain_specific_risk = (
                "Accepting instructions without completed CDD and conflict checks exposes"
                " the firm to SRA disciplinary action under the Code of Conduct 2019 and"
                " potential criminal liability under POCA 2002 if the matter involves the"
                " proceeds of crime."
            )
            enrichment.confidence_boost = 0.18

        if "client money" in text_lower or "client account" in text_lower:
            enrichment.domain_specific_risk = (
                "Mishandling client money is the most serious category of SRA breach."
                " Failure to maintain proper client account records can result in"
                " intervention, striking off, and criminal prosecution."
            )
            enrichment.confidence_boost = 0.20

        if enrichment.regulation_citations:
            primary = enrichment.regulation_citations[0].split(" — ")[0]
            evidence_str = ", ".join(enrichment.prescribed_evidence_types[:3])
            enrichment.specific_clause = enrichment.regulation_citations[0]
            enrichment.remediation_precision = (
                f"Per {primary}: provide {evidence_str} as evidence"
                f" and ensure compliance documentation is complete before proceeding."
            )

        logger.debug(
            "Legal adapter: %d citations for hypothesis",
            len(enrichment.regulation_citations),
        )
        return enrichment

    def get_regulatory_context(self, plane: str, object_types: list[str]) -> list[str]:
        return [
            "SRA Code of Conduct 2019",
            "MLR 2017",
            "POCA 2002",
            "UK GDPR",
            "Legal Services Act 2007",
        ]
