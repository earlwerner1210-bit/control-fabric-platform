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
