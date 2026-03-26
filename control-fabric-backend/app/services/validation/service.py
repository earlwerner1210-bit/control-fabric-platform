"""Validation service -- deterministic rule-based checks on workflow outputs."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.schemas.workflows import ValidationStatus

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _result(
    target_type: str,
    target_id: UUID,
    rule_name: str,
    passed: bool,
    severity: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": uuid4(),
        "target_type": target_type,
        "target_id": target_id,
        "rule_name": rule_name,
        "passed": passed,
        "severity": severity,
        "details": details or {},
        "created_at": _now(),
    }


class ValidationService:
    """Deterministic, rule-based validation layer.

    Every LLM output or workflow result must pass through this service before
    being surfaced to users or persisted as a final decision.
    """

    # ── Contract compile validation ───────────────────────────────────────

    def validate_contract_compile(
        self,
        compile_result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Run validation rules against a contract-compile output."""
        target_id = compile_result.get("case_id", uuid4())
        results: list[dict[str, Any]] = []

        # Rule 1: Must have at least one obligation
        obligation_count = compile_result.get("obligation_count", 0)
        results.append(
            _result(
                "contract_compile",
                target_id,
                "min_obligations",
                passed=obligation_count > 0,
                severity="error",
                details={"obligation_count": obligation_count, "threshold": 1},
            )
        )

        # Rule 2: Contract summary must be non-empty
        summary = compile_result.get("contract_summary") or ""
        results.append(
            _result(
                "contract_compile",
                target_id,
                "summary_present",
                passed=len(summary.strip()) > 0,
                severity="warning",
                details={"summary_length": len(summary)},
            )
        )

        # Rule 3: No compile errors
        errors = compile_result.get("errors", [])
        results.append(
            _result(
                "contract_compile",
                target_id,
                "no_compile_errors",
                passed=len(errors) == 0,
                severity="error",
                details={"error_count": len(errors), "errors": errors[:5]},
            )
        )

        # Rule 4: Control objects must exist
        co_ids = compile_result.get("control_object_ids", [])
        results.append(
            _result(
                "contract_compile",
                target_id,
                "control_objects_created",
                passed=len(co_ids) > 0,
                severity="error",
                details={"control_object_count": len(co_ids)},
            )
        )

        logger.info(
            "validation.contract_compile: case=%s passed=%d/%d",
            target_id,
            sum(1 for r in results if r["passed"]),
            len(results),
        )
        return results

    # ── Billability decision validation ───────────────────────────────────

    def validate_billability_decision(
        self,
        decision: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Validate a billability determination."""
        target_id = decision.get("id", uuid4())
        results: list[dict[str, Any]] = []

        # Rule 1: Verdict must be a known value
        verdict = decision.get("verdict", "")
        valid_verdicts = {"billable", "non_billable", "under_recovery", "penalty_risk", "unknown"}
        results.append(
            _result(
                "billability_decision",
                target_id,
                "valid_verdict",
                passed=verdict in valid_verdicts,
                severity="critical",
                details={"verdict": verdict, "allowed": list(valid_verdicts)},
            )
        )

        # Rule 2: Evidence object IDs should be present
        evidence = decision.get("evidence_object_ids", [])
        results.append(
            _result(
                "billability_decision",
                target_id,
                "evidence_present",
                passed=len(evidence) > 0,
                severity="warning",
                details={"evidence_count": len(evidence)},
            )
        )

        # Rule 3: Confidence gating -- if a confidence score exists, it must be >= 0.6
        confidence = decision.get("confidence")
        if confidence is not None:
            results.append(
                _result(
                    "billability_decision",
                    target_id,
                    "confidence_threshold",
                    passed=float(confidence) >= 0.6,
                    severity="error",
                    details={"confidence": confidence, "threshold": 0.6},
                )
            )

        logger.info(
            "validation.billability: target=%s passed=%d/%d",
            target_id,
            sum(1 for r in results if r["passed"]),
            len(results),
        )
        return results

    # ── Margin diagnosis validation ───────────────────────────────────────

    def validate_margin_diagnosis(
        self,
        diagnosis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Validate a margin-diagnosis workflow output."""
        target_id = diagnosis.get("case_id", uuid4())
        results: list[dict[str, Any]] = []

        # Rule 1: Executive summary required
        summary = diagnosis.get("executive_summary") or ""
        results.append(
            _result(
                "margin_diagnosis",
                target_id,
                "executive_summary_present",
                passed=len(summary.strip()) > 10,
                severity="warning",
                details={"summary_length": len(summary)},
            )
        )

        # Rule 2: Verdict must be known
        verdict = diagnosis.get("verdict", "")
        valid_verdicts = {"billable", "non_billable", "under_recovery", "penalty_risk", "unknown"}
        results.append(
            _result(
                "margin_diagnosis",
                target_id,
                "valid_verdict",
                passed=verdict in valid_verdicts,
                severity="critical",
                details={"verdict": verdict},
            )
        )

        # Rule 3: Leakage drivers should be populated when verdict indicates issues
        leakage = diagnosis.get("leakage_drivers", [])
        needs_leakage = verdict in {"under_recovery", "penalty_risk"}
        results.append(
            _result(
                "margin_diagnosis",
                target_id,
                "leakage_drivers_populated",
                passed=(not needs_leakage) or len(leakage) > 0,
                severity="error",
                details={"verdict": verdict, "leakage_count": len(leakage)},
            )
        )

        # Rule 4: Recovery recommendations when under_recovery
        recs = diagnosis.get("recovery_recommendations", [])
        needs_recs = verdict == "under_recovery"
        results.append(
            _result(
                "margin_diagnosis",
                target_id,
                "recovery_recommendations_populated",
                passed=(not needs_recs) or len(recs) > 0,
                severity="warning",
                details={"verdict": verdict, "recommendation_count": len(recs)},
            )
        )

        # Rule 5: Schema completeness -- required top-level keys
        required_keys = {"verdict", "leakage_drivers", "executive_summary"}
        missing = required_keys - set(diagnosis.keys())
        results.append(
            _result(
                "margin_diagnosis",
                target_id,
                "schema_completeness",
                passed=len(missing) == 0,
                severity="error",
                details={"missing_keys": list(missing)},
            )
        )

        logger.info(
            "validation.margin_diagnosis: case=%s passed=%d/%d",
            target_id,
            sum(1 for r in results if r["passed"]),
            len(results),
        )
        return results

    # ── Aggregate status ──────────────────────────────────────────────────

    @staticmethod
    def determine_final_status(
        validations: list[dict[str, Any]],
    ) -> ValidationStatus:
        """Derive an aggregate validation status from individual results.

        Priority order: any critical failure -> ESCALATE, any error failure -> BLOCKED,
        any warning failure -> WARN, else APPROVED.
        """
        has_critical_fail = any(
            not v["passed"] and v["severity"] == "critical" for v in validations
        )
        has_error_fail = any(
            not v["passed"] and v["severity"] == "error" for v in validations
        )
        has_warning_fail = any(
            not v["passed"] and v["severity"] == "warning" for v in validations
        )

        if has_critical_fail:
            return ValidationStatus.ESCALATE
        if has_error_fail:
            return ValidationStatus.BLOCKED
        if has_warning_fail:
            return ValidationStatus.WARN
        return ValidationStatus.APPROVED


# Singleton
validation_service = ValidationService()
