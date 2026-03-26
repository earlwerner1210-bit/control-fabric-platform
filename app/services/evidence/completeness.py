"""Evidence completeness scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompletenessScore:
    """Evidence completeness assessment result."""

    score: float
    max_score: float
    dimensions: dict[str, float]
    missing: list[str]
    explanation: str

    @property
    def normalized(self) -> float:
        return self.score / self.max_score if self.max_score > 0 else 0.0


DIMENSION_WEIGHTS = {
    "source_documents": 2.0,
    "source_chunks": 1.5,
    "control_objects": 2.0,
    "validation_trace": 1.5,
    "model_lineage": 1.0,
    "cross_plane_conflicts": 0.5,
    "rule_hits": 1.5,
    "chain_stages": 1.0,
}


def score_evidence_completeness(
    items: list[dict[str, Any]] | None = None,
    chain_stages: list[str] | None = None,
    trace: dict[str, Any] | None = None,
    validation_trace: dict[str, Any] | None = None,
    model_lineage: dict[str, Any] | None = None,
) -> CompletenessScore:
    """Score evidence completeness across multiple dimensions.

    Returns a CompletenessScore with per-dimension breakdown.
    """
    dimensions: dict[str, float] = {}
    missing: list[str] = []
    max_score = sum(DIMENSION_WEIGHTS.values())

    # Source documents
    docs = [i for i in (items or []) if i.get("evidence_type") == "document"]
    if docs:
        dimensions["source_documents"] = DIMENSION_WEIGHTS["source_documents"]
    else:
        dimensions["source_documents"] = 0.0
        missing.append("source_documents")

    # Source chunks
    chunks = [i for i in (items or []) if i.get("evidence_type") == "chunk"]
    if chunks:
        dimensions["source_chunks"] = DIMENSION_WEIGHTS["source_chunks"]
    else:
        dimensions["source_chunks"] = 0.0
        missing.append("source_chunks")

    # Control objects
    controls = [i for i in (items or []) if i.get("evidence_type") == "control_object"]
    if controls:
        dimensions["control_objects"] = DIMENSION_WEIGHTS["control_objects"]
    else:
        dimensions["control_objects"] = 0.0
        missing.append("control_objects")

    # Validation trace
    if validation_trace and validation_trace.get("validators_run"):
        dimensions["validation_trace"] = DIMENSION_WEIGHTS["validation_trace"]
    else:
        dimensions["validation_trace"] = 0.0
        missing.append("validation_trace")

    # Model lineage
    if model_lineage and model_lineage.get("model_id"):
        dimensions["model_lineage"] = DIMENSION_WEIGHTS["model_lineage"]
    else:
        dimensions["model_lineage"] = 0.0
        missing.append("model_lineage")

    # Cross-plane conflicts
    if trace and trace.get("cross_plane_conflicts") is not None:
        dimensions["cross_plane_conflicts"] = DIMENSION_WEIGHTS["cross_plane_conflicts"]
    else:
        dimensions["cross_plane_conflicts"] = 0.0
        missing.append("cross_plane_conflicts")

    # Rule hits
    if trace and trace.get("rules_fired"):
        dimensions["rule_hits"] = DIMENSION_WEIGHTS["rule_hits"]
    else:
        dimensions["rule_hits"] = 0.0
        missing.append("rule_hits")

    # Chain stages
    required_stages = {
        "contract_basis",
        "work_authorization",
        "execution_evidence",
        "billing_evidence",
    }
    provided_stages = set(chain_stages or [])
    stage_coverage = (
        len(provided_stages & required_stages) / len(required_stages) if required_stages else 0
    )
    dimensions["chain_stages"] = DIMENSION_WEIGHTS["chain_stages"] * stage_coverage
    if stage_coverage < 1.0:
        missing_stages = required_stages - provided_stages
        missing.append(f"chain_stages({', '.join(sorted(missing_stages))})")

    score = sum(dimensions.values())

    # Build explanation
    present = [k for k, v in dimensions.items() if v > 0]
    explanation_parts = []
    if present:
        explanation_parts.append(f"Present: {', '.join(present)}")
    if missing:
        explanation_parts.append(f"Missing: {', '.join(missing)}")
    explanation_parts.append(f"Score: {score:.1f}/{max_score:.1f} ({score / max_score * 100:.0f}%)")

    return CompletenessScore(
        score=score,
        max_score=max_score,
        dimensions=dimensions,
        missing=missing,
        explanation=". ".join(explanation_parts),
    )
