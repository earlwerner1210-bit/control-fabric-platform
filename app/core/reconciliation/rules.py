"""Built-in reconciliation rules — deterministic cross-plane checks."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.control_object import ControlObject
from app.core.reconciliation.types import (
    Mismatch,
    MismatchCategory,
    MismatchSeverity,
)
from app.core.types import ControlObjectId, PlaneType


class ReconciliationRule(Protocol):
    """Protocol for reconciliation rules."""

    rule_id: str

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
    ) -> list[Mismatch]: ...


class RateDeviationRule:
    """Checks for rate deviations between commercial and field objects."""

    rule_id = "rate_deviation"

    def __init__(
        self,
        rate_field: str = "rate",
        threshold: float = 0.01,
    ) -> None:
        self._rate_field = rate_field
        self._threshold = threshold

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
    ) -> list[Mismatch]:
        source_rate = source.payload.get(self._rate_field)
        target_rate = target.payload.get(self._rate_field)
        if source_rate is None or target_rate is None:
            return []
        try:
            s_val = float(source_rate)
            t_val = float(target_rate)
        except (ValueError, TypeError):
            return []
        if abs(s_val - t_val) > self._threshold:
            return [
                Mismatch(
                    category=MismatchCategory.RATE_DEVIATION,
                    severity=MismatchSeverity.HIGH,
                    source_object_id=source.id,
                    target_object_id=target.id,
                    source_plane=source.plane,
                    target_plane=target.plane,
                    description=(
                        f"Rate deviation: {s_val} vs {t_val} (threshold: {self._threshold})"
                    ),
                    expected_value=s_val,
                    actual_value=t_val,
                    deviation=abs(s_val - t_val),
                    rule_id=self.rule_id,
                    metadata={"financial_impact": abs(s_val - t_val)},
                )
            ]
        return []


class QuantityDiscrepancyRule:
    """Checks for quantity mismatches."""

    rule_id = "quantity_discrepancy"

    def __init__(self, qty_field: str = "quantity") -> None:
        self._qty_field = qty_field

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
    ) -> list[Mismatch]:
        source_qty = source.payload.get(self._qty_field)
        target_qty = target.payload.get(self._qty_field)
        if source_qty is None or target_qty is None:
            return []
        try:
            s_val = float(source_qty)
            t_val = float(target_qty)
        except (ValueError, TypeError):
            return []
        if s_val != t_val:
            return [
                Mismatch(
                    category=MismatchCategory.QUANTITY_DISCREPANCY,
                    severity=MismatchSeverity.MEDIUM,
                    source_object_id=source.id,
                    target_object_id=target.id,
                    source_plane=source.plane,
                    target_plane=target.plane,
                    description=f"Quantity mismatch: {s_val} vs {t_val}",
                    expected_value=s_val,
                    actual_value=t_val,
                    deviation=abs(s_val - t_val),
                    rule_id=self.rule_id,
                )
            ]
        return []


class ObligationUnmetRule:
    """Checks if obligations have corresponding fulfillment evidence."""

    rule_id = "obligation_unmet"

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
    ) -> list[Mismatch]:
        if source.payload.get("obligation_status") == "unmet":
            return [
                Mismatch(
                    category=MismatchCategory.OBLIGATION_UNMET,
                    severity=MismatchSeverity.HIGH,
                    source_object_id=source.id,
                    target_object_id=target.id,
                    source_plane=source.plane,
                    target_plane=target.plane,
                    description=(
                        f"Obligation '{source.label}' is unmet with no "
                        f"fulfillment from '{target.label}'"
                    ),
                    rule_id=self.rule_id,
                )
            ]
        return []


class ScopeMatchRule:
    """Checks for scope alignment between cross-plane objects."""

    rule_id = "scope_mismatch"

    def __init__(self, scope_field: str = "scope") -> None:
        self._scope_field = scope_field

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
    ) -> list[Mismatch]:
        source_scope = source.payload.get(self._scope_field)
        target_scope = target.payload.get(self._scope_field)
        if source_scope is None or target_scope is None:
            return []
        if source_scope != target_scope:
            return [
                Mismatch(
                    category=MismatchCategory.SCOPE_MISMATCH,
                    severity=MismatchSeverity.MEDIUM,
                    source_object_id=source.id,
                    target_object_id=target.id,
                    source_plane=source.plane,
                    target_plane=target.plane,
                    description=(f"Scope mismatch: '{source_scope}' vs '{target_scope}'"),
                    expected_value=source_scope,
                    actual_value=target_scope,
                    rule_id=self.rule_id,
                )
            ]
        return []


class BillingWithoutCompletionRule:
    """Flags billing events without matching work completion."""

    rule_id = "billing_without_completion"

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
    ) -> list[Mismatch]:
        is_billing = source.payload.get("is_billed", False)
        is_completed = target.payload.get("is_completed", False)
        if is_billing and not is_completed:
            return [
                Mismatch(
                    category=MismatchCategory.BILLING_WITHOUT_COMPLETION,
                    severity=MismatchSeverity.CRITICAL,
                    source_object_id=source.id,
                    target_object_id=target.id,
                    source_plane=source.plane,
                    target_plane=target.plane,
                    description=(
                        f"Billing event '{source.label}' has no matching "
                        f"completion for '{target.label}'"
                    ),
                    rule_id=self.rule_id,
                )
            ]
        return []


class MissingEvidenceRule:
    """Flags objects that lack required evidence."""

    rule_id = "missing_evidence"

    def __init__(self, required_evidence_types: list[str] | None = None) -> None:
        self._required = required_evidence_types or []

    def evaluate(
        self,
        source: ControlObject,
        target: ControlObject,
    ) -> list[Mismatch]:
        mismatches: list[Mismatch] = []
        for obj in (source, target):
            existing_types = {e.evidence_type for e in obj.evidence}
            for req in self._required:
                if req not in existing_types:
                    mismatches.append(
                        Mismatch(
                            category=MismatchCategory.MISSING_EVIDENCE,
                            severity=MismatchSeverity.MEDIUM,
                            source_object_id=source.id,
                            target_object_id=target.id,
                            source_plane=source.plane,
                            target_plane=target.plane,
                            description=(
                                f"Object '{obj.label}' missing required evidence type: {req}"
                            ),
                            rule_id=self.rule_id,
                        )
                    )
        return mismatches


DEFAULT_RULES: list[ReconciliationRule] = [
    RateDeviationRule(),
    QuantityDiscrepancyRule(),
    ObligationUnmetRule(),
    ScopeMatchRule(),
    BillingWithoutCompletionRule(),
    MissingEvidenceRule(),
]
