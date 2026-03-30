"""Unit tests for ValidationService.

Tests cover contract compile validation, billability validation, margin diagnosis
validation, and final status determination.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain_packs.contract_margin.schemas.contract import (
    BillabilityDecision,
    ClauseType,
    ContractCompileSummary,
    ExtractedClause,
    MarginDiagnosisResult,
    ParsedContract,
    PriorityLevel,
)

# ── Validation service ──────────────────────────────────────────────────────


class ValidationService:
    """Rule-based validation for contract compile and margin diagnosis outputs."""

    def validate_contract_compile(self, contract: ParsedContract) -> list[dict[str, Any]]:
        """Validate a parsed contract meets minimum quality thresholds."""
        results: list[dict[str, Any]] = []

        # Must have at least one clause
        results.append(
            {
                "rule": "has_clauses",
                "passed": len(contract.clauses) > 0,
                "severity": "error",
                "detail": f"Found {len(contract.clauses)} clauses",
            }
        )

        # Must have a title
        results.append(
            {
                "rule": "has_title",
                "passed": bool(contract.title),
                "severity": "warning",
                "detail": f"Title: '{contract.title}'",
            }
        )

        # SLA table should be present
        results.append(
            {
                "rule": "has_sla_table",
                "passed": len(contract.sla_table) > 0,
                "severity": "warning",
                "detail": f"Found {len(contract.sla_table)} SLA entries",
            }
        )

        # Rate card should be present
        results.append(
            {
                "rule": "has_rate_card",
                "passed": len(contract.rate_card) > 0,
                "severity": "error",
                "detail": f"Found {len(contract.rate_card)} rate card entries",
            }
        )

        # All clause confidences should exceed threshold
        low_confidence = [c for c in contract.clauses if c.confidence < 0.7]
        results.append(
            {
                "rule": "clause_confidence",
                "passed": len(low_confidence) == 0,
                "severity": "warning",
                "detail": f"{len(low_confidence)} clauses below 0.7 confidence",
            }
        )

        return results

    def validate_billability(self, decision: BillabilityDecision) -> list[dict[str, Any]]:
        """Validate a billability decision."""
        results: list[dict[str, Any]] = []

        results.append(
            {
                "rule": "confidence_threshold",
                "passed": decision.confidence >= 0.7,
                "severity": "warning",
                "detail": f"Confidence: {decision.confidence}",
            }
        )

        results.append(
            {
                "rule": "has_reasons",
                "passed": len(decision.reasons) > 0 or decision.billable,
                "severity": "info",
                "detail": f"Reasons: {len(decision.reasons)}",
            }
        )

        results.append(
            {
                "rule": "has_evidence",
                "passed": len(decision.evidence_refs) > 0,
                "severity": "warning",
                "detail": f"Evidence refs: {len(decision.evidence_refs)}",
            }
        )

        return results

    def validate_margin_diagnosis(self, diagnosis: MarginDiagnosisResult) -> list[dict[str, Any]]:
        """Validate a margin diagnosis result."""
        results: list[dict[str, Any]] = []

        results.append(
            {
                "rule": "valid_verdict",
                "passed": diagnosis.verdict in ("billable", "non_billable", "partial", "review"),
                "severity": "error",
                "detail": f"Verdict: {diagnosis.verdict}",
            }
        )

        results.append(
            {
                "rule": "has_executive_summary",
                "passed": bool(diagnosis.executive_summary),
                "severity": "warning",
                "detail": "Executive summary present" if diagnosis.executive_summary else "Missing",
            }
        )

        results.append(
            {
                "rule": "evidence_completeness",
                "passed": diagnosis.evidence_bundle.completeness_score() >= 0.5,
                "severity": "warning",
                "detail": f"Score: {diagnosis.evidence_bundle.completeness_score()}",
            }
        )

        return results

    def compute_final_status(self, results: list[dict[str, Any]]) -> str:
        """Compute final validation status from a list of results."""
        has_error_failure = any(not r["passed"] and r["severity"] == "error" for r in results)
        has_warning_failure = any(not r["passed"] and r["severity"] == "warning" for r in results)

        if has_error_failure:
            return "blocked"
        elif has_warning_failure:
            return "warn"
        else:
            return "approved"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def service() -> ValidationService:
    return ValidationService()


@pytest.fixture
def valid_contract(sample_contract) -> ParsedContract:
    return ParsedContract(**sample_contract)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestValidationService:
    def test_contract_compile_valid(self, service, valid_contract):
        results = service.validate_contract_compile(valid_contract)
        assert all(r["passed"] for r in results)

    def test_contract_compile_empty(self, service):
        contract = ParsedContract()
        results = service.validate_contract_compile(contract)
        failed = [r for r in results if not r["passed"]]
        assert len(failed) >= 2  # No clauses, no rate card

    def test_billability_valid(self, service):
        decision = BillabilityDecision(
            billable=True,
            rate_applied=450.0,
            confidence=0.9,
            evidence_refs=["photo", "sheet"],
        )
        results = service.validate_billability(decision)
        assert all(r["passed"] for r in results)

    def test_billability_low_confidence(self, service):
        decision = BillabilityDecision(
            billable=False,
            rate_applied=0.0,
            confidence=0.3,
            reasons=["No rate match"],
        )
        results = service.validate_billability(decision)
        confidence_result = next(r for r in results if r["rule"] == "confidence_threshold")
        assert confidence_result["passed"] is False

    def test_margin_diagnosis_valid(self, service):
        diagnosis = MarginDiagnosisResult(
            verdict="billable",
            billability=BillabilityDecision(billable=True, rate_applied=450.0, confidence=0.9),
            executive_summary="Clean bill",
        )
        results = service.validate_margin_diagnosis(diagnosis)
        verdict_result = next(r for r in results if r["rule"] == "valid_verdict")
        assert verdict_result["passed"] is True

    def test_final_status_approved(self, service):
        results = [
            {"rule": "test", "passed": True, "severity": "error", "detail": "ok"},
            {"rule": "test2", "passed": True, "severity": "warning", "detail": "ok"},
        ]
        assert service.compute_final_status(results) == "approved"

    def test_final_status_blocked(self, service):
        results = [
            {"rule": "test", "passed": False, "severity": "error", "detail": "fail"},
        ]
        assert service.compute_final_status(results) == "blocked"

    def test_final_status_warn(self, service):
        results = [
            {"rule": "test", "passed": True, "severity": "error", "detail": "ok"},
            {"rule": "test2", "passed": False, "severity": "warning", "detail": "warn"},
        ]
        assert service.compute_final_status(results) == "warn"
