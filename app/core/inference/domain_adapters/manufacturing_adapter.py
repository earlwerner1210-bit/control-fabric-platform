"""
Manufacturing Domain SLM Adapter

Regulatory coverage:
  - ISO 9001:2015 — Quality Management Systems
  - IATF 16949:2016 — Automotive Quality Management
  - IEC 62443 — Industrial Automation and Control Systems Security
  - ISO 45001:2018 — Occupational Health and Safety
  - OSHA Process Safety Management (PSM) 29 CFR 1910.119
  - EU Machinery Directive 2006/42/EC
"""

from __future__ import annotations

import logging

from app.core.inference.slm_router import (
    DomainHypothesisEnrichment,
    DomainSLMAdapter,
    SLMContext,
)

logger = logging.getLogger(__name__)


class ManufacturingSLMAdapter(DomainSLMAdapter):
    adapter_id = "manufacturing-v1"
    domain_name = "manufacturing"
    supported_planes = ["operations", "quality", "safety", "compliance", "supply_chain"]
    supported_object_types = [
        "technical_control",
        "risk_control",
        "regulatory_mandate",
        "compliance_requirement",
        "domain_pack_extension",
    ]

    ISO9001_MAPPINGS = {
        "change": (
            "ISO 9001:2015 Clause 8.5.6 — changes to production or service provision"
            " must be controlled; records of changes must be retained"
        ),
        "nonconformance": (
            "ISO 9001:2015 Clause 8.7 — nonconforming outputs must be identified,"
            " controlled, and documented; root cause analysis required"
        ),
        "supplier": (
            "ISO 9001:2015 Clause 8.4 — externally provided processes, products, and"
            " services must be controlled; supplier qualification records required"
        ),
        "design": (
            "ISO 9001:2015 Clause 8.3 — design and development controls must be applied;"
            " design changes must be reviewed, verified, and validated"
        ),
        "calibration": (
            "ISO 9001:2015 Clause 7.1.5 — monitoring and measuring resources must be"
            " calibrated; calibration records must be maintained"
        ),
        "training": (
            "ISO 9001:2015 Clause 7.2 — competence of personnel performing"
            " quality-affecting work must be documented and maintained"
        ),
        "audit": (
            "ISO 9001:2015 Clause 9.2 — internal audits must be conducted at planned"
            " intervals; audit findings must be addressed"
        ),
    }

    IATF_MAPPINGS = {
        "ppap": (
            "IATF 16949:2016 / AIAG PPAP — production part approval required before"
            " production shipment of new or changed parts"
        ),
        "fmea": (
            "IATF 16949:2016 Clause 8.3.3 — DFMEA and PFMEA must be updated when"
            " design or process changes occur"
        ),
        "control_plan": (
            "IATF 16949:2016 Clause 8.5.1.1 — control plans must be updated for any"
            " process changes; customer notification may be required"
        ),
        "customer_approval": (
            "IATF 16949:2016 Clause 8.3.4.4 — customer approval required before"
            " implementing changes to manufacturing process"
        ),
    }

    IEC62443_MAPPINGS = {
        "ics_change": (
            "IEC 62443-2-3 — patch management for IACS: patches must be assessed and"
            " approved before deployment to industrial control systems"
        ),
        "network": (
            "IEC 62443-3-3 — network segmentation and zone/conduit model must be"
            " maintained; changes require security impact assessment"
        ),
        "access": (
            "IEC 62443-2-1 — access control for IACS: privileged access changes require"
            " documented authorisation and audit trail"
        ),
        "vulnerability": (
            "IEC 62443-2-4 — IACS service providers must have documented process for"
            " vulnerability disclosure and remediation"
        ),
    }

    SAFETY_MAPPINGS = {
        "moc": (
            "OSHA PSM 29 CFR 1910.119(l) — management of change procedure required;"
            " PSM MOC must be completed before any process change"
        ),
        "pha": (
            "OSHA PSM 29 CFR 1910.119(e) — process hazard analysis must be updated"
            " to reflect process changes within defined intervals"
        ),
        "hazardous": (
            "OSHA PSM / ATEX Directive 2014/34/EU — changes involving hazardous substances"
            " or explosive atmospheres require safety case review"
        ),
    }

    REQUIRED_EVIDENCE = {
        "production_change": [
            "engineering_change_order",
            "pfmea_update",
            "control_plan_update",
            "process_validation",
            "customer_approval_if_required",
        ],
        "new_supplier": [
            "supplier_qualification_audit",
            "ppap_approved",
            "quality_agreement",
            "approved_supplier_list_update",
        ],
        "software_release": [
            "software_validation_report",
            "ics_security_assessment",
            "change_control_record",
            "patch_approval",
        ],
        "safety_change": [
            "psm_moc_form",
            "pha_update",
            "safety_integrity_level_assessment",
            "hazop_sign_off",
        ],
        "product_change": [
            "design_change_notice",
            "dfmea_update",
            "customer_notification",
            "requalification_evidence",
        ],
    }

    def can_handle(self, context: SLMContext) -> bool:
        if any(
            r in ["ISO9001", "IATF", "IEC62443", "ISO14001", "ISO45001", "OSHA", "CE"]
            for r in context.regulatory_context
        ):
            return True
        if context.operational_plane in ["quality", "safety", "supply_chain"]:
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
            model = loader.load("manufacturing")
            if not model.is_loaded:
                return None

            prompt = (
                f"Assess governance risk for manufacturing operation:\n"
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
                **self.ISO9001_MAPPINGS,
                **self.IATF_MAPPINGS,
                **self.IEC62443_MAPPINGS,
            }.items():
                if key in result_lower or key.replace("_", " ") in result_lower:
                    enrichment.regulation_citations.append(citation)

            if enrichment.regulation_citations:
                enrichment.specific_clause = enrichment.regulation_citations[0]
                enrichment.confidence_boost = 0.16

            logger.info("Manufacturing adapter used fine-tuned model for enrichment")
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
            **self.ISO9001_MAPPINGS,
            **self.IATF_MAPPINGS,
            **self.IEC62443_MAPPINGS,
            **self.SAFETY_MAPPINGS,
        }.items():
            if key in text_lower or key.replace("_", " ") in text_lower:
                enrichment.regulation_citations.append(citation)

        for action_type, evidence_types in self.REQUIRED_EVIDENCE.items():
            if action_type.replace("_", " ") in text_lower:
                enrichment.prescribed_evidence_types.extend(
                    ev for ev in evidence_types if ev not in enrichment.prescribed_evidence_types
                )

        if "production" in text_lower and "change" in text_lower:
            enrichment.domain_specific_risk = (
                "Production changes without controlled change management violate ISO"
                " 9001:2015 Clause 8.5.6 and IATF 16949 customer-specific requirements."
                " Automotive customers may require PPAP resubmission and production freeze"
                " until approval is obtained."
            )
            enrichment.confidence_boost = 0.16

        if enrichment.regulation_citations:
            enrichment.specific_clause = enrichment.regulation_citations[0]
            primary = enrichment.regulation_citations[0].split(" — ")[0]
            enrichment.remediation_precision = (
                f"Per {primary}: complete"
                f" {', '.join(enrichment.prescribed_evidence_types[:3])}"
                f" before implementation."
            )

        return enrichment

    def get_regulatory_context(self, plane: str, object_types: list[str]) -> list[str]:
        return [
            "ISO 9001:2015",
            "IATF 16949:2016",
            "IEC 62443",
            "ISO 14001:2015",
            "ISO 45001:2018",
        ]
