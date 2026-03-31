"""
Regulatory Corpus Scraper

Fetches regulatory documents for SLM fine-tuning:
  - EUR-Lex (NIS2, DORA, CRD)
  - FCA Handbook sections
  - Ofcom General Conditions
  - Static corpora bundled with domain packs
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CorpusDocument:
    """A single regulatory document in the corpus."""

    doc_id: str
    title: str
    source: str
    domain: str
    text: str
    url: str = ""
    scraped_at: str = ""
    section_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "source": self.source,
            "domain": self.domain,
            "text": self.text,
            "url": self.url,
            "scraped_at": self.scraped_at,
            "section_refs": self.section_refs,
        }


EURLEX_DOCUMENTS = {
    "telecom": [
        {
            "celex": "32022L2555",
            "title": "NIS2 Directive",
            "articles": [21, 23, 24],
        },
        {
            "celex": "32022R2554",
            "title": "DORA Regulation",
            "articles": [8, 11, 17, 28],
        },
    ],
    "financial_services": [
        {
            "celex": "32022R2554",
            "title": "DORA Regulation",
            "articles": [8, 11, 17, 28],
        },
        {
            "celex": "32013R0575",
            "title": "CRR — Capital Requirements Regulation",
            "articles": [85, 312, 313],
        },
    ],
}

STATIC_CORPORA = {
    "telecom": {
        "NIS2 Article 21(2)(b)": (
            "Incident handling: Essential entities shall adopt appropriate and proportionate"
            " technical, operational and organisational measures to manage the risks posed to"
            " the security of network and information systems, including incident handling."
        ),
        "NIS2 Article 21(2)(d)": (
            "Supply chain security: including security-related aspects concerning the"
            " relationships between each entity and its direct suppliers or service providers."
        ),
        "NIS2 Article 21(2)(e)": (
            "Security in network and information systems acquisition, development and"
            " maintenance, including vulnerability handling and disclosure."
        ),
        "NIS2 Article 21(2)(i)": (
            "The use of multi-factor authentication or continuous authentication solutions,"
            " secured voice, video and text communications and secured emergency communication"
            " systems within the entity, where appropriate."
        ),
        "NIS2 Article 23": (
            "Reporting obligations: Each Member State shall ensure that essential and important"
            " entities notify, without undue delay, the CSIRT or competent authority of any"
            " significant incident. An early warning within 24 hours, an incident notification"
            " within 72 hours, and a final report not later than one month after submission of"
            " the incident notification."
        ),
        "Ofcom General Condition C4": (
            "Network integrity: Communications providers shall take all necessary measures to"
            " maintain, to the greatest extent possible, uninterrupted access to emergency"
            " organisations and the integrity of the public electronic communications network."
        ),
        "Ofcom General Condition C5": (
            "Security measures: Communications providers shall take appropriate technical and"
            " organisational measures to appropriately manage the risks posed to the security"
            " of public electronic communications networks and publicly available electronic"
            " communications services."
        ),
        "3GPP TS 32.600": (
            "Configuration Management (CM): This specification defines the Integration"
            " Reference Point for configuration management including network element"
            " provisioning, change management, and software management."
        ),
        "GSMA FS.13": (
            "Security Accreditation Scheme: Framework for assessing the security of mobile"
            " network elements and services. Covers security assessment methodology, risk"
            " assessment, and security controls validation."
        ),
    },
    "financial_services": {
        "FCA SYSC 8.1": (
            "Outsourcing requirements: A firm must take reasonable steps to avoid undue"
            " additional operational risk when outsourcing important operational functions."
            " A firm must not undertake the outsourcing of important operational functions"
            " in such a way as to impair materially the quality of its internal control and"
            " the ability of the FCA to monitor the firm's compliance."
        ),
        "FCA SYSC 13.9": (
            "Information security: A firm should establish and maintain appropriate systems"
            " and controls for managing its information security risks, including policies"
            " and procedures covering access controls, encryption, and security monitoring."
        ),
        "FCA SYSC 15A": (
            "Operational resilience: Firms must identify their important business services,"
            " set impact tolerances, and carry out mapping and scenario testing to ensure"
            " they can remain within impact tolerances during severe but plausible disruptions."
        ),
        "DORA Article 8": (
            "ICT risk management framework: Financial entities shall have in place an"
            " internal governance and control framework that ensures an effective and prudent"
            " management of ICT risk. The management body shall define, approve, oversee and"
            " be accountable for the implementation of the ICT risk management framework."
        ),
        "DORA Article 17": (
            "ICT-related incident management: Financial entities shall define, establish and"
            " implement an ICT-related incident management process to detect, manage and"
            " notify ICT-related incidents. Financial entities shall classify ICT-related"
            " incidents according to criteria including the criticality of the services"
            " affected and the duration of the incident."
        ),
        "PRA SS1/21": (
            "Operational resilience: Firms should identify their important business services"
            " from the perspective of the risk of harm that disruption could cause to"
            " consumers, market integrity, or policyholder protection."
        ),
    },
    "legal": {
        "SRA Code of Conduct 2019 Para 6.1": (
            "Conflicts of interest: You must not act if there is an own interest conflict or"
            " a significant risk of such a conflict. You must not act in a matter where there"
            " is a conflict between the interests of two or more clients unless the clients"
            " have a substantially common interest and the conditions are met."
        ),
        "MLR 2017 Regulation 27": (
            "Customer Due Diligence: A relevant person must apply customer due diligence"
            " measures when establishing a business relationship, or carrying out an occasional"
            " transaction. CDD measures must be applied before carrying out a transaction and"
            " before establishing a business relationship."
        ),
        "POCA 2002 Section 330": (
            "Failure to disclose: A person commits an offence if they know or suspect, or have"
            " reasonable grounds for knowing or suspecting, that another person is engaged in"
            " money laundering, and the information came to them in the course of their work in"
            " the regulated sector, and they do not disclose the information to a nominated"
            " officer or the National Crime Agency as soon as is practicable."
        ),
        "UK GDPR Article 5": (
            "Principles relating to processing of personal data: Personal data shall be"
            " processed lawfully, fairly and in a transparent manner. Personal data shall be"
            " collected for specified, explicit and legitimate purposes. Personal data shall be"
            " adequate, relevant and limited to what is necessary."
        ),
        "SRA Accounts Rules 2019 Rule 2.1": (
            "Client money must be kept separate from money belonging to the authorised body."
            " Client money must be kept in a client account. Client accounts must be"
            " reconciled at least every five weeks."
        ),
        "SRA Code of Conduct 2019 Para 4.2": (
            "Supervision: You must not act where you are unable to provide competent legal"
            " services. You must only act if you have adequate supervision in place."
        ),
    },
    "healthcare": {
        "FDA 21 CFR Part 11.10": (
            "Controls for closed systems: Persons who use closed systems to create, modify,"
            " maintain, or transmit electronic records shall employ procedures and controls"
            " designed to ensure the authenticity, integrity, and confidentiality of electronic"
            " records. System validation, audit trails, and access controls are required."
        ),
        "FDA 21 CFR Part 820.30": (
            "Design controls: Each manufacturer of any class II or class III device shall"
            " establish and maintain procedures to control the design of the device. Design"
            " input, output, review, verification, validation, transfer, and changes are all"
            " required elements."
        ),
        "EU MDR 2017/745 Article 61": (
            "Clinical evaluation: Manufacturers shall plan, continuously conduct and document"
            " a clinical evaluation. The evaluation shall follow a defined and methodologically"
            " sound procedure based on clinical data."
        ),
        "HIPAA Security Rule 45 CFR 164.312": (
            "Technical safeguards: A covered entity must implement reasonable and appropriate"
            " administrative, physical, and technical safeguards to protect ePHI. Access"
            " controls, audit controls, integrity controls, and transmission security required."
        ),
        "ICH E6(R2) Section 5.5": (
            "Quality management: The sponsor is responsible for implementing and maintaining"
            " quality assurance and quality control systems with written SOPs to ensure trials"
            " are conducted in compliance with the protocol, GCP, and regulatory requirements."
        ),
    },
    "banking": {
        "BCBS 239 Principle 3": (
            "Accuracy and integrity of risk data: A bank should be able to generate accurate"
            " and reliable risk data to meet normal and stress reporting accuracy requirements."
            " Data should be aggregated on a largely automated basis. Automated reconciliation"
            " controls should be in place."
        ),
        "SR 11-7 Section II": (
            "Model validation: Validation is a set of processes and activities intended to"
            " verify that models are performing as expected, in line with their design"
            " objectives and business uses. Independent review is a key mechanism for ensuring"
            " that models are conceptually sound."
        ),
        "Basel III Pillar 2 ICAAP": (
            "Internal capital adequacy assessment: Banks must have a process for assessing"
            " their overall capital adequacy in relation to their risk profile and a strategy"
            " for maintaining capital levels. Material changes to business model or risk"
            " profile require reassessment."
        ),
        "UK SMCR Senior Managers Regime": (
            "Senior managers are personally accountable for the areas of the firm falling"
            " within their prescribed responsibilities. Any material regulatory failure within"
            " a senior manager's area of responsibility may lead to personal regulatory action."
        ),
    },
    "insurance": {
        "Solvency II Article 45": (
            "Own risk and solvency assessment: Every insurance and reinsurance undertaking"
            " shall conduct its own risk and solvency assessment. The assessment shall include"
            " overall solvency needs, compliance with capital requirements, and significance"
            " of deviations from SCR assumptions."
        ),
        "Solvency II Article 112": (
            "Internal model approval: Undertakings may calculate the SCR using an internal"
            " model. Major changes to the model require prior supervisory approval. The"
            " undertaking must have a major and minor model change policy."
        ),
        "Lloyd's Minimum Standards MS14": (
            "Delegated authority: Managing agents must maintain effective oversight and control"
            " of all delegated authority arrangements. Coverholder performance monitoring must"
            " be conducted regularly. Coverholder audits must be current."
        ),
        "FCA ICOBS 8.1": (
            "Claims handling: A firm must handle claims promptly and fairly. A firm must not"
            " unreasonably reject a claim. Where a claim is declined in whole or part, the firm"
            " must provide a clear explanation of the reasons."
        ),
    },
    "manufacturing": {
        "ISO 9001:2015 Clause 8.5.6": (
            "Control of changes: The organization shall review and control changes for"
            " production or service provision. Documented information describing the results"
            " of the review, the person authorizing the change, and any necessary actions"
            " arising from the review must be retained."
        ),
        "IATF 16949:2016 Clause 8.3.4.4": (
            "Product approval process: The organization shall comply with the applicable"
            " customer product and manufacturing process approval procedure. Documented product"
            " approval before shipment required if specified by the customer."
        ),
        "IEC 62443-2-3": (
            "Patch management in IACS environment: Patches to industrial automation and"
            " control systems shall be assessed before deployment. The assessment shall"
            " determine the potential impact on the IACS. Deployment procedures shall include"
            " backout plans."
        ),
        "OSHA PSM 29 CFR 1910.119(l)": (
            "Management of change: The employer shall establish and implement written"
            " procedures to manage changes to process chemicals, technology, equipment, and"
            " procedures. Information must be transmitted to affected employees before startup."
        ),
    },
    "semiconductor": {
        "ITAR 22 CFR Part 120.33": (
            "Technical data definition and control: Technical data means information required"
            " for the design, development, production, or modification of defense articles."
            " Controlled technical data may not be exported or released to a foreign person"
            " without a licence or applicable exemption."
        ),
        "EAR 15 CFR Part 734.13": (
            "Export and deemed export controls: A release of technology subject to the EAR to"
            " a foreign national in the United States constitutes a deemed export. Most"
            " semiconductor technology classified under ECCN 3E001 requires a licence."
        ),
        "SEMI S2 Section 6": (
            "Equipment change assessment: Changes to semiconductor manufacturing equipment"
            " shall be assessed for environmental, health, and safety impact prior to"
            " implementation. Documentation and approval by EHS qualified personnel required."
        ),
        "JEDEC JESD47": (
            "Stress-test driven qualification: Components and processes used in semiconductor"
            " manufacturing shall be qualified to applicable JEDEC standards before production."
            " Process changes affecting reliability shall trigger requalification."
        ),
        "US CHIPS Act Section 9902": (
            "Guardrail provisions: Recipients of CHIPS Act funding shall not engage in any"
            " significant transaction involving material expansion of semiconductor"
            " manufacturing capacity in a country of concern for a period of 10 years."
        ),
    },
}


class RegulatoryCorpusScraper:
    """
    Scrapes regulatory documents for SLM fine-tuning.

    Modes:
      - static: Uses bundled corpus text (always available)
      - live: Attempts EUR-Lex API fetch, falls back to static
    """

    def __init__(
        self,
        domain: str = "telecom",
        output_dir: str = "slm/corpus/raw",
        mode: str = "static",
    ) -> None:
        self.domain = domain
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        self.documents: list[CorpusDocument] = []

    def scrape(self) -> list[CorpusDocument]:
        """Run the scraper. Returns list of corpus documents."""
        logger.info("Scraping %s corpus (mode=%s)", self.domain, self.mode)

        if self.mode == "live":
            self._scrape_eurlex()

        self._load_static_corpus()
        self._save_corpus()

        logger.info("Corpus complete: %d documents", len(self.documents))
        return self.documents

    def _scrape_eurlex(self) -> None:
        """Attempt to fetch from EUR-Lex. Graceful fallback on failure."""
        docs = EURLEX_DOCUMENTS.get(self.domain, [])
        if not docs:
            logger.info("No EUR-Lex documents configured for domain %s", self.domain)
            return

        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed — skipping live EUR-Lex scrape")
            return

        for doc_ref in docs:
            celex = doc_ref["celex"]
            try:
                url = (
                    f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}&format=TEXT"
                )
                with httpx.Client(timeout=30) as client:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        text = resp.text[:50000]
                        doc_id = hashlib.sha256(f"{celex}:{self.domain}".encode()).hexdigest()[:16]
                        self.documents.append(
                            CorpusDocument(
                                doc_id=doc_id,
                                title=doc_ref["title"],
                                source="EUR-Lex",
                                domain=self.domain,
                                text=text,
                                url=url,
                                scraped_at=datetime.now(UTC).isoformat(),
                                section_refs=[f"Article {a}" for a in doc_ref["articles"]],
                            )
                        )
                        logger.info("Fetched EUR-Lex: %s (%s)", doc_ref["title"], celex)
                    else:
                        logger.warning("EUR-Lex returned %d for %s", resp.status_code, celex)
            except Exception as e:
                logger.warning("EUR-Lex fetch failed for %s: %s", celex, e)

    def _load_static_corpus(self) -> None:
        """Load bundled static corpus texts."""
        corpus = STATIC_CORPORA.get(self.domain, {})
        existing_titles = {d.title for d in self.documents}

        for ref, text in corpus.items():
            if ref in existing_titles:
                continue
            doc_id = hashlib.sha256(f"static:{self.domain}:{ref}".encode()).hexdigest()[:16]
            self.documents.append(
                CorpusDocument(
                    doc_id=doc_id,
                    title=ref,
                    source="static_corpus",
                    domain=self.domain,
                    text=text,
                    scraped_at=datetime.now(UTC).isoformat(),
                    section_refs=[ref],
                )
            )

    def _save_corpus(self) -> None:
        """Save corpus to JSON file."""
        output_file = self.output_dir / f"{self.domain}_corpus.json"
        data = [doc.to_dict() for doc in self.documents]
        output_file.write_text(json.dumps(data, indent=2))
        logger.info("Saved corpus to %s (%d docs)", output_file, len(data))

    @property
    def document_count(self) -> int:
        return len(self.documents)

    def get_training_texts(self) -> list[str]:
        """Return plain text list for training input."""
        return [doc.text for doc in self.documents]
