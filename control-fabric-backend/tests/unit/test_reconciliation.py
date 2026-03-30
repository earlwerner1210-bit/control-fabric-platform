"""Unit tests for reconciliation components.

Tests cover linkers, evidence assembler, conflict detector, and margin reconciler.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.domain_packs.contract_margin.schemas.contract import (
    BillabilityDecision,
    BillableCategory,
    CommercialEvidenceBundle,
    LeakageTrigger,
    MarginDiagnosisResult,
    PriorityLevel,
)

# ── Reconciliation components ────────────────────────────────────────────────


class ControlObjectLinker:
    """Links work order activities to contract control objects."""

    def link(self, activity: str, control_objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return control objects whose label matches the activity."""
        return [co for co in control_objects if activity.lower() in co.get("label", "").lower()]


class EvidenceAssembler:
    """Assemble evidence bundles from multiple sources."""

    def assemble(
        self,
        contract_refs: list[str],
        work_order_refs: list[str],
        execution_refs: list[str],
        billing_refs: list[str],
    ) -> CommercialEvidenceBundle:
        gaps: list[str] = []
        if not contract_refs:
            gaps.append("No contract evidence provided")
        if not work_order_refs:
            gaps.append("No work order evidence provided")
        if not execution_refs:
            gaps.append("No execution evidence provided")
        if not billing_refs:
            gaps.append("No billing evidence provided")
        return CommercialEvidenceBundle(
            contract_evidence=contract_refs,
            work_order_evidence=work_order_refs,
            execution_evidence=execution_refs,
            billing_evidence=billing_refs,
            gaps=gaps,
        )


class ConflictDetector:
    """Detect conflicts between multiple billability decisions."""

    def detect(self, decisions: list[BillabilityDecision]) -> list[dict[str, Any]]:
        conflicts: list[dict[str, Any]] = []
        for i, d1 in enumerate(decisions):
            for j, d2 in enumerate(decisions):
                if i >= j:
                    continue
                if d1.billable != d2.billable:
                    conflicts.append(
                        {
                            "type": "verdict_mismatch",
                            "decision_a": i,
                            "decision_b": j,
                            "detail": f"Decision {i} says {'billable' if d1.billable else 'non-billable'}, "
                            f"Decision {j} says {'billable' if d2.billable else 'non-billable'}",
                        }
                    )
                if d1.rate_applied != d2.rate_applied and d1.billable and d2.billable:
                    conflicts.append(
                        {
                            "type": "rate_mismatch",
                            "decision_a": i,
                            "decision_b": j,
                            "detail": f"Rate {d1.rate_applied} vs {d2.rate_applied}",
                        }
                    )
        return conflicts


class MarginReconciler:
    """Reconcile margin diagnosis from billability, leakage, and evidence."""

    def reconcile(
        self,
        billability: BillabilityDecision,
        leakage_triggers: list[LeakageTrigger],
        evidence: CommercialEvidenceBundle,
    ) -> MarginDiagnosisResult:
        if not billability.billable:
            verdict = "non_billable"
        elif leakage_triggers:
            verdict = "partial"
        else:
            verdict = "billable"

        total_leakage = sum(t.estimated_impact_value for t in leakage_triggers)

        return MarginDiagnosisResult(
            verdict=verdict,
            billability=billability,
            leakage_triggers=leakage_triggers,
            penalty_exposure=total_leakage,
            evidence_bundle=evidence,
            executive_summary=f"Verdict: {verdict}. Leakage: GBP {total_leakage:.2f}.",
            confidence=evidence.completeness_score() * billability.confidence,
        )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def linker() -> ControlObjectLinker:
    return ControlObjectLinker()


@pytest.fixture
def assembler() -> EvidenceAssembler:
    return EvidenceAssembler()


@pytest.fixture
def conflict_detector() -> ConflictDetector:
    return ConflictDetector()


@pytest.fixture
def reconciler() -> MarginReconciler:
    return MarginReconciler()


@pytest.fixture
def control_objects() -> list[dict[str, Any]]:
    return [
        {"id": str(uuid4()), "label": "HV Switching obligation", "type": "obligation"},
        {"id": str(uuid4()), "label": "Cable Jointing rate", "type": "rate_card_item"},
        {"id": str(uuid4()), "label": "Metering service", "type": "billable_event"},
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestControlObjectLinker:
    def test_link_match(self, linker, control_objects):
        result = linker.link("HV Switching", control_objects)
        assert len(result) == 1
        assert "HV Switching" in result[0]["label"]

    def test_link_no_match(self, linker, control_objects):
        result = linker.link("Unknown Activity", control_objects)
        assert len(result) == 0

    def test_link_case_insensitive(self, linker, control_objects):
        result = linker.link("hv switching", control_objects)
        assert len(result) == 1


class TestEvidenceAssembler:
    def test_full_evidence(self, assembler):
        bundle = assembler.assemble(["CL-001"], ["WO-001"], ["EXE-001"], ["INV-001"])
        assert bundle.completeness_score() == 1.0
        assert len(bundle.gaps) == 0

    def test_partial_evidence_gaps(self, assembler):
        bundle = assembler.assemble(["CL-001"], [], ["EXE-001"], [])
        assert bundle.completeness_score() < 1.0
        assert len(bundle.gaps) == 2

    def test_empty_evidence(self, assembler):
        bundle = assembler.assemble([], [], [], [])
        assert bundle.completeness_score() == 0.0
        assert len(bundle.gaps) == 4


class TestConflictDetector:
    def test_no_conflicts(self, conflict_detector):
        d1 = BillabilityDecision(billable=True, rate_applied=450.0, confidence=0.9)
        d2 = BillabilityDecision(billable=True, rate_applied=450.0, confidence=0.9)
        conflicts = conflict_detector.detect([d1, d2])
        assert len(conflicts) == 0

    def test_verdict_mismatch(self, conflict_detector):
        d1 = BillabilityDecision(billable=True, rate_applied=450.0, confidence=0.9)
        d2 = BillabilityDecision(billable=False, rate_applied=0.0, confidence=0.5)
        conflicts = conflict_detector.detect([d1, d2])
        assert any(c["type"] == "verdict_mismatch" for c in conflicts)

    def test_rate_mismatch(self, conflict_detector):
        d1 = BillabilityDecision(billable=True, rate_applied=450.0, confidence=0.9)
        d2 = BillabilityDecision(billable=True, rate_applied=500.0, confidence=0.9)
        conflicts = conflict_detector.detect([d1, d2])
        assert any(c["type"] == "rate_mismatch" for c in conflicts)


class TestMarginReconciler:
    def test_billable_verdict(self, reconciler):
        billability = BillabilityDecision(billable=True, rate_applied=450.0, confidence=0.9)
        evidence = CommercialEvidenceBundle(
            contract_evidence=["CL-001"],
            work_order_evidence=["WO-001"],
            execution_evidence=["EXE-001"],
            billing_evidence=["INV-001"],
        )
        result = reconciler.reconcile(billability, [], evidence)
        assert result.verdict == "billable"

    def test_non_billable_verdict(self, reconciler):
        billability = BillabilityDecision(billable=False, rate_applied=0.0, confidence=0.5)
        evidence = CommercialEvidenceBundle()
        result = reconciler.reconcile(billability, [], evidence)
        assert result.verdict == "non_billable"

    def test_partial_verdict_with_leakage(self, reconciler):
        billability = BillabilityDecision(billable=True, rate_applied=450.0, confidence=0.8)
        triggers = [
            LeakageTrigger(
                trigger_type="missing_daywork_sheet",
                description="Missing sheet",
                severity=PriorityLevel.medium,
                estimated_impact_value=100.0,
            ),
        ]
        evidence = CommercialEvidenceBundle(contract_evidence=["CL-001"])
        result = reconciler.reconcile(billability, triggers, evidence)
        assert result.verdict == "partial"
        assert result.penalty_exposure == 100.0

    def test_confidence_calculation(self, reconciler):
        billability = BillabilityDecision(billable=True, rate_applied=450.0, confidence=0.9)
        evidence = CommercialEvidenceBundle(
            contract_evidence=["CL-001"],
            work_order_evidence=["WO-001"],
        )
        result = reconciler.reconcile(billability, [], evidence)
        expected_confidence = evidence.completeness_score() * 0.9
        assert abs(result.confidence - expected_confidence) < 0.01
