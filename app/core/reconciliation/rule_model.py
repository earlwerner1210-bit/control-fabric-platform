"""Wave 2 reconciliation rule model — typed, inspectable, extensible rule system."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.control_link import ControlLink
from app.core.control_object import ControlObject
from app.core.reconciliation.domain_types import (
    CrossPlaneMismatchCategory,
    MatchScore,
    ReconciliationMismatch,
    ReconciliationRuleId,
    ReconciliationRuleVersion,
)
from app.core.types import ControlLinkType, ControlObjectType, EvidenceRef, PlaneType


class ReconciliationRuleCategory(str, enum.Enum):
    IDENTITY_CORRELATION = "identity-correlation"
    EXTERNAL_REFERENCE_CORRELATION = "external-reference-correlation"
    TOPOLOGY_LINKAGE = "topology-linkage"
    STATE_ALIGNMENT = "state-alignment"
    QUANTITY_ALIGNMENT = "quantity-alignment"
    COST_ALIGNMENT = "cost-alignment"
    CHRONOLOGY_ALIGNMENT = "chronology-alignment"
    COVERAGE_EXPECTATION = "coverage-expectation"
    EVIDENCE_SUFFICIENCY = "evidence-sufficiency"


class ReconciliationRuleWeight(BaseModel):
    rule_id: ReconciliationRuleId
    weight: float = 1.0
    is_hard_fail: bool = False
    required_for_match: bool = False


class ReconciliationRuleApplicability(BaseModel):
    applicable_planes: list[PlaneType] = Field(default_factory=list)
    applicable_object_types: list[ControlObjectType] = Field(default_factory=list)
    applicable_object_kinds: list[str] = Field(default_factory=list)
    applicable_link_types: list[ControlLinkType] = Field(default_factory=list)
    requires_cross_plane: bool = False

    def matches_planes(self, source_plane: PlaneType, target_plane: PlaneType) -> bool:
        if not self.applicable_planes:
            return True
        return source_plane in self.applicable_planes or target_plane in self.applicable_planes

    def matches_object(self, obj: ControlObject) -> bool:
        if self.applicable_object_types and obj.object_type not in self.applicable_object_types:
            return False
        if self.applicable_object_kinds and obj.object_kind not in self.applicable_object_kinds:
            return False
        return True

    def is_applicable(
        self,
        source: ControlObject,
        target: ControlObject,
    ) -> bool:
        if not self.matches_planes(source.plane, target.plane):
            return False
        if self.requires_cross_plane and source.plane == target.plane:
            return False
        if self.applicable_object_types:
            if (
                source.object_type not in self.applicable_object_types
                and target.object_type not in self.applicable_object_types
            ):
                return False
        return True


class ReconciliationRuleExplanation(BaseModel):
    rule_id: ReconciliationRuleId
    description: str
    score_contribution: float = 0.0
    matched: bool = False
    hard_fail: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ReconciliationRuleTraceEntry(BaseModel):
    rule_id: ReconciliationRuleId
    rule_version: ReconciliationRuleVersion = ReconciliationRuleVersion(1)
    category: ReconciliationRuleCategory
    source_object_id: str
    target_object_id: str
    applied: bool = True
    explanation: ReconciliationRuleExplanation | None = None
    mismatches_found: list[ReconciliationMismatch] = Field(default_factory=list)
    score_contribution: float = 0.0


class ReconciliationRuleResult(BaseModel):
    rule_id: ReconciliationRuleId
    score_contribution: float = 0.0
    matched: bool = False
    hard_fail: bool = False
    mismatches: list[ReconciliationMismatch] = Field(default_factory=list)
    explanation: ReconciliationRuleExplanation | None = None
    required_evidence: list[str] = Field(default_factory=list)


class ReconciliationRule(ABC):
    """Base class for Wave 2 reconciliation rules."""

    rule_id: ReconciliationRuleId
    rule_version: ReconciliationRuleVersion = ReconciliationRuleVersion(1)
    category: ReconciliationRuleCategory
    weight: ReconciliationRuleWeight
    applicability: ReconciliationRuleApplicability

    @abstractmethod
    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
        links: list[ControlLink],
    ) -> ReconciliationRuleResult: ...

    def is_applicable(self, source: ControlObject, target: ControlObject) -> bool:
        return self.applicability.is_applicable(source, target)


class IdentityCorrelationRule(ReconciliationRule):
    """Matches objects by correlation keys."""

    rule_id = ReconciliationRuleId("identity-correlation")
    category = ReconciliationRuleCategory.IDENTITY_CORRELATION
    weight = ReconciliationRuleWeight(
        rule_id=ReconciliationRuleId("identity-correlation"),
        weight=2.0,
        required_for_match=True,
    )
    applicability = ReconciliationRuleApplicability(requires_cross_plane=True)

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
        links: list[ControlLink],
    ) -> ReconciliationRuleResult:
        matching_keys: list[str] = []
        for key, val in source.correlation_keys.items():
            if target.correlation_keys.get(key) == val and val:
                matching_keys.append(key)

        if matching_keys:
            score = min(len(matching_keys) * 0.5, 1.0)
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=score * self.weight.weight,
                matched=True,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"Matched on correlation keys: {matching_keys}",
                    score_contribution=score * self.weight.weight,
                    matched=True,
                    details={"matching_keys": matching_keys},
                ),
            )
        return ReconciliationRuleResult(
            rule_id=self.rule_id,
            score_contribution=0.0,
            matched=False,
            explanation=ReconciliationRuleExplanation(
                rule_id=self.rule_id,
                description="No matching correlation keys found",
                score_contribution=0.0,
                matched=False,
            ),
        )


class ExternalReferenceCorrelationRule(ReconciliationRule):
    """Matches objects by external system references."""

    rule_id = ReconciliationRuleId("external-reference-correlation")
    category = ReconciliationRuleCategory.EXTERNAL_REFERENCE_CORRELATION
    weight = ReconciliationRuleWeight(
        rule_id=ReconciliationRuleId("external-reference-correlation"),
        weight=1.5,
    )
    applicability = ReconciliationRuleApplicability()

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
        links: list[ControlLink],
    ) -> ReconciliationRuleResult:
        matching_refs: list[str] = []
        for key, val in source.external_refs.items():
            if target.external_refs.get(key) == val and val:
                matching_refs.append(key)

        if matching_refs:
            score = min(len(matching_refs) * 0.4, 1.0)
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=score * self.weight.weight,
                matched=True,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"Matched on external refs: {matching_refs}",
                    score_contribution=score * self.weight.weight,
                    matched=True,
                    details={"matching_refs": matching_refs},
                ),
            )
        return ReconciliationRuleResult(
            rule_id=self.rule_id,
            score_contribution=0.0,
            matched=False,
            explanation=ReconciliationRuleExplanation(
                rule_id=self.rule_id,
                description="No matching external references",
                score_contribution=0.0,
                matched=False,
            ),
        )


class TopologyLinkageRule(ReconciliationRule):
    """Scores candidates based on existing graph links between them."""

    rule_id = ReconciliationRuleId("topology-linkage")
    category = ReconciliationRuleCategory.TOPOLOGY_LINKAGE
    weight = ReconciliationRuleWeight(
        rule_id=ReconciliationRuleId("topology-linkage"),
        weight=1.8,
    )
    applicability = ReconciliationRuleApplicability()

    SCORING_LINK_TYPES: dict[ControlLinkType, float] = {
        ControlLinkType.CORRELATES_WITH: 0.8,
        ControlLinkType.FULFILLS: 0.9,
        ControlLinkType.BILLS_FOR: 0.9,
        ControlLinkType.DERIVES_FROM: 0.6,
        ControlLinkType.EVIDENCES: 0.5,
        ControlLinkType.IMPLEMENTS: 0.7,
    }

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
        links: list[ControlLink],
    ) -> ReconciliationRuleResult:
        relevant_links: list[ControlLink] = []
        best_score = 0.0
        for link in links:
            is_between = (link.source_id == source.id and link.target_id == target.id) or (
                link.source_id == target.id and link.target_id == source.id
            )
            if is_between:
                relevant_links.append(link)
                link_score = self.SCORING_LINK_TYPES.get(link.link_type, 0.3)
                best_score = max(best_score, link_score)

        unsupported = [
            link
            for link in relevant_links
            if link.link_type == ControlLinkType.CONTRADICTS
            or link.link_type == ControlLinkType.BLOCKS
        ]

        if unsupported:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=0.0,
                matched=False,
                hard_fail=True,
                mismatches=[
                    ReconciliationMismatch(
                        category=CrossPlaneMismatchCategory.UNSUPPORTED_LINKAGE,
                        source_object_id=source.id,
                        target_object_id=target.id,
                        source_plane=source.plane,
                        target_plane=target.plane,
                        involved_link_ids=[l.id for l in unsupported],
                        description=(
                            f"Unsupported linkage between {source.label} and "
                            f"{target.label}: {[l.link_type.value for l in unsupported]}"
                        ),
                        rule_id=self.rule_id,
                    )
                ],
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description="Unsupported/contradicting linkage detected",
                    score_contribution=0.0,
                    matched=False,
                    hard_fail=True,
                ),
            )

        if relevant_links:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=best_score * self.weight.weight,
                matched=True,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"Found {len(relevant_links)} direct links",
                    score_contribution=best_score * self.weight.weight,
                    matched=True,
                    details={
                        "link_count": len(relevant_links),
                        "link_types": [l.link_type.value for l in relevant_links],
                    },
                ),
            )

        return ReconciliationRuleResult(
            rule_id=self.rule_id,
            score_contribution=0.0,
            matched=False,
            explanation=ReconciliationRuleExplanation(
                rule_id=self.rule_id,
                description="No direct graph links found",
                score_contribution=0.0,
                matched=False,
            ),
        )


class StateAlignmentRule(ReconciliationRule):
    """Checks lifecycle state consistency between cross-plane objects."""

    rule_id = ReconciliationRuleId("state-alignment")
    category = ReconciliationRuleCategory.STATE_ALIGNMENT
    weight = ReconciliationRuleWeight(
        rule_id=ReconciliationRuleId("state-alignment"),
        weight=1.0,
        is_hard_fail=False,
    )
    applicability = ReconciliationRuleApplicability(requires_cross_plane=True)

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
        links: list[ControlLink],
    ) -> ReconciliationRuleResult:
        source_state = source.state
        target_state = target.state

        if source_state == target_state:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=1.0 * self.weight.weight,
                matched=True,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"States aligned: {source_state.value}",
                    score_contribution=1.0 * self.weight.weight,
                    matched=True,
                ),
            )

        payload_state_src = source.payload.get("state", source_state.value)
        payload_state_tgt = target.payload.get("state", target_state.value)
        if payload_state_src != payload_state_tgt:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=0.0,
                matched=False,
                mismatches=[
                    ReconciliationMismatch(
                        category=CrossPlaneMismatchCategory.STATE_CONFLICT,
                        source_object_id=source.id,
                        target_object_id=target.id,
                        source_plane=source.plane,
                        target_plane=target.plane,
                        description=(
                            f"State conflict: {source.label} is {payload_state_src}, "
                            f"{target.label} is {payload_state_tgt}"
                        ),
                        expected_value=payload_state_src,
                        actual_value=payload_state_tgt,
                        rule_id=self.rule_id,
                    )
                ],
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"State mismatch: {payload_state_src} vs {payload_state_tgt}",
                    score_contribution=0.0,
                    matched=False,
                ),
            )

        return ReconciliationRuleResult(
            rule_id=self.rule_id,
            score_contribution=0.5 * self.weight.weight,
            matched=True,
            explanation=ReconciliationRuleExplanation(
                rule_id=self.rule_id,
                description="Lifecycle states differ but payload states align",
                score_contribution=0.5 * self.weight.weight,
                matched=True,
            ),
        )


class QuantityAlignmentRule(ReconciliationRule):
    """Checks quantity alignment between cross-plane objects."""

    rule_id = ReconciliationRuleId("quantity-alignment")
    category = ReconciliationRuleCategory.QUANTITY_ALIGNMENT
    weight = ReconciliationRuleWeight(
        rule_id=ReconciliationRuleId("quantity-alignment"),
        weight=1.2,
    )
    applicability = ReconciliationRuleApplicability()

    def __init__(self, quantity_field: str = "quantity", tolerance: float = 0.0) -> None:
        self._quantity_field = quantity_field
        self._tolerance = tolerance

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
        links: list[ControlLink],
    ) -> ReconciliationRuleResult:
        src_qty = source.payload.get(self._quantity_field)
        tgt_qty = target.payload.get(self._quantity_field)
        if src_qty is None or tgt_qty is None:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=0.0,
                matched=False,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"Quantity field '{self._quantity_field}' not present on both objects",
                    score_contribution=0.0,
                    matched=False,
                ),
            )
        try:
            s_val = float(src_qty)
            t_val = float(tgt_qty)
        except (ValueError, TypeError):
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=0.0,
                matched=False,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description="Quantity fields are not numeric",
                    score_contribution=0.0,
                    matched=False,
                ),
            )

        deviation = abs(s_val - t_val)
        if deviation <= self._tolerance:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=1.0 * self.weight.weight,
                matched=True,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"Quantities match: {s_val} == {t_val}",
                    score_contribution=1.0 * self.weight.weight,
                    matched=True,
                ),
            )

        return ReconciliationRuleResult(
            rule_id=self.rule_id,
            score_contribution=0.0,
            matched=False,
            mismatches=[
                ReconciliationMismatch(
                    category=CrossPlaneMismatchCategory.QUANTITY_CONFLICT,
                    source_object_id=source.id,
                    target_object_id=target.id,
                    source_plane=source.plane,
                    target_plane=target.plane,
                    description=f"Quantity conflict: {s_val} vs {t_val}",
                    expected_value=s_val,
                    actual_value=t_val,
                    deviation=deviation,
                    rule_id=self.rule_id,
                )
            ],
            explanation=ReconciliationRuleExplanation(
                rule_id=self.rule_id,
                description=f"Quantity mismatch: deviation={deviation}",
                score_contribution=0.0,
                matched=False,
            ),
        )


class CostAlignmentRule(ReconciliationRule):
    """Checks cost/rate alignment between cross-plane objects."""

    rule_id = ReconciliationRuleId("cost-alignment")
    category = ReconciliationRuleCategory.COST_ALIGNMENT
    weight = ReconciliationRuleWeight(
        rule_id=ReconciliationRuleId("cost-alignment"),
        weight=1.5,
        is_hard_fail=False,
    )
    applicability = ReconciliationRuleApplicability()

    def __init__(self, cost_field: str = "cost", threshold: float = 0.01) -> None:
        self._cost_field = cost_field
        self._threshold = threshold

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
        links: list[ControlLink],
    ) -> ReconciliationRuleResult:
        src_cost = source.payload.get(self._cost_field)
        tgt_cost = target.payload.get(self._cost_field)
        if src_cost is None or tgt_cost is None:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=0.0,
                matched=False,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"Cost field '{self._cost_field}' not present on both objects",
                    score_contribution=0.0,
                    matched=False,
                ),
            )
        try:
            s_val = float(src_cost)
            t_val = float(tgt_cost)
        except (ValueError, TypeError):
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=0.0,
                matched=False,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description="Cost fields are not numeric",
                    score_contribution=0.0,
                    matched=False,
                ),
            )

        deviation = abs(s_val - t_val)
        if deviation <= self._threshold:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=1.0 * self.weight.weight,
                matched=True,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"Costs aligned: {s_val} ~= {t_val}",
                    score_contribution=1.0 * self.weight.weight,
                    matched=True,
                ),
            )

        return ReconciliationRuleResult(
            rule_id=self.rule_id,
            score_contribution=0.0,
            matched=False,
            mismatches=[
                ReconciliationMismatch(
                    category=CrossPlaneMismatchCategory.COST_CONFLICT,
                    source_object_id=source.id,
                    target_object_id=target.id,
                    source_plane=source.plane,
                    target_plane=target.plane,
                    description=f"Cost conflict: {s_val} vs {t_val} (threshold: {self._threshold})",
                    expected_value=s_val,
                    actual_value=t_val,
                    deviation=deviation,
                    rule_id=self.rule_id,
                    metadata={"financial_impact": deviation},
                )
            ],
            explanation=ReconciliationRuleExplanation(
                rule_id=self.rule_id,
                description=f"Cost deviation: {deviation}",
                score_contribution=0.0,
                matched=False,
            ),
        )


class ChronologyAlignmentRule(ReconciliationRule):
    """Checks temporal consistency between cross-plane objects."""

    rule_id = ReconciliationRuleId("chronology-alignment")
    category = ReconciliationRuleCategory.CHRONOLOGY_ALIGNMENT
    weight = ReconciliationRuleWeight(
        rule_id=ReconciliationRuleId("chronology-alignment"),
        weight=0.8,
    )
    applicability = ReconciliationRuleApplicability()

    def __init__(self, date_field: str = "effective_date") -> None:
        self._date_field = date_field

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
        links: list[ControlLink],
    ) -> ReconciliationRuleResult:
        src_date = source.payload.get(self._date_field)
        tgt_date = target.payload.get(self._date_field)
        if src_date is None or tgt_date is None:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=0.0,
                matched=False,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"Date field '{self._date_field}' not present on both objects",
                    score_contribution=0.0,
                    matched=False,
                ),
            )

        if str(src_date) == str(tgt_date):
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=1.0 * self.weight.weight,
                matched=True,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"Dates aligned: {src_date}",
                    score_contribution=1.0 * self.weight.weight,
                    matched=True,
                ),
            )

        return ReconciliationRuleResult(
            rule_id=self.rule_id,
            score_contribution=0.0,
            matched=False,
            mismatches=[
                ReconciliationMismatch(
                    category=CrossPlaneMismatchCategory.CHRONOLOGY_CONFLICT,
                    source_object_id=source.id,
                    target_object_id=target.id,
                    source_plane=source.plane,
                    target_plane=target.plane,
                    description=f"Chronology conflict: {src_date} vs {tgt_date}",
                    expected_value=str(src_date),
                    actual_value=str(tgt_date),
                    rule_id=self.rule_id,
                )
            ],
            explanation=ReconciliationRuleExplanation(
                rule_id=self.rule_id,
                description=f"Date mismatch: {src_date} vs {tgt_date}",
                score_contribution=0.0,
                matched=False,
            ),
        )


class CoverageExpectationRule(ReconciliationRule):
    """Checks that expected cross-plane coverage exists."""

    rule_id = ReconciliationRuleId("coverage-expectation")
    category = ReconciliationRuleCategory.COVERAGE_EXPECTATION
    weight = ReconciliationRuleWeight(
        rule_id=ReconciliationRuleId("coverage-expectation"),
        weight=1.0,
    )
    applicability = ReconciliationRuleApplicability()

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
        links: list[ControlLink],
    ) -> ReconciliationRuleResult:
        has_cross_plane = any(
            link
            for link in links
            if (link.source_id == source.id or link.target_id == source.id)
            and link.is_cross_plane
        )
        if has_cross_plane:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=1.0 * self.weight.weight,
                matched=True,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description="Cross-plane coverage present",
                    score_contribution=1.0 * self.weight.weight,
                    matched=True,
                ),
            )
        return ReconciliationRuleResult(
            rule_id=self.rule_id,
            score_contribution=0.0,
            matched=False,
            explanation=ReconciliationRuleExplanation(
                rule_id=self.rule_id,
                description="No cross-plane coverage detected for source object",
                score_contribution=0.0,
                matched=False,
            ),
        )


class EvidenceSufficiencyRule(ReconciliationRule):
    """Checks that objects have sufficient evidence for reconciliation."""

    rule_id = ReconciliationRuleId("evidence-sufficiency")
    category = ReconciliationRuleCategory.EVIDENCE_SUFFICIENCY
    weight = ReconciliationRuleWeight(
        rule_id=ReconciliationRuleId("evidence-sufficiency"),
        weight=0.8,
    )
    applicability = ReconciliationRuleApplicability()

    def __init__(self, required_evidence_types: list[str] | None = None) -> None:
        self._required_types = required_evidence_types or []

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
        links: list[ControlLink],
    ) -> ReconciliationRuleResult:
        all_evidence = list(source.evidence) + list(target.evidence)
        present_types = {e.evidence_type for e in all_evidence}

        if not self._required_types:
            if all_evidence:
                return ReconciliationRuleResult(
                    rule_id=self.rule_id,
                    score_contribution=1.0 * self.weight.weight,
                    matched=True,
                    explanation=ReconciliationRuleExplanation(
                        rule_id=self.rule_id,
                        description=f"Evidence present: {len(all_evidence)} items",
                        score_contribution=1.0 * self.weight.weight,
                        matched=True,
                    ),
                )
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=0.0,
                matched=False,
                mismatches=[
                    ReconciliationMismatch(
                        category=CrossPlaneMismatchCategory.EVIDENCE_INSUFFICIENT,
                        source_object_id=source.id,
                        target_object_id=target.id,
                        source_plane=source.plane,
                        target_plane=target.plane,
                        description=f"No evidence attached to {source.label} or {target.label}",
                        rule_id=self.rule_id,
                    )
                ],
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description="No evidence found on either object",
                    score_contribution=0.0,
                    matched=False,
                ),
                required_evidence=self._required_types,
            )

        missing = [t for t in self._required_types if t not in present_types]
        if missing:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=0.0,
                matched=False,
                mismatches=[
                    ReconciliationMismatch(
                        category=CrossPlaneMismatchCategory.EVIDENCE_INSUFFICIENT,
                        source_object_id=source.id,
                        target_object_id=target.id,
                        source_plane=source.plane,
                        target_plane=target.plane,
                        description=f"Missing required evidence types: {missing}",
                        rule_id=self.rule_id,
                        metadata={"missing_types": missing},
                    )
                ],
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"Missing evidence: {missing}",
                    score_contribution=0.0,
                    matched=False,
                ),
                required_evidence=missing,
            )

        return ReconciliationRuleResult(
            rule_id=self.rule_id,
            score_contribution=1.0 * self.weight.weight,
            matched=True,
            explanation=ReconciliationRuleExplanation(
                rule_id=self.rule_id,
                description="All required evidence types present",
                score_contribution=1.0 * self.weight.weight,
                matched=True,
            ),
        )


class ReconciliationRuleSet(BaseModel):
    """A named, versioned set of reconciliation rules."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    version: ReconciliationRuleVersion = ReconciliationRuleVersion(1)
    description: str = ""
    domain: str = ""


class ReconciliationRuleRegistry:
    """Registry of Wave 2 reconciliation rules, extensible by domain packs."""

    def __init__(self) -> None:
        self._rules: dict[ReconciliationRuleId, ReconciliationRule] = {}
        self._rule_sets: dict[str, list[ReconciliationRuleId]] = {}

    def register_rule(self, rule: ReconciliationRule) -> None:
        self._rules[rule.rule_id] = rule

    def get_rule(self, rule_id: ReconciliationRuleId) -> ReconciliationRule | None:
        return self._rules.get(rule_id)

    def list_rules(self) -> list[ReconciliationRule]:
        return list(self._rules.values())

    def get_applicable_rules(
        self,
        source: ControlObject,
        target: ControlObject,
    ) -> list[ReconciliationRule]:
        return [r for r in self._rules.values() if r.is_applicable(source, target)]

    def register_rule_set(self, name: str, rule_ids: list[ReconciliationRuleId]) -> None:
        self._rule_sets[name] = list(rule_ids)

    def get_rule_set(self, name: str) -> list[ReconciliationRule]:
        ids = self._rule_sets.get(name, [])
        return [self._rules[rid] for rid in ids if rid in self._rules]

    @property
    def rule_count(self) -> int:
        return len(self._rules)


DEFAULT_WAVE2_RULES: list[ReconciliationRule] = [
    IdentityCorrelationRule(),
    ExternalReferenceCorrelationRule(),
    TopologyLinkageRule(),
    StateAlignmentRule(),
    QuantityAlignmentRule(),
    CostAlignmentRule(),
    ChronologyAlignmentRule(),
    CoverageExpectationRule(),
    EvidenceSufficiencyRule(),
]


def build_default_rule_registry() -> ReconciliationRuleRegistry:
    registry = ReconciliationRuleRegistry()
    rule_ids: list[ReconciliationRuleId] = []
    for rule in DEFAULT_WAVE2_RULES:
        registry.register_rule(rule)
        rule_ids.append(rule.rule_id)
    registry.register_rule_set("default-cross-plane", rule_ids)
    return registry
