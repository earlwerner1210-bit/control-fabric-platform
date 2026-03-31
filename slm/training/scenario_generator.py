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
