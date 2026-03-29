"""Wave 2 coverage analysis and evidence sufficiency evaluation."""

from __future__ import annotations

import uuid

from app.core.control_object import ControlObject
from app.core.reconciliation.domain_types import (
    CoverageExpectationResult,
    CoverageGap,
    EvidenceSufficiencyResult,
    ExpectedPlaneCoverage,
)
from app.core.types import ControlObjectId, PlaneType


class CoverageAnalyzer:
    """Evaluates whether expected cross-plane coverage is met."""

    def analyze(
        self,
        objects: list[ControlObject],
        expectations: list[ExpectedPlaneCoverage],
    ) -> CoverageExpectationResult:
        if not expectations:
            return CoverageExpectationResult(is_fully_covered=True)

        gaps: list[CoverageGap] = []
        objects_by_plane: dict[PlaneType, list[ControlObject]] = {}
        for obj in objects:
            objects_by_plane.setdefault(obj.plane, []).append(obj)

        for expectation in expectations:
            plane_objects = objects_by_plane.get(expectation.plane, [])
            for kind in expectation.expected_object_kinds:
                kind_objects = [o for o in plane_objects if o.object_kind == kind]
                min_count = expectation.min_objects_per_kind.get(kind, 1)
                actual_count = len(kind_objects)
                if actual_count < min_count:
                    gaps.append(
                        CoverageGap(
                            plane=expectation.plane,
                            expected_object_kind=kind,
                            expected_count=min_count,
                            actual_count=actual_count,
                            missing_count=min_count - actual_count,
                            description=(
                                f"Expected at least {min_count} '{kind}' objects in "
                                f"{expectation.plane.value}, found {actual_count}"
                            ),
                        )
                    )

        return CoverageExpectationResult(
            expectations=expectations,
            gaps=gaps,
            is_fully_covered=len(gaps) == 0,
        )


class EvidenceSufficiencyEvaluator:
    """Evaluates whether objects have sufficient evidence for reconciliation."""

    def __init__(self, required_evidence_types: list[str] | None = None) -> None:
        self._required_types = required_evidence_types or []

    def evaluate_object(self, obj: ControlObject) -> EvidenceSufficiencyResult:
        present_types = [e.evidence_type for e in obj.evidence]
        present_set = set(present_types)
        missing = [t for t in self._required_types if t not in present_set]

        return EvidenceSufficiencyResult(
            object_id=obj.id,
            is_sufficient=len(missing) == 0,
            required_evidence_types=list(self._required_types),
            present_evidence_types=present_types,
            missing_evidence_types=missing,
        )

    def evaluate_all(self, objects: list[ControlObject]) -> list[EvidenceSufficiencyResult]:
        return [self.evaluate_object(obj) for obj in objects]

    def get_insufficient(self, objects: list[ControlObject]) -> list[EvidenceSufficiencyResult]:
        return [r for r in self.evaluate_all(objects) if not r.is_sufficient]
