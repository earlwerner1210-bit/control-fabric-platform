"""Severity and Prioritisation Engine — weighted scoring, dedup, clustering."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from .domain_types import (
    OperatorUrgency,
    RouteCategory,
    ScoredCase,
    SeverityInput,
    SeverityWeight,
)

logger = logging.getLogger(__name__)

_DEFAULT_WEIGHTS: list[SeverityWeight] = [
    SeverityWeight(dimension="severity_raw", weight=0.30, description="Raw severity label"),
    SeverityWeight(dimension="financial_impact", weight=0.25, description="Monetary exposure"),
    SeverityWeight(dimension="affected_objects", weight=0.20, description="Blast radius"),
    SeverityWeight(dimension="rule_criticality", weight=0.25, description="Rule importance"),
]

_SEVERITY_MAP: dict[str, float] = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.50,
    "low": 0.25,
    "info": 0.10,
}


class SeverityEngine:
    """Stateless severity scorer with pluggable weights."""

    def __init__(self, weights: list[SeverityWeight] | None = None) -> None:
        self.weights = weights or list(_DEFAULT_WEIGHTS)
        self._seen_hashes: set[str] = set()
        self._clusters: dict[str, list[str]] = {}

    # ── public api ──────────────────────────────────────────

    def score(self, inp: SeverityInput) -> ScoredCase:
        factors: dict[str, float] = {}

        sev_val = _SEVERITY_MAP.get(inp.severity_raw.lower(), 0.50)
        factors["severity_raw"] = sev_val

        fin = min(inp.financial_impact / 1_000_000, 1.0) if inp.financial_impact > 0 else 0.0
        factors["financial_impact"] = fin

        obj = min(inp.affected_objects / 100, 1.0)
        factors["affected_objects"] = obj

        rule_val = _SEVERITY_MAP.get(inp.rule_criticality.lower(), 0.50)
        factors["rule_criticality"] = rule_val

        weight_map = {w.dimension: w.weight for w in self.weights}
        composite = sum(factors.get(d, 0.0) * weight_map.get(d, 0.0) for d in factors)
        composite_score = round(composite * 100, 2)

        route = self._route(composite_score, inp)
        urgency = self._urgency(composite_score, inp)

        if inp.cluster_id:
            self._clusters.setdefault(inp.cluster_id, []).append(inp.case_id)

        return ScoredCase(
            case_id=inp.case_id,
            composite_score=composite_score,
            route=route,
            urgency=urgency,
            scoring_factors=factors,
        )

    def score_batch(self, inputs: list[SeverityInput]) -> list[ScoredCase]:
        results: list[ScoredCase] = []
        for inp in inputs:
            if inp.is_duplicate and self._is_seen(inp):
                logger.info("Suppressing duplicate case %s", inp.case_id)
                results.append(
                    ScoredCase(
                        case_id=inp.case_id,
                        composite_score=0.0,
                        route=RouteCategory.SUPPRESS,
                        urgency=OperatorUrgency.BACKLOG,
                        scoring_factors={"suppressed": 1.0},
                    )
                )
                continue
            results.append(self.score(inp))

        ranked = sorted(results, key=lambda s: s.composite_score, reverse=True)
        return [
            ScoredCase(
                case_id=s.case_id,
                composite_score=s.composite_score,
                route=s.route,
                urgency=s.urgency,
                rank=i + 1,
                scoring_factors=s.scoring_factors,
                scored_at=s.scored_at,
            )
            for i, s in enumerate(ranked)
        ]

    def get_priority_queue(self, scored: list[ScoredCase]) -> list[ScoredCase]:
        return [s for s in scored if s.route != RouteCategory.SUPPRESS]

    def get_cluster(self, cluster_id: str) -> list[str]:
        return self._clusters.get(cluster_id, [])

    # ── private ─────────────────────────────────────────────

    def _route(self, score: float, inp: SeverityInput) -> RouteCategory:
        if score >= 70:
            return RouteCategory.MUST_BLOCK
        if score >= 45:
            return RouteCategory.REQUIRES_REVIEW
        if score >= 20:
            return RouteCategory.MONITOR
        return RouteCategory.SUPPRESS

    def _urgency(self, score: float, inp: SeverityInput) -> OperatorUrgency:
        if score >= 70:
            return OperatorUrgency.IMMEDIATE
        if score >= 45:
            return OperatorUrgency.SAME_DAY
        if score >= 20:
            return OperatorUrgency.THIS_WEEK
        return OperatorUrgency.BACKLOG

    def _is_seen(self, inp: SeverityInput) -> bool:
        h = hashlib.sha256(f"{inp.case_type}:{inp.domain_pack}:{inp.severity_raw}".encode())
        digest = h.hexdigest()[:16]
        if digest in self._seen_hashes:
            return True
        self._seen_hashes.add(digest)
        return False
