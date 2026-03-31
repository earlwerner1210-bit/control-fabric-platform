"""
Synthetic Scenario Generator

Generates training examples for SLM fine-tuning from:
  - Regulatory corpus documents
  - Control object templates
  - Historical governance decisions

Output: JSONL training file with (instruction, input, output) triples.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TrainingExample:
    """A single training example for SLM fine-tuning."""

    instruction: str
    input_text: str
    output_text: str
    domain: str
    scenario_type: str
    regulatory_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "instruction": self.instruction,
            "input": self.input_text,
            "output": self.output_text,
            "domain": self.domain,
            "scenario_type": self.scenario_type,
            "regulatory_refs": self.regulatory_refs,
        }


SCENARIO_TEMPLATES = {
    "telecom": {
        "network_change": {
            "instructions": [
                "Assess the governance risk of this network change request.",
                "Identify regulatory obligations for this network modification.",
                "Determine required evidence for this network change.",
            ],
            "inputs": [
                (
                    "Network change CR-{id}: Upgrade core router firmware in production"
                    " network segment A. Maintenance window: {window}. Rollback plan: {rollback}."
                ),
                (
                    "Network change CR-{id}: Reconfigure BGP peering with transit provider."
                    " Impact: {impact} subscribers. Change window: {window}."
                ),
                (
                    "Network change CR-{id}: Deploy new firewall rules for VoLTE traffic."
                    " Security classification: {classification}. Tested: {tested}."
                ),
            ],
            "output_template": (
                "Risk assessment: {risk_level}\n"
                "Regulatory obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "NIS2 Article 21(2)(b)",
                "Ofcom General Condition C4",
                "3GPP TS 32.600",
            ],
        },
        "security_incident": {
            "instructions": [
                "Classify this security incident under NIS2 reporting requirements.",
                "Determine reporting obligations for this telecom security event.",
                "Assess the severity and reporting timeline for this incident.",
            ],
            "inputs": [
                (
                    "Security incident SI-{id}: Unauthorized access detected on"
                    " network management system. Duration: {duration}. Users affected: {users}."
                ),
                (
                    "Security incident SI-{id}: DDoS attack on DNS infrastructure."
                    " Peak traffic: {traffic}. Service degradation: {degradation}."
                ),
                (
                    "Security incident SI-{id}: Data exfiltration attempt on subscriber"
                    " database. Records potentially accessed: {records}. Contained: {contained}."
                ),
            ],
            "output_template": (
                "NIS2 Classification: {classification}\n"
                "Reporting timeline:\n{timeline}\n"
                "Required notifications: {notifications}\n"
                "Remediation steps: {remediation}"
            ),
            "regulatory_refs": [
                "NIS2 Article 23",
                "Ofcom Security Breach Reporting",
                "GSMA FS.13",
            ],
        },
        "production_release": {
            "instructions": [
                "Evaluate governance readiness for this production release.",
                "Identify missing evidence for this release gate submission.",
                "Assess compliance of this release with telecom regulatory requirements.",
            ],
            "inputs": [
                (
                    "Release REL-{id}: Deploy billing system update v{version}."
                    " CI status: {ci_status}. Security scan: {scan_status}."
                    " Network impact assessment: {nia_status}."
                ),
                (
                    "Release REL-{id}: Core network element software upgrade."
                    " Vendor: {vendor}. Testing: {test_status}."
                    " Rollback plan: {rollback_status}."
                ),
            ],
            "output_template": (
                "Gate readiness: {readiness}\n"
                "Missing evidence: {missing}\n"
                "Regulatory risk: {risk}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "NIS2 Article 21(2)(e)",
                "NIS2 Article 21(2)(b)",
                "Ofcom General Condition C4",
            ],
        },
    },
    "financial_services": {
        "change_management": {
            "instructions": [
                "Assess FCA compliance for this change request.",
                "Identify DORA obligations for this ICT change.",
                "Evaluate governance controls for this system change.",
            ],
            "inputs": [
                (
                    "Change CR-{id}: Update trading platform matching engine."
                    " Impact: {impact} trading pairs. Testing: {test_status}."
                    " Four-eyes approval: {approval_status}."
                ),
                (
                    "Change CR-{id}: Modify AML transaction monitoring rules."
                    " Regulatory driver: {driver}. Model validation: {validation_status}."
                ),
            ],
            "output_template": (
                "FCA compliance: {compliance}\n"
                "DORA obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "FCA SYSC 8.1",
                "DORA Article 8",
                "PRA SS1/21",
            ],
        },
        "incident_response": {
            "instructions": [
                "Classify this ICT incident under DORA reporting requirements.",
                "Determine FCA notification obligations for this incident.",
                "Assess regulatory impact of this operational disruption.",
            ],
            "inputs": [
                (
                    "Incident INC-{id}: Payment processing system outage."
                    " Duration: {duration}. Transactions affected: {transactions}."
                    " Customer impact: {impact}."
                ),
                (
                    "Incident INC-{id}: Cyber attack on internet banking platform."
                    " Attack vector: {vector}. Data compromised: {data_status}."
                    " Containment: {containment}."
                ),
            ],
            "output_template": (
                "DORA classification: {classification}\n"
                "Reporting timeline:\n{timeline}\n"
                "FCA notification: {notification}\n"
                "Remediation plan: {remediation}"
            ),
            "regulatory_refs": [
                "DORA Article 17",
                "FCA SYSC 15A",
                "PRA SS1/21",
            ],
        },
    },
    "legal": {
        "new_client": {
            "instructions": [
                "Assess SRA compliance for this new client onboarding.",
                "Identify AML obligations for this new matter.",
                "Determine required evidence for client due diligence.",
            ],
            "inputs": [
                (
                    "New client matter MAT-{id}: Client onboarding for corporate"
                    " transaction. CDD status: {test_status}. Conflict check: {approval_status}."
                ),
                (
                    "New client retainer MAT-{id}: High-value property transaction."
                    " Source of funds: {validation_status}. PEP check: {tested}."
                ),
            ],
            "output_template": (
                "SRA compliance: {compliance}\n"
                "AML obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "SRA Code of Conduct 2019",
                "MLR 2017 Regulation 27",
                "POCA 2002 Section 330",
            ],
        },
        "data_protection": {
            "instructions": [
                "Assess GDPR compliance for this data processing activity.",
                "Identify data protection obligations for this client matter.",
                "Determine DSAR response requirements.",
            ],
            "inputs": [
                (
                    "DSAR received DSAR-{id}: Data subject access request."
                    " Deadline: {window}. Records identified: {records}."
                ),
                (
                    "Data retention review DR-{id}: Matter files beyond retention"
                    " period. Records: {records}. Exemptions: {tested}."
                ),
            ],
            "output_template": (
                "GDPR compliance: {compliance}\n"
                "Obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "UK GDPR Article 5",
                "UK GDPR Article 12",
                "UK GDPR Article 33",
            ],
        },
    },
    "healthcare": {
        "software_validation": {
            "instructions": [
                "Assess FDA compliance for this software change.",
                "Identify 21 CFR Part 11 obligations for this system update.",
                "Determine validation requirements for this release.",
            ],
            "inputs": [
                (
                    "Software release SWR-{id}: Update to clinical data system."
                    " Validation: {test_status}. Audit trail: {tested}."
                ),
                (
                    "Software release SWR-{id}: Medical device firmware update."
                    " 21 CFR Part 11: {approval_status}. IQ/OQ/PQ: {validation_status}."
                ),
            ],
            "output_template": (
                "FDA compliance: {compliance}\n"
                "21 CFR Part 11 obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "FDA 21 CFR Part 11.10",
                "FDA 21 CFR Part 820.30",
                "EU MDR 2017/745 Article 61",
            ],
        },
        "phi_handling": {
            "instructions": [
                "Assess HIPAA compliance for this PHI access request.",
                "Identify breach notification requirements for this incident.",
                "Determine BAA requirements for this vendor relationship.",
            ],
            "inputs": [
                (
                    "PHI access request PHI-{id}: Vendor access to patient records."
                    " BAA: {approval_status}. Minimum necessary: {tested}."
                ),
                (
                    "Data breach notification BR-{id}: Potential PHI exposure."
                    " Records affected: {records}. Containment: {containment}."
                ),
            ],
            "output_template": (
                "HIPAA compliance: {compliance}\n"
                "Obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "HIPAA 45 CFR 164.502",
                "HIPAA 45 CFR 164.504(e)",
                "HIPAA 45 CFR 164.400",
            ],
        },
    },
    "banking": {
        "model_risk": {
            "instructions": [
                "Assess SR 11-7 compliance for this model change.",
                "Identify BCBS 239 obligations for this risk data change.",
                "Determine model validation requirements.",
            ],
            "inputs": [
                (
                    "Model change MCR-{id}: Update to credit risk model."
                    " Validation: {validation_status}. Backtesting: {test_status}."
                ),
                (
                    "Model change MCR-{id}: Stress test scenario update."
                    " MRC approval: {approval_status}. Documentation: {tested}."
                ),
            ],
            "output_template": (
                "SR 11-7 compliance: {compliance}\n"
                "Model risk obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "SR 11-7 Section II",
                "PRA SS3/19",
                "Basel III / CRR II",
            ],
        },
        "regulatory_reporting": {
            "instructions": [
                "Assess BCBS 239 compliance for this risk report.",
                "Identify data quality obligations for regulatory submission.",
                "Determine senior manager accountability requirements.",
            ],
            "inputs": [
                (
                    "Risk report RPT-{id}: Quarterly risk data submission."
                    " Reconciliation: {test_status}. Data quality: {validation_status}."
                ),
                (
                    "Capital report RPT-{id}: RWA calculation update."
                    " Senior manager attestation: {approval_status}."
                ),
            ],
            "output_template": (
                "BCBS 239 compliance: {compliance}\n"
                "Reporting obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "BCBS 239 Principle 3",
                "BCBS 239 Principle 6",
                "UK SMCR",
            ],
        },
    },
    "insurance": {
        "model_approval": {
            "instructions": [
                "Assess Solvency II compliance for this model change.",
                "Identify PRA notification requirements for this change.",
                "Determine ORSA update requirements.",
            ],
            "inputs": [
                (
                    "Model change IMC-{id}: Internal model update for SCR."
                    " PRA pre-approval: {approval_status}. Board: {tested}."
                ),
                (
                    "ORSA update ORSA-{id}: Risk profile change assessment."
                    " Material change: {classification}. Validation: {validation_status}."
                ),
            ],
            "output_template": (
                "Solvency II compliance: {compliance}\n"
                "PRA obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "Solvency II Article 112",
                "Solvency II Article 45",
                "PRA SS19/15",
            ],
        },
        "product_governance": {
            "instructions": [
                "Assess FCA ICOBS compliance for this product change.",
                "Identify fair value assessment requirements.",
                "Determine claims handling obligations.",
            ],
            "inputs": [
                (
                    "Product change PGR-{id}: Insurance product modification."
                    " Fair value: {validation_status}. Target market: {test_status}."
                ),
                (
                    "Claims procedure CP-{id}: Claims handling process change."
                    " Compliance sign-off: {approval_status}."
                ),
            ],
            "output_template": (
                "FCA ICOBS compliance: {compliance}\n"
                "Obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "FCA ICOBS 2.5",
                "FCA ICOBS 8",
                "FCA PS20/16",
            ],
        },
    },
    "manufacturing": {
        "production_change": {
            "instructions": [
                "Assess ISO 9001 compliance for this production change.",
                "Identify IATF 16949 obligations for this process update.",
                "Determine PPAP requirements for this change.",
            ],
            "inputs": [
                (
                    "Production change ECO-{id}: Manufacturing process modification."
                    " PFMEA: {test_status}. Control plan: {validation_status}."
                ),
                (
                    "Supplier change SCR-{id}: New supplier qualification."
                    " Audit: {approval_status}. PPAP: {tested}."
                ),
            ],
            "output_template": (
                "ISO 9001 compliance: {compliance}\n"
                "IATF obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "ISO 9001:2015 Clause 8.5.6",
                "IATF 16949:2016 / AIAG PPAP",
                "ISO 9001:2015 Clause 8.4",
            ],
        },
        "safety_change": {
            "instructions": [
                "Assess OSHA PSM compliance for this process change.",
                "Identify IEC 62443 obligations for this ICS change.",
                "Determine PHA update requirements.",
            ],
            "inputs": [
                (
                    "Safety change MOC-{id}: Process modification in hazardous area."
                    " PSM MOC: {approval_status}. PHA: {test_status}."
                ),
                (
                    "ICS change ICS-{id}: Patch to industrial control system."
                    " Security assessment: {validation_status}. Rollback: {rollback}."
                ),
            ],
            "output_template": (
                "OSHA PSM compliance: {compliance}\n"
                "Safety obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "OSHA PSM 29 CFR 1910.119(l)",
                "IEC 62443-2-3",
                "ISO 45001:2018",
            ],
        },
    },
    "semiconductor": {
        "export_control": {
            "instructions": [
                "Assess ITAR/EAR compliance for this export transaction.",
                "Identify deemed export obligations for this disclosure.",
                "Determine denied party screening requirements.",
            ],
            "inputs": [
                (
                    "Export transaction EXP-{id}: Technical data transfer to foreign entity."
                    " ECCN: {classification}. Licence: {approval_status}."
                ),
                (
                    "Deemed export DE-{id}: Foreign national access to controlled technology."
                    " Screening: {test_status}. Authorisation: {validation_status}."
                ),
            ],
            "output_template": (
                "Export control compliance: {compliance}\n"
                "ITAR/EAR obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "ITAR 22 CFR Part 120",
                "EAR 15 CFR Part 734.13",
                "EAR 15 CFR Part 744",
            ],
        },
        "ip_governance": {
            "instructions": [
                "Assess IP protection requirements for this release.",
                "Identify patent filing obligations before disclosure.",
                "Determine NDA requirements for this data sharing.",
            ],
            "inputs": [
                (
                    "IP release IPR-{id}: Technical disclosure to partner."
                    " Patent clearance: {approval_status}. NDA: {tested}."
                ),
                (
                    "Process change PCN-{id}: Semiconductor process modification."
                    " JEDEC PCN: {test_status}. Customer notification: {validation_status}."
                ),
            ],
            "output_template": (
                "IP governance: {compliance}\n"
                "Obligations:\n{obligations}\n"
                "Required evidence: {evidence}\n"
                "Recommendation: {recommendation}"
            ),
            "regulatory_refs": [
                "USPTO / EPO filing requirements",
                "UK Trade Secrets Regulations 2018",
                "JEDEC JEP671",
            ],
        },
    },
}

FILL_VALUES = {
    "id": lambda: str(random.randint(1000, 9999)),
    "window": lambda: random.choice(
        ["Saturday 02:00-06:00", "Sunday 00:00-04:00", "Wednesday 23:00-03:00"]
    ),
    "rollback": lambda: random.choice(["documented", "not documented", "partial"]),
    "impact": lambda: random.choice(["500", "5000", "50000", "500000"]),
    "classification": lambda: random.choice(["critical", "high", "medium", "low"]),
    "tested": lambda: random.choice(["yes", "no", "partial"]),
    "duration": lambda: random.choice(["15 minutes", "2 hours", "6 hours", "24 hours"]),
    "users": lambda: random.choice(["100", "1000", "10000", "100000"]),
    "traffic": lambda: random.choice(["10Gbps", "50Gbps", "100Gbps"]),
    "degradation": lambda: random.choice(["5%", "20%", "50%", "complete"]),
    "records": lambda: random.choice(["1000", "50000", "1000000"]),
    "contained": lambda: random.choice(["yes", "no", "in progress"]),
    "version": lambda: f"{random.randint(1, 5)}.{random.randint(0, 20)}.{random.randint(0, 99)}",
    "ci_status": lambda: random.choice(["passed", "failed", "not run"]),
    "scan_status": lambda: random.choice(["clean", "3 findings", "not run"]),
    "nia_status": lambda: random.choice(["complete", "pending", "not started"]),
    "vendor": lambda: random.choice(["Ericsson", "Nokia", "Huawei", "Samsung"]),
    "test_status": lambda: random.choice(["complete", "partial", "not started"]),
    "rollback_status": lambda: random.choice(["documented", "not documented"]),
    "risk_level": lambda: random.choice(["HIGH", "MEDIUM", "LOW"]),
    "readiness": lambda: random.choice(["READY", "NOT READY", "CONDITIONAL"]),
    "compliance": lambda: random.choice(["COMPLIANT", "NON-COMPLIANT", "PARTIAL"]),
    "approval_status": lambda: random.choice(["approved", "pending", "not requested"]),
    "driver": lambda: random.choice(["regulatory change", "risk finding", "business request"]),
    "validation_status": lambda: random.choice(["validated", "pending", "expired"]),
    "transactions": lambda: random.choice(["10000", "100000", "1000000"]),
    "vector": lambda: random.choice(["phishing", "credential stuffing", "zero-day exploit"]),
    "data_status": lambda: random.choice(["no data compromised", "under investigation"]),
    "containment": lambda: random.choice(["contained", "in progress", "not contained"]),
    "obligations": lambda: random.choice(
        [
            "- Complete required documentation\n- Obtain necessary approvals",
            "- Submit evidence to governance team\n- Notify regulatory body if required",
            "- Review against applicable regulations\n- Document compliance status",
        ]
    ),
    "evidence": lambda: random.choice(
        [
            "change_control_record, approval_sign_off, risk_assessment",
            "validation_report, compliance_checklist, audit_trail",
            "impact_assessment, regulatory_notification, sign_off_record",
        ]
    ),
    "recommendation": lambda: random.choice(
        [
            "BLOCK until all required evidence is provided",
            "PROCEED with conditions — evidence must be provided within 48 hours",
            "ESCALATE to senior governance for review",
        ]
    ),
    "timeline": lambda: random.choice(
        [
            "- 24 hours: early warning\n- 72 hours: full notification\n- 1 month: final report",
            "- Immediate: containment\n- 48 hours: notification\n- 30 days: final report",
        ]
    ),
    "remediation": lambda: random.choice(
        [
            "Complete missing documentation and resubmit for approval",
            "Obtain required sign-offs and update compliance records",
            "Remediate findings and provide evidence of correction",
        ]
    ),
    "notifications": lambda: random.choice(
        [
            "Regulatory authority, affected parties, internal governance",
            "Board, competent authority, impacted customers",
        ]
    ),
    "notification": lambda: random.choice(
        [
            "Required within regulatory timeframe",
            "Not required at this threshold",
            "Required — escalate to compliance team",
        ]
    ),
    "missing": lambda: random.choice(
        [
            "risk_assessment, approval_record",
            "validation_report, sign_off",
            "compliance_checklist, audit_evidence",
        ]
    ),
    "risk": lambda: random.choice(["HIGH", "MEDIUM", "LOW"]),
}


def _fill_template(template: str) -> str:
    """Fill template placeholders with random values."""
    result = template
    for key, gen_fn in FILL_VALUES.items():
        placeholder = "{" + key + "}"
        while placeholder in result:
            result = result.replace(placeholder, gen_fn(), 1)
    return result


class SyntheticScenarioGenerator:
    """
    Generates synthetic training examples for SLM fine-tuning.

    Each example is a (instruction, input, output) triple with
    regulatory references for provenance tracking.
    """

    def __init__(
        self,
        domain: str = "telecom",
        output_dir: str = "slm/training/data",
        corpus_texts: list[str] | None = None,
        target_count: int = 10000,
        seed: int = 42,
    ) -> None:
        self.domain = domain
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.corpus_texts = corpus_texts or []
        self.target_count = target_count
        self.examples: list[TrainingExample] = []
        random.seed(seed)

    def generate(self) -> list[TrainingExample]:
        """Generate synthetic training examples."""
        logger.info(
            "Generating %d training examples for domain %s",
            self.target_count,
            self.domain,
        )

        templates = SCENARIO_TEMPLATES.get(self.domain, {})
        if not templates:
            logger.warning("No scenario templates for domain %s", self.domain)
            return []

        scenario_types = list(templates.keys())
        per_scenario = self.target_count // len(scenario_types)

        for scenario_type in scenario_types:
            template = templates[scenario_type]
            for i in range(per_scenario):
                instruction = random.choice(template["instructions"])
                input_text = _fill_template(random.choice(template["inputs"]))
                output_text = _fill_template(template["output_template"])

                if self.corpus_texts and random.random() < 0.3:
                    corpus_excerpt = random.choice(self.corpus_texts)[:200]
                    output_text += f"\n\nRegulatory context: {corpus_excerpt}"

                self.examples.append(
                    TrainingExample(
                        instruction=instruction,
                        input_text=input_text,
                        output_text=output_text,
                        domain=self.domain,
                        scenario_type=scenario_type,
                        regulatory_refs=template["regulatory_refs"],
                    )
                )

        remaining = self.target_count - len(self.examples)
        for _ in range(remaining):
            scenario_type = random.choice(scenario_types)
            template = templates[scenario_type]
            instruction = random.choice(template["instructions"])
            input_text = _fill_template(random.choice(template["inputs"]))
            output_text = _fill_template(template["output_template"])
            self.examples.append(
                TrainingExample(
                    instruction=instruction,
                    input_text=input_text,
                    output_text=output_text,
                    domain=self.domain,
                    scenario_type=scenario_type,
                    regulatory_refs=template["regulatory_refs"],
                )
            )

        random.shuffle(self.examples)
        self._save_examples()

        logger.info("Generated %d training examples", len(self.examples))
        return self.examples

    def _save_examples(self) -> None:
        """Save examples as JSONL for training."""
        output_file = self.output_dir / f"{self.domain}_training.jsonl"
        with open(output_file, "w") as f:
            for ex in self.examples:
                f.write(json.dumps(ex.to_dict()) + "\n")
        logger.info("Saved training data to %s", output_file)

        splits = self._create_splits()
        for split_name, split_data in splits.items():
            split_file = self.output_dir / f"{self.domain}_{split_name}.jsonl"
            with open(split_file, "w") as f:
                for ex in split_data:
                    f.write(json.dumps(ex.to_dict()) + "\n")
            logger.info("Saved %s split: %d examples", split_name, len(split_data))

    def _create_splits(self) -> dict[str, list[TrainingExample]]:
        """Create train/val/test splits (80/10/10)."""
        n = len(self.examples)
        train_end = int(n * 0.8)
        val_end = int(n * 0.9)
        return {
            "train": self.examples[:train_end],
            "val": self.examples[train_end:val_end],
            "test": self.examples[val_end:],
        }

    @property
    def example_count(self) -> int:
        return len(self.examples)

    def get_scenario_distribution(self) -> dict[str, int]:
        """Return count of examples per scenario type."""
        dist: dict[str, int] = {}
        for ex in self.examples:
            dist[ex.scenario_type] = dist.get(ex.scenario_type, 0) + 1
        return dist
