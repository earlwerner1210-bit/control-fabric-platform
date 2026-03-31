"""
SLM Evaluation Harness

Evaluates fine-tuned domain SLMs against baseline and regulatory benchmarks.

Metrics:
  1. Regulatory citation accuracy — does the model cite the correct regulation?
  2. Evidence completeness — does the model prescribe all required evidence?
  3. Risk classification accuracy — correct risk level assignment
  4. Remediation specificity — actionable vs generic remediation
  5. Hallucination rate — fabricated regulations or controls
  6. Latency — inference time for governance assessment
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EvalMetrics:
    """Evaluation metrics for a single model."""

    citation_accuracy: float = 0.0
    evidence_completeness: float = 0.0
    risk_accuracy: float = 0.0
    remediation_specificity: float = 0.0
    hallucination_rate: float = 0.0
    avg_latency_ms: float = 0.0
    num_examples: int = 0
    model_id: str = ""
    domain: str = ""
    evaluated_at: str = ""

    def overall_score(self) -> float:
        """Weighted overall score (0-100)."""
        return (
            self.citation_accuracy * 0.25
            + self.evidence_completeness * 0.20
            + self.risk_accuracy * 0.20
            + self.remediation_specificity * 0.15
            + (1.0 - self.hallucination_rate) * 0.15
            + min(1.0, 100.0 / max(self.avg_latency_ms, 1)) * 0.05
        ) * 100

    def grade(self) -> str:
        """Letter grade based on overall score."""
        score = self.overall_score()
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    def to_dict(self) -> dict:
        return {
            "citation_accuracy": self.citation_accuracy,
            "evidence_completeness": self.evidence_completeness,
            "risk_accuracy": self.risk_accuracy,
            "remediation_specificity": self.remediation_specificity,
            "hallucination_rate": self.hallucination_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "num_examples": self.num_examples,
            "overall_score": self.overall_score(),
            "grade": self.grade(),
            "model_id": self.model_id,
            "domain": self.domain,
            "evaluated_at": self.evaluated_at,
        }


@dataclass
class EvalComparison:
    """Comparison between base and fine-tuned model."""

    base_metrics: EvalMetrics
    finetuned_metrics: EvalMetrics
    improvements: dict[str, float] = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "base": self.base_metrics.to_dict(),
            "finetuned": self.finetuned_metrics.to_dict(),
            "improvements": self.improvements,
            "recommendation": self.recommendation,
        }


KNOWN_REGULATIONS = {
    "telecom": [
        "NIS2",
        "Ofcom",
        "3GPP",
        "GSMA",
        "ENISA",
        "Article 21",
        "Article 23",
        "Article 24",
        "General Condition C4",
        "General Condition C5",
        "TS 32.600",
        "FS.13",
    ],
    "financial_services": [
        "FCA",
        "SYSC",
        "PRA",
        "DORA",
        "MiFID",
        "Basel",
        "Article 8",
        "Article 11",
        "Article 17",
        "Article 28",
        "SS1/21",
        "SS1/23",
        "CRR",
        "CRD",
    ],
}

REQUIRED_EVIDENCE_MAP = {
    "telecom": {
        "network_change": ["change_request", "network_impact_assessment", "maintenance_window"],
        "production_release": ["ci_result", "security_scan", "rollback_plan"],
        "security_incident": ["incident_report", "containment_evidence", "root_cause_analysis"],
    },
    "financial_services": {
        "change_management": ["change_request", "impact_assessment", "four_eyes_approval"],
        "production_release": ["change_request", "approver_sign_off", "rollback_plan"],
        "incident_response": ["incident_report", "timeline", "regulatory_notification"],
    },
}


class SLMEvaluator:
    """
    Evaluates domain SLMs against regulatory benchmarks.

    Can compare base model vs fine-tuned model performance.
    """

    def __init__(
        self,
        domain: str = "telecom",
        test_data_path: str | None = None,
        results_dir: str = "slm/evaluation/results",
    ) -> None:
        self.domain = domain
        self.test_data_path = test_data_path or f"slm/training/data/{domain}_test.jsonl"
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.known_regs = KNOWN_REGULATIONS.get(domain, [])
        self.evidence_map = REQUIRED_EVIDENCE_MAP.get(domain, {})

    def evaluate(
        self,
        model_id: str = "base",
        predictions: list[dict] | None = None,
    ) -> EvalMetrics:
        """Evaluate a model's predictions against test data."""
        test_examples = self._load_test_data()
        if not test_examples:
            logger.warning("No test data found at %s", self.test_data_path)
            return EvalMetrics(model_id=model_id, domain=self.domain)

        if predictions is None:
            predictions = [{"output": ex.get("output", "")} for ex in test_examples]

        metrics = self._compute_metrics(test_examples, predictions, model_id)
        self._save_results(metrics)
        return metrics

    def compare(
        self,
        base_predictions: list[dict] | None = None,
        finetuned_predictions: list[dict] | None = None,
        base_model_id: str = "base",
        finetuned_model_id: str = "finetuned",
    ) -> EvalComparison:
        """Compare base vs fine-tuned model."""
        base_metrics = self.evaluate(base_model_id, base_predictions)
        ft_metrics = self.evaluate(finetuned_model_id, finetuned_predictions)

        improvements = {
            "citation_accuracy": ft_metrics.citation_accuracy - base_metrics.citation_accuracy,
            "evidence_completeness": (
                ft_metrics.evidence_completeness - base_metrics.evidence_completeness
            ),
            "risk_accuracy": ft_metrics.risk_accuracy - base_metrics.risk_accuracy,
            "remediation_specificity": (
                ft_metrics.remediation_specificity - base_metrics.remediation_specificity
            ),
            "hallucination_rate": base_metrics.hallucination_rate - ft_metrics.hallucination_rate,
            "latency_ms": base_metrics.avg_latency_ms - ft_metrics.avg_latency_ms,
        }

        improved_count = sum(1 for v in improvements.values() if v > 0)
        if improved_count >= 4 and ft_metrics.overall_score() >= 70:
            recommendation = "DEPLOY: Fine-tuned model shows significant improvement."
        elif improved_count >= 2:
            recommendation = "CONDITIONAL: Some improvements, review before deploying."
        else:
            recommendation = "REJECT: Fine-tuned model does not improve on baseline."

        comparison = EvalComparison(
            base_metrics=base_metrics,
            finetuned_metrics=ft_metrics,
            improvements=improvements,
            recommendation=recommendation,
        )

        comparison_file = self.results_dir / f"{self.domain}_comparison.json"
        comparison_file.write_text(json.dumps(comparison.to_dict(), indent=2))

        return comparison

    def _load_test_data(self) -> list[dict]:
        """Load test examples from JSONL."""
        test_file = Path(self.test_data_path)
        if not test_file.exists():
            return []
        examples = []
        with open(test_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    examples.append(json.loads(line))
        return examples

    def _compute_metrics(
        self,
        test_examples: list[dict],
        predictions: list[dict],
        model_id: str,
    ) -> EvalMetrics:
        """Compute all evaluation metrics."""
        citation_scores: list[float] = []
        evidence_scores: list[float] = []
        risk_scores: list[float] = []
        remediation_scores: list[float] = []
        hallucination_scores: list[float] = []
        latencies: list[float] = []

        for i, (example, pred) in enumerate(zip(test_examples, predictions)):
            start = time.monotonic()

            pred_text = pred.get("output", "")
            expected_text = example.get("output", "")
            scenario_type = example.get("scenario_type", "")
            reg_refs = example.get("regulatory_refs", [])

            citation_scores.append(self._score_citations(pred_text, reg_refs))
            evidence_scores.append(self._score_evidence(pred_text, scenario_type))
            risk_scores.append(self._score_risk_classification(pred_text, expected_text))
            remediation_scores.append(self._score_remediation(pred_text))
            hallucination_scores.append(self._score_hallucination(pred_text))

            elapsed_ms = (time.monotonic() - start) * 1000
            latencies.append(elapsed_ms)

        n = max(len(test_examples), 1)
        return EvalMetrics(
            citation_accuracy=sum(citation_scores) / n,
            evidence_completeness=sum(evidence_scores) / n,
            risk_accuracy=sum(risk_scores) / n,
            remediation_specificity=sum(remediation_scores) / n,
            hallucination_rate=sum(hallucination_scores) / n,
            avg_latency_ms=sum(latencies) / n,
            num_examples=len(test_examples),
            model_id=model_id,
            domain=self.domain,
            evaluated_at=datetime.now(UTC).isoformat(),
        )

    def _score_citations(self, pred_text: str, expected_refs: list[str]) -> float:
        """Score: does the prediction cite the expected regulations?"""
        if not expected_refs:
            return 1.0
        found = sum(1 for ref in expected_refs if ref.lower() in pred_text.lower())
        return found / len(expected_refs)

    def _score_evidence(self, pred_text: str, scenario_type: str) -> float:
        """Score: does the prediction mention required evidence types?"""
        required = self.evidence_map.get(scenario_type, [])
        if not required:
            return 1.0
        pred_lower = pred_text.lower()
        found = sum(1 for ev in required if ev.replace("_", " ") in pred_lower or ev in pred_lower)
        return found / len(required)

    def _score_risk_classification(self, pred_text: str, expected_text: str) -> float:
        """Score: correct risk level assignment."""
        risk_levels = ["HIGH", "MEDIUM", "LOW", "CRITICAL"]
        pred_upper = pred_text.upper()
        expected_upper = expected_text.upper()

        pred_risk = next((r for r in risk_levels if r in pred_upper), None)
        expected_risk = next((r for r in risk_levels if r in expected_upper), None)

        if pred_risk is None or expected_risk is None:
            return 0.5
        if pred_risk == expected_risk:
            return 1.0
        level_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        diff = abs(level_order.get(pred_risk, 1) - level_order.get(expected_risk, 1))
        return max(0.0, 1.0 - diff * 0.33)

    def _score_remediation(self, pred_text: str) -> float:
        """Score: how specific and actionable is the remediation?"""
        specificity_markers = [
            "provide",
            "ensure",
            "submit",
            "document",
            "review",
            "before",
            "within",
            "must",
            "required",
            "approval",
        ]
        pred_lower = pred_text.lower()
        found = sum(1 for m in specificity_markers if m in pred_lower)
        return min(1.0, found / 4.0)

    def _score_hallucination(self, pred_text: str) -> float:
        """Score: rate of fabricated regulation references (lower is better)."""
        reg_patterns = ["Article", "Section", "Regulation", "Directive", "Condition"]
        pred_words = pred_text.split()
        total_refs = 0
        hallucinated = 0

        for i, word in enumerate(pred_words):
            if word in reg_patterns and i + 1 < len(pred_words):
                total_refs += 1
                context = " ".join(pred_words[max(0, i - 2) : i + 3])
                if not any(kr.lower() in context.lower() for kr in self.known_regs):
                    hallucinated += 1

        if total_refs == 0:
            return 0.0
        return hallucinated / total_refs

    def _save_results(self, metrics: EvalMetrics) -> None:
        """Save evaluation results."""
        results_file = self.results_dir / f"{self.domain}_{metrics.model_id}_eval.json"
        results_file.write_text(json.dumps(metrics.to_dict(), indent=2))
        logger.info(
            "Eval results saved: %s (score=%.1f, grade=%s)",
            results_file,
            metrics.overall_score(),
            metrics.grade(),
        )
