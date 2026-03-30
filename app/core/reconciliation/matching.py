"""Wave 2 matching, scoring, classification — fabric-native candidate lifecycle."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.control_link import ControlLink
from app.core.control_object import ControlObject
from app.core.reconciliation.domain_types import (
    CandidateRanking,
    CrossPlaneMismatchCategory,
    DuplicateCandidateSet,
    MatchCandidate,
    MatchScore,
    MatchScoreBreakdown,
    ReconciliationAssemblyInput,
    ReconciliationAssemblyOutput,
    ReconciliationCasePriority,
    ReconciliationEvidenceBundle,
    ReconciliationHash,
    ReconciliationMismatch,
    ReconciliationOutcome,
    ReconciliationOutcomeType,
    ReconciliationRunId,
    ReconciliationSummary,
    new_candidate_id,
)
from app.core.reconciliation.rule_model import (
    ReconciliationRule,
    ReconciliationRuleRegistry,
    ReconciliationRuleTraceEntry,
)
from app.core.types import ConfidenceScore, ControlLinkType, PlaneType


class CandidateGenerator:
    """Generates match candidates from graph relationships, correlation keys, and external refs."""

    def generate(
        self,
        source_objects: list[ControlObject],
        target_objects: list[ControlObject],
        links: list[ControlLink],
    ) -> list[MatchCandidate]:
        candidates: list[MatchCandidate] = []
        seen_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()

        for link in links:
            if not link.is_cross_plane:
                continue
            src = _find_object(link.source_id, source_objects)
            tgt = _find_object(link.target_id, target_objects)
            if src and tgt:
                pair_key = (uuid.UUID(bytes=src.id.bytes), uuid.UUID(bytes=tgt.id.bytes))
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    candidates.append(
                        MatchCandidate(
                            source_object_id=src.id,
                            target_object_id=tgt.id,
                            source_plane=src.plane,
                            target_plane=tgt.plane,
                            match_method="graph-link",
                        )
                    )
            src_r = _find_object(link.target_id, source_objects)
            tgt_r = _find_object(link.source_id, target_objects)
            if src_r and tgt_r:
                pair_key = (
                    uuid.UUID(bytes=src_r.id.bytes),
                    uuid.UUID(bytes=tgt_r.id.bytes),
                )
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    candidates.append(
                        MatchCandidate(
                            source_object_id=src_r.id,
                            target_object_id=tgt_r.id,
                            source_plane=src_r.plane,
                            target_plane=tgt_r.plane,
                            match_method="graph-link-reverse",
                        )
                    )

        for src in source_objects:
            for key, val in src.correlation_keys.items():
                if not val:
                    continue
                for tgt in target_objects:
                    if tgt.correlation_keys.get(key) == val:
                        pair_key = (
                            uuid.UUID(bytes=src.id.bytes),
                            uuid.UUID(bytes=tgt.id.bytes),
                        )
                        if pair_key not in seen_pairs:
                            seen_pairs.add(pair_key)
                            candidates.append(
                                MatchCandidate(
                                    source_object_id=src.id,
                                    target_object_id=tgt.id,
                                    source_plane=src.plane,
                                    target_plane=tgt.plane,
                                    match_method="correlation-key",
                                    metadata={"matched_key": key, "matched_value": val},
                                )
                            )

        for src in source_objects:
            for key, val in src.external_refs.items():
                if not val:
                    continue
                for tgt in target_objects:
                    if tgt.external_refs.get(key) == val:
                        pair_key = (
                            uuid.UUID(bytes=src.id.bytes),
                            uuid.UUID(bytes=tgt.id.bytes),
                        )
                        if pair_key not in seen_pairs:
                            seen_pairs.add(pair_key)
                            candidates.append(
                                MatchCandidate(
                                    source_object_id=src.id,
                                    target_object_id=tgt.id,
                                    source_plane=src.plane,
                                    target_plane=tgt.plane,
                                    match_method="external-ref",
                                    metadata={"matched_ref": key, "matched_value": val},
                                )
                            )

        return candidates


class CandidateScorer:
    """Scores match candidates by applying reconciliation rules."""

    def __init__(self, rule_registry: ReconciliationRuleRegistry) -> None:
        self._rule_registry = rule_registry

    def score_candidate(
        self,
        candidate: MatchCandidate,
        source: ControlObject,
        target: ControlObject,
        links: list[ControlLink],
    ) -> tuple[MatchCandidate, list[ReconciliationRuleTraceEntry]]:
        applicable_rules = self._rule_registry.get_applicable_rules(source, target)
        score_breakdown = MatchScoreBreakdown()
        all_mismatches: list[ReconciliationMismatch] = []
        trace_entries: list[ReconciliationRuleTraceEntry] = []
        total_weight = 0.0
        total_score = 0.0
        hard_fail = False

        for rule in applicable_rules:
            result = rule.evaluate(source, target, links)
            total_weight += rule.weight.weight
            total_score += result.score_contribution

            score_breakdown.rule_scores[rule.rule_id] = result.score_contribution
            if result.explanation:
                score_breakdown.rule_explanations[rule.rule_id] = result.explanation.description

            if result.mismatches:
                all_mismatches.extend(result.mismatches)

            if result.hard_fail:
                hard_fail = True

            trace_entries.append(
                ReconciliationRuleTraceEntry(
                    rule_id=rule.rule_id,
                    rule_version=rule.rule_version,
                    category=rule.category,
                    source_object_id=str(source.id),
                    target_object_id=str(target.id),
                    applied=True,
                    explanation=result.explanation,
                    mismatches_found=result.mismatches,
                    score_contribution=result.score_contribution,
                )
            )

        score_breakdown.weighted_total = total_score
        score_breakdown.max_possible = total_weight

        final_score = 0.0 if hard_fail else score_breakdown.normalized_score

        candidate.score = MatchScore(final_score)
        candidate.score_breakdown = score_breakdown
        candidate.confidence = ConfidenceScore(final_score)
        candidate.mismatches = all_mismatches

        return candidate, trace_entries

    def score_all(
        self,
        candidates: list[MatchCandidate],
        objects_by_id: dict[uuid.UUID, ControlObject],
        links: list[ControlLink],
    ) -> tuple[list[MatchCandidate], list[ReconciliationRuleTraceEntry]]:
        all_traces: list[ReconciliationRuleTraceEntry] = []
        scored: list[MatchCandidate] = []
        for candidate in candidates:
            source = objects_by_id.get(uuid.UUID(bytes=candidate.source_object_id.bytes))
            target = objects_by_id.get(uuid.UUID(bytes=candidate.target_object_id.bytes))
            if source and target:
                scored_candidate, traces = self.score_candidate(candidate, source, target, links)
                scored.append(scored_candidate)
                all_traces.extend(traces)
        return scored, all_traces


class DuplicateDetector:
    """Detects multiple high-confidence candidates for the same source object."""

    def __init__(self, score_gap_threshold: float = 0.05) -> None:
        self._gap_threshold = score_gap_threshold

    def detect(self, candidates: list[MatchCandidate]) -> list[DuplicateCandidateSet]:
        by_source: dict[uuid.UUID, list[MatchCandidate]] = {}
        for c in candidates:
            key = uuid.UUID(bytes=c.source_object_id.bytes)
            by_source.setdefault(key, []).append(c)

        duplicates: list[DuplicateCandidateSet] = []
        for source_id, source_candidates in by_source.items():
            if len(source_candidates) < 2:
                continue
            sorted_candidates = sorted(
                source_candidates, key=lambda c: float(c.score), reverse=True
            )
            top_score = float(sorted_candidates[0].score)
            close_matches = [
                c
                for c in sorted_candidates
                if abs(float(c.score) - top_score) <= self._gap_threshold
            ]
            if len(close_matches) > 1:
                from app.core.types import ControlObjectId

                duplicates.append(
                    DuplicateCandidateSet(
                        source_object_id=ControlObjectId(source_id),
                        duplicate_target_ids=[c.target_object_id for c in close_matches],
                        scores=[c.score for c in close_matches],
                        description=(
                            f"Multiple high-confidence matches for object {source_id}: "
                            f"{len(close_matches)} candidates within {self._gap_threshold} score gap"
                        ),
                    )
                )
        return duplicates

    def build_rankings(self, candidates: list[MatchCandidate]) -> list[CandidateRanking]:
        by_source: dict[uuid.UUID, list[MatchCandidate]] = {}
        for c in candidates:
            key = uuid.UUID(bytes=c.source_object_id.bytes)
            by_source.setdefault(key, []).append(c)

        rankings: list[CandidateRanking] = []
        for source_id, source_candidates in by_source.items():
            from app.core.types import ControlObjectId

            sorted_candidates = sorted(
                source_candidates, key=lambda c: float(c.score), reverse=True
            )
            top_score = (
                MatchScore(float(sorted_candidates[0].score))
                if sorted_candidates
                else MatchScore(0.0)
            )
            ambiguity_gap = 0.0
            is_ambiguous = False
            if len(sorted_candidates) >= 2:
                ambiguity_gap = abs(
                    float(sorted_candidates[0].score) - float(sorted_candidates[1].score)
                )
                is_ambiguous = ambiguity_gap <= self._gap_threshold

            rankings.append(
                CandidateRanking(
                    source_object_id=ControlObjectId(source_id),
                    ranked_candidates=sorted_candidates,
                    top_score=top_score,
                    is_ambiguous=is_ambiguous,
                    ambiguity_gap=ambiguity_gap,
                )
            )
        return rankings


class MismatchClassifier:
    """Classifies mismatches from scored candidates and coverage analysis."""

    def classify_identifier_conflicts(
        self,
        source_objects: list[ControlObject],
        target_objects: list[ControlObject],
    ) -> list[ReconciliationMismatch]:
        mismatches: list[ReconciliationMismatch] = []
        for src in source_objects:
            for tgt in target_objects:
                if src.plane == tgt.plane:
                    continue
                for key, val in src.correlation_keys.items():
                    tgt_val = tgt.correlation_keys.get(key)
                    if tgt_val and tgt_val != val and key in tgt.correlation_keys:
                        if src.object_kind == tgt.object_kind or src.domain == tgt.domain:
                            mismatches.append(
                                ReconciliationMismatch(
                                    category=CrossPlaneMismatchCategory.IDENTIFIER_CONFLICT,
                                    source_object_id=src.id,
                                    target_object_id=tgt.id,
                                    source_plane=src.plane,
                                    target_plane=tgt.plane,
                                    description=(
                                        f"Identifier conflict on key '{key}': "
                                        f"{val} (source) vs {tgt_val} (target)"
                                    ),
                                    expected_value=val,
                                    actual_value=tgt_val,
                                )
                            )
        return mismatches

    def classify_missing_objects(
        self,
        matched_source_ids: set[uuid.UUID],
        matched_target_ids: set[uuid.UUID],
        source_objects: list[ControlObject],
        target_objects: list[ControlObject],
        source_plane: PlaneType,
        target_plane: PlaneType,
    ) -> list[ReconciliationMismatch]:
        from app.core.reconciliation.domain_types import MISSING_CATEGORY_BY_PLANE

        mismatches: list[ReconciliationMismatch] = []
        for src in source_objects:
            if uuid.UUID(bytes=src.id.bytes) not in matched_source_ids:
                category = MISSING_CATEGORY_BY_PLANE.get(
                    target_plane, CrossPlaneMismatchCategory.MISSING_IN_FIELD
                )
                mismatches.append(
                    ReconciliationMismatch(
                        category=category,
                        source_object_id=src.id,
                        source_plane=src.plane,
                        target_plane=target_plane,
                        description=(
                            f"Object '{src.label}' in {src.plane.value} has no match "
                            f"in {target_plane.value}"
                        ),
                    )
                )
        for tgt in target_objects:
            if uuid.UUID(bytes=tgt.id.bytes) not in matched_target_ids:
                category = MISSING_CATEGORY_BY_PLANE.get(
                    source_plane, CrossPlaneMismatchCategory.MISSING_IN_COMMERCIAL
                )
                mismatches.append(
                    ReconciliationMismatch(
                        category=category,
                        target_object_id=tgt.id,
                        source_plane=source_plane,
                        target_plane=tgt.plane,
                        description=(
                            f"Object '{tgt.label}' in {tgt.plane.value} has no match "
                            f"in {source_plane.value}"
                        ),
                    )
                )
        return mismatches


class ReconciliationAssembler:
    """Assembles final reconciliation outcomes from scored candidates and analysis."""

    def __init__(self, match_threshold: float = 0.7) -> None:
        self._match_threshold = match_threshold

    def assemble(
        self,
        assembly_input: ReconciliationAssemblyInput,
        run_id: ReconciliationRunId,
        tenant_id: uuid.UUID,
        planes: list[PlaneType],
        domains: list[str],
    ) -> ReconciliationAssemblyOutput:
        outcomes: list[ReconciliationOutcome] = []

        for ranking in assembly_input.rankings:
            if not ranking.ranked_candidates:
                continue
            top = ranking.ranked_candidates[0]
            if float(top.score) >= self._match_threshold:
                outcome = ReconciliationOutcome(
                    outcome_type=ReconciliationOutcomeType.FULLY_RECONCILED,
                    source_object_id=top.source_object_id,
                    target_object_id=top.target_object_id,
                    candidate=top,
                    mismatches=top.mismatches,
                    confidence=top.confidence,
                    evidence_bundle=ReconciliationEvidenceBundle(
                        source_object_ids=[top.source_object_id],
                        target_object_ids=[top.target_object_id],
                        evidence_refs=list(top.evidence_refs),
                    ),
                )
                outcome.compute_hash()
                outcomes.append(outcome)
            elif float(top.score) > 0.0:
                outcome = ReconciliationOutcome(
                    outcome_type=ReconciliationOutcomeType.CANDIDATE_MATCH,
                    source_object_id=top.source_object_id,
                    target_object_id=top.target_object_id,
                    candidate=top,
                    mismatches=top.mismatches,
                    confidence=top.confidence,
                )
                outcome.compute_hash()
                outcomes.append(outcome)

        for dup_set in assembly_input.duplicates:
            outcome = ReconciliationOutcome(
                outcome_type=ReconciliationOutcomeType.DUPLICATE_DETECTED,
                source_object_id=dup_set.source_object_id,
                mismatches=[
                    ReconciliationMismatch(
                        category=CrossPlaneMismatchCategory.DUPLICATE_CANDIDATE,
                        source_object_id=dup_set.source_object_id,
                        description=dup_set.description,
                    )
                ],
                metadata={
                    "duplicate_target_ids": [str(tid) for tid in dup_set.duplicate_target_ids],
                },
            )
            outcome.compute_hash()
            outcomes.append(outcome)

        if assembly_input.coverage_result and not assembly_input.coverage_result.is_fully_covered:
            for gap in assembly_input.coverage_result.gaps:
                outcome = ReconciliationOutcome(
                    outcome_type=ReconciliationOutcomeType.COVERAGE_GAP,
                    coverage_gap=gap,
                    metadata={"plane": gap.plane.value, "kind": gap.expected_object_kind},
                )
                outcome.compute_hash()
                outcomes.append(outcome)

        for ev_result in assembly_input.evidence_results:
            if not ev_result.is_sufficient:
                outcome = ReconciliationOutcome(
                    outcome_type=ReconciliationOutcomeType.INSUFFICIENT_EVIDENCE,
                    source_object_id=ev_result.object_id,
                    mismatches=[
                        ReconciliationMismatch(
                            category=CrossPlaneMismatchCategory.EVIDENCE_INSUFFICIENT,
                            source_object_id=ev_result.object_id,
                            description=(
                                f"Missing evidence types: {ev_result.missing_evidence_types}"
                            ),
                            metadata={"missing_types": ev_result.missing_evidence_types},
                        )
                    ],
                )
                outcome.compute_hash()
                outcomes.append(outcome)

        for mismatch in assembly_input.mismatches:
            already_in_outcome = any(m.id == mismatch.id for o in outcomes for m in o.mismatches)
            if not already_in_outcome:
                outcome = ReconciliationOutcome(
                    outcome_type=ReconciliationOutcomeType.MISMATCH_DETECTED,
                    source_object_id=mismatch.source_object_id,
                    target_object_id=mismatch.target_object_id,
                    mismatches=[mismatch],
                )
                outcome.compute_hash()
                outcomes.append(outcome)

        total_matches = sum(
            1 for o in outcomes if o.outcome_type == ReconciliationOutcomeType.FULLY_RECONCILED
        )
        total_mismatches = sum(len(o.mismatches) for o in outcomes)
        total_duplicates = sum(
            1 for o in outcomes if o.outcome_type == ReconciliationOutcomeType.DUPLICATE_DETECTED
        )
        total_coverage_gaps = sum(
            1 for o in outcomes if o.outcome_type == ReconciliationOutcomeType.COVERAGE_GAP
        )
        total_insufficient = sum(
            1 for o in outcomes if o.outcome_type == ReconciliationOutcomeType.INSUFFICIENT_EVIDENCE
        )

        outcome_counts: dict[str, int] = {}
        for o in outcomes:
            outcome_counts[o.outcome_type.value] = outcome_counts.get(o.outcome_type.value, 0) + 1

        summary = ReconciliationSummary(
            run_id=run_id,
            tenant_id=tenant_id,
            total_candidates_generated=len(assembly_input.candidates),
            total_matches=total_matches,
            total_mismatches=total_mismatches,
            total_duplicates=total_duplicates,
            total_coverage_gaps=total_coverage_gaps,
            total_insufficient_evidence=total_insufficient,
            outcome_counts=outcome_counts,
            planes_reconciled=planes,
            domains_reconciled=domains,
        )

        return ReconciliationAssemblyOutput(outcomes=outcomes, summary=summary)


def _find_object(object_id: uuid.UUID, objects: list[ControlObject]) -> ControlObject | None:
    target_bytes = (
        object_id.bytes if hasattr(object_id, "bytes") else uuid.UUID(str(object_id)).bytes
    )
    for obj in objects:
        if obj.id.bytes == target_bytes:
            return obj
    return None
