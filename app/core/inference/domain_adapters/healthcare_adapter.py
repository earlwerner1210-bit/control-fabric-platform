"""
Healthcare Domain SLM Adapter

Regulatory coverage:
  - FDA 21 CFR Part 11 — electronic records and signatures
  - FDA 21 CFR Part 820 — Quality System Regulation (QSR) / QMSR
  - FDA 21 CFR Part 803 — Medical Device Reporting (MDR)
  - EU MDR 2017/745 — Medical Device Regulation
  - HIPAA Privacy Rule (45 CFR Part 164)
  - HIPAA Security Rule (45 CFR Part 164.300)
  - ICH E6(R2) — Good Clinical Practice
  - NHS Data Security and Protection Toolkit
"""

from __future__ import annotations

import logging

from app.core.inference.slm_router import (
    DomainHypothesisEnrichment,
    DomainSLMAdapter,
    SLMContext,
)

logger = logging.getLogger(__name__)


class HealthcareSLMAdapter(DomainSLMAdapter):
    adapter_id = "healthcare-v1"
    domain_name = "healthcare"
    supported_planes = ["compliance", "operations", "risk", "security", "quality"]
    supported_object_types = [
        "regulatory_mandate",
        "compliance_requirement",
        "technical_control",
        "risk_control",
        "domain_pack_extension",
        "quality_record",
    ]

    FDA_MAPPINGS = {
        "software": (
            "FDA 21 CFR Part 11.10 — software used in regulated operations must be validated"
            " to ensure accuracy, reliability, and consistent intended performance"
        ),
        "electronic_record": (
            "FDA 21 CFR Part 11.10(a) — systems that create, modify, maintain, or transmit"
            " electronic records must be validated"
        ),
        "audit_trail": (
            "FDA 21 CFR Part 11.10(e) — audit trails must be computer-generated and include"
            " date and time of operator entries and actions"
        ),
        "change_control": (
            "FDA 21 CFR Part 820.70(b) — changes to production processes must be verified"
            " or validated and documented before implementation"
        ),
        "design_change": (
            "FDA 21 CFR Part 820.30(i) — design changes must be identified, documented,"
            " validated or verified, reviewed, and approved before implementation"
        ),
        "capa": (
            "FDA 21 CFR Part 820.100 — corrective and preventive action procedures must"
            " be established and documented"
        ),
        "release": (
            "FDA 21 CFR Part 820.80 — finished device acceptance activities must be"
            " documented and completed before release"
        ),
        "adverse_event": (
            "FDA 21 CFR Part 803.50 — manufacturers must report adverse events to FDA"
            " within 30 calendar days of becoming aware"
        ),
    }

    MDR_MAPPINGS = {
        "clinical_evidence": (
            "EU MDR 2017/745 Article 61 — clinical evaluation must be based on sufficient"
            " clinical evidence; technical file must be current"
        ),
        "pms": (
            "EU MDR 2017/745 Article 83 — post-market surveillance system must be"
            " established and maintained for each device"
        ),
        "vigilance": (
            "EU MDR 2017/745 Article 87 — serious incidents must be reported to competent"
            " authority without delay and within 15 days"
        ),
        "technical_file": (
            "EU MDR 2017/745 Article 10(4) — technical documentation must be updated"
            " whenever a change is made to the device"
        ),
    }

    HIPAA_MAPPINGS = {
        "phi": (
            "HIPAA Privacy Rule 45 CFR 164.502 — protected health information may only"
            " be used or disclosed as permitted; authorisation required"
        ),
        "access": (
            "HIPAA Security Rule 45 CFR 164.312(a) — access controls must be implemented"
            " to allow only authorised users to access ePHI"
        ),
        "encryption": (
            "HIPAA Security Rule 45 CFR 164.312(e)(2) — encryption of ePHI in transit"
            " is an addressable implementation specification"
        ),
        "breach": (
            "HIPAA Breach Notification Rule 45 CFR 164.400 — covered entities must notify"
            " affected individuals within 60 days of discovery"
        ),
        "baa": (
            "HIPAA 45 CFR 164.504(e) — business associate agreements must be in place"
            " before sharing PHI with third parties"
        ),
        "minimum_necessary": (
            "HIPAA Privacy Rule 45 CFR 164.502(b) — minimum necessary standard applies"
            " to all uses and disclosures of PHI"
        ),
    }

    GCP_MAPPINGS = {
        "protocol": (
            "ICH E6(R2) Section 8 — protocol amendments must be approved by IRB/IEC"
            " and sponsor before implementation"
        ),
        "informed_consent": (
            "ICH E6(R2) Section 4.8 — informed consent must be obtained before any"
            " trial-specific procedures are conducted"
        ),
        "data_integrity": (
            "ICH E6(R2) Section 5.5 — sponsor must implement quality management system"
            " to ensure clinical data integrity"
        ),
    }

    REQUIRED_EVIDENCE = {
        "software_release": [
            "validation_protocol",
            "validation_report",
            "iq_oq_pq_evidence",
            "21_cfr_11_compliance_checklist",
        ],
        "device_change": [
            "design_change_request",
            "risk_assessment",
            "verification_validation_report",
            "technical_file_update",
        ],
        "clinical_trial_change": [
            "protocol_amendment",
            "irb_iec_approval",
            "informed_consent_update",
            "regulatory_notification",
        ],
        "phi_access": [
            "access_authorisation_record",
            "minimum_necessary_justification",
            "baa_in_place",
        ],
        "production_release": [
            "change_control_record",
            "capa_if_required",
            "qa_release_authorisation",
            "gmp_compliance_check",
        ],
        "adverse_event": [
            "adverse_event_report",
            "risk_benefit_assessment",
            "regulatory_submission_evidence",
        ],
    }

    def can_handle(self, context: SLMContext) -> bool:
        if any(
            r in ["FDA", "HIPAA", "MDR", "GCP", "MHRA", "NHS", "CQC", "ICH"]
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
            model = loader.load("healthcare")
            if not model.is_loaded:
                return None

            prompt = (
                f"Assess governance risk for healthcare operation:\n"
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

            for key, citation in {**self.FDA_MAPPINGS, **self.HIPAA_MAPPINGS}.items():
                if key in result_lower or key.replace("_", " ") in result_lower:
                    enrichment.regulation_citations.append(citation)

            if enrichment.regulation_citations:
                enrichment.specific_clause = enrichment.regulation_citations[0]
                enrichment.confidence_boost = 0.20

            logger.info("Healthcare adapter used fine-tuned model for enrichment")
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
            **self.FDA_MAPPINGS,
            **self.MDR_MAPPINGS,
            **self.HIPAA_MAPPINGS,
            **self.GCP_MAPPINGS,
        }.items():
            if key in text_lower or key.replace("_", " ") in text_lower:
                enrichment.regulation_citations.append(citation)

        for action_type, evidence_types in self.REQUIRED_EVIDENCE.items():
            if action_type.replace("_", " ") in text_lower:
                enrichment.prescribed_evidence_types.extend(
                    ev for ev in evidence_types if ev not in enrichment.prescribed_evidence_types
                )

        if "software" in text_lower and ("release" in text_lower or "change" in text_lower):
            enrichment.domain_specific_risk = (
                "Software changes in regulated healthcare environments require validated"
                " systems under FDA 21 CFR Part 11. Unvalidated software releases can result"
                " in FDA 483 observations, warning letters, or consent decrees."
            )
            enrichment.confidence_boost = 0.20

        if "patient" in text_lower and ("data" in text_lower or "record" in text_lower):
            enrichment.domain_specific_risk = (
                "Unauthorised use or disclosure of protected health information (PHI)"
                " constitutes a HIPAA violation. Penalties range from $100 to $50,000 per"
                " violation. The breach notification rule requires patient notification"
                " within 60 days."
            )
            enrichment.confidence_boost = 0.18

        if enrichment.regulation_citations:
            enrichment.specific_clause = enrichment.regulation_citations[0]
            primary = enrichment.regulation_citations[0].split(" — ")[0]
            enrichment.remediation_precision = (
                f"Per {primary}: complete"
                f" {', '.join(enrichment.prescribed_evidence_types[:3])}"
                f" before proceeding with this action."
            )

        return enrichment

    def get_regulatory_context(self, plane: str, object_types: list[str]) -> list[str]:
        return [
            "FDA 21 CFR Part 11",
            "FDA 21 CFR Part 820",
            "EU MDR 2017/745",
            "HIPAA",
            "ICH E6(R2)",
            "NHS DSPT",
        ]
