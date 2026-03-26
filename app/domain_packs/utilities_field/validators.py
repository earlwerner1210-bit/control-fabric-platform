"""Utilities Field domain validators — rule-based validation of LLM and pipeline outputs."""

from __future__ import annotations

from app.domain_packs.utilities_field.schemas import (
    ExceptionType,
    ReadinessStatus,
    RecommendationType,
    WorkOrderType,
)
from app.schemas.validation import RuleResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_VERDICTS: set[str] = {s.value for s in ReadinessStatus}
_VALID_RECOMMENDATION_TYPES: set[str] = {r.value for r in RecommendationType}
_VALID_EXCEPTION_TYPES: set[str] = {e.value for e in ExceptionType}
_HIGH_RISK_WORK_ORDER_TYPES: set[str] = {
    WorkOrderType.emergency.value,
    WorkOrderType.repair.value,
    WorkOrderType.installation.value,
}

_MIN_DISPATCH_CONFIDENCE: float = 0.5


# ---------------------------------------------------------------------------
# UtilitiesFieldValidator
# ---------------------------------------------------------------------------


class UtilitiesFieldValidator:
    """Validate utilities-field domain outputs against deterministic rules.

    Every ``validate_*`` method returns a list of :class:`RuleResult` items so
    that results can be aggregated and audited uniformly.
    """

    # -- readiness decision -------------------------------------------------

    def validate_readiness_decision(self, output_payload: dict) -> list[RuleResult]:
        """Validate a readiness-decision output.

        Checks:
        1. ``verdict`` is a valid :class:`ReadinessStatus` value.
        2. When verdict is ``blocked``, at least one reason is present.
        3. ``skill_fit`` key is present.
        4. Every blocker entry has a ``severity`` field.
        """
        results: list[RuleResult] = []

        # 1. Verdict is valid.
        verdict = output_payload.get("verdict") or output_payload.get("status")
        if verdict is None:
            results.append(
                RuleResult(
                    rule_name="readiness_verdict_present",
                    passed=False,
                    message="Readiness output missing 'verdict' or 'status' field",
                    severity="error",
                )
            )
        elif verdict not in _VALID_VERDICTS:
            results.append(
                RuleResult(
                    rule_name="readiness_verdict_valid",
                    passed=False,
                    message=f"Invalid readiness verdict '{verdict}'; expected one of {sorted(_VALID_VERDICTS)}",
                    severity="error",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="readiness_verdict_valid",
                    passed=True,
                    message=f"Readiness verdict '{verdict}' is valid",
                    severity="info",
                )
            )

        # 2. Blocked verdict must have reasons.
        if verdict == ReadinessStatus.blocked.value:
            reasons = (
                output_payload.get("reasons") or output_payload.get("missing_prerequisites") or []
            )
            if not reasons:
                results.append(
                    RuleResult(
                        rule_name="readiness_blocked_has_reasons",
                        passed=False,
                        message="Readiness verdict is 'blocked' but no reasons or missing_prerequisites provided",
                        severity="error",
                    )
                )
            else:
                results.append(
                    RuleResult(
                        rule_name="readiness_blocked_has_reasons",
                        passed=True,
                        message=f"Blocked verdict has {len(reasons)} reason(s)",
                        severity="info",
                    )
                )

        # 3. skill_fit is present.
        skill_fit = output_payload.get("skill_fit")
        if skill_fit is None:
            results.append(
                RuleResult(
                    rule_name="readiness_skill_fit_present",
                    passed=False,
                    message="Readiness output missing 'skill_fit' field",
                    severity="warning",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="readiness_skill_fit_present",
                    passed=True,
                    message="skill_fit field is present",
                    severity="info",
                )
            )

        # 4. Every blocker has severity.
        blockers = output_payload.get("blockers", [])
        if isinstance(blockers, list):
            for idx, blocker in enumerate(blockers):
                if not isinstance(blocker, dict):
                    results.append(
                        RuleResult(
                            rule_name=f"readiness_blocker_{idx}_is_dict",
                            passed=False,
                            message=f"Blocker at index {idx} is not a dict",
                            severity="error",
                        )
                    )
                    continue
                if "severity" not in blocker:
                    results.append(
                        RuleResult(
                            rule_name=f"readiness_blocker_{idx}_has_severity",
                            passed=False,
                            message=f"Blocker at index {idx} missing 'severity' field",
                            severity="warning",
                        )
                    )
                else:
                    results.append(
                        RuleResult(
                            rule_name=f"readiness_blocker_{idx}_has_severity",
                            passed=True,
                            message=f"Blocker at index {idx} has severity '{blocker['severity']}'",
                            severity="info",
                        )
                    )

        return results

    # -- dispatch recommendation --------------------------------------------

    def validate_dispatch_recommendation(self, rec: dict) -> list[RuleResult]:
        """Validate a dispatch-recommendation output.

        Checks:
        1. ``recommendation`` value is a valid :class:`RecommendationType`.
        2. At least one reason is present.
        3. ``confidence`` meets the minimum threshold.
        """
        results: list[RuleResult] = []

        # 1. Recommendation type valid.
        rec_type = rec.get("recommendation")
        if rec_type is None:
            results.append(
                RuleResult(
                    rule_name="dispatch_recommendation_present",
                    passed=False,
                    message="Dispatch recommendation missing 'recommendation' field",
                    severity="error",
                )
            )
        elif rec_type not in _VALID_RECOMMENDATION_TYPES:
            results.append(
                RuleResult(
                    rule_name="dispatch_recommendation_valid",
                    passed=False,
                    message=f"Invalid recommendation type '{rec_type}'; expected one of {sorted(_VALID_RECOMMENDATION_TYPES)}",
                    severity="error",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="dispatch_recommendation_valid",
                    passed=True,
                    message=f"Recommendation type '{rec_type}' is valid",
                    severity="info",
                )
            )

        # 2. Reasons present.
        reasons = rec.get("reasons", [])
        if not reasons:
            results.append(
                RuleResult(
                    rule_name="dispatch_reasons_present",
                    passed=False,
                    message="Dispatch recommendation has no reasons",
                    severity="warning",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="dispatch_reasons_present",
                    passed=True,
                    message=f"Dispatch recommendation has {len(reasons)} reason(s)",
                    severity="info",
                )
            )

        # 3. Confidence threshold.
        confidence = rec.get("confidence")
        if confidence is None:
            results.append(
                RuleResult(
                    rule_name="dispatch_confidence_present",
                    passed=False,
                    message="Dispatch recommendation missing 'confidence' field",
                    severity="warning",
                )
            )
        else:
            try:
                conf_val = float(confidence)
            except (TypeError, ValueError):
                results.append(
                    RuleResult(
                        rule_name="dispatch_confidence_numeric",
                        passed=False,
                        message=f"Confidence value '{confidence}' is not numeric",
                        severity="error",
                    )
                )
            else:
                meets_threshold = conf_val >= _MIN_DISPATCH_CONFIDENCE
                results.append(
                    RuleResult(
                        rule_name="dispatch_confidence_threshold",
                        passed=meets_threshold,
                        message=(
                            f"Confidence {conf_val:.2f} meets minimum threshold {_MIN_DISPATCH_CONFIDENCE}"
                            if meets_threshold
                            else f"Confidence {conf_val:.2f} below minimum threshold {_MIN_DISPATCH_CONFIDENCE}"
                        ),
                        severity="info" if meets_threshold else "warning",
                    )
                )

        return results

    # -- field exception ----------------------------------------------------

    def validate_field_exception(self, exception: dict) -> list[RuleResult]:
        """Validate a field-exception classification.

        Checks:
        1. ``exception_type`` is a valid :class:`ExceptionType`.
        2. ``root_cause`` is present and non-empty.
        """
        results: list[RuleResult] = []

        # 1. Exception type valid.
        exc_type = exception.get("exception_type")
        if exc_type is None:
            results.append(
                RuleResult(
                    rule_name="exception_type_present",
                    passed=False,
                    message="Field exception missing 'exception_type' field",
                    severity="error",
                )
            )
        elif exc_type not in _VALID_EXCEPTION_TYPES:
            results.append(
                RuleResult(
                    rule_name="exception_type_valid",
                    passed=False,
                    message=f"Invalid exception type '{exc_type}'; expected one of {sorted(_VALID_EXCEPTION_TYPES)}",
                    severity="error",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="exception_type_valid",
                    passed=True,
                    message=f"Exception type '{exc_type}' is valid",
                    severity="info",
                )
            )

        # 2. Root cause present.
        root_cause = exception.get("root_cause", "")
        if not root_cause or not str(root_cause).strip():
            results.append(
                RuleResult(
                    rule_name="exception_root_cause_present",
                    passed=False,
                    message="Field exception missing or empty 'root_cause'",
                    severity="error",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="exception_root_cause_present",
                    passed=True,
                    message="Root cause is present",
                    severity="info",
                )
            )

        return results

    # -- work order completeness --------------------------------------------

    def validate_work_order_completeness(self, wo: dict) -> list[RuleResult]:
        """Validate work-order data quality.

        Checks:
        1. Has a non-empty ``work_order_id``.
        2. Has a valid ``work_order_type``.
        3. Has at least one required skill.
        4. High-risk work-order types must have at least one permit.
        """
        results: list[RuleResult] = []
        valid_wo_types = {t.value for t in WorkOrderType}

        # 1. Work order ID present.
        wo_id = wo.get("work_order_id", "")
        if not wo_id or not str(wo_id).strip():
            results.append(
                RuleResult(
                    rule_name="wo_has_id",
                    passed=False,
                    message="Work order missing 'work_order_id'",
                    severity="error",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="wo_has_id",
                    passed=True,
                    message=f"Work order ID '{wo_id}' is present",
                    severity="info",
                )
            )

        # 2. Valid work order type.
        wo_type = wo.get("work_order_type", "")
        if wo_type not in valid_wo_types:
            results.append(
                RuleResult(
                    rule_name="wo_type_valid",
                    passed=False,
                    message=f"Invalid work order type '{wo_type}'; expected one of {sorted(valid_wo_types)}",
                    severity="error",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="wo_type_valid",
                    passed=True,
                    message=f"Work order type '{wo_type}' is valid",
                    severity="info",
                )
            )

        # 3. Has required skills.
        skills = wo.get("required_skills", [])
        if not skills:
            results.append(
                RuleResult(
                    rule_name="wo_has_skills",
                    passed=False,
                    message="Work order has no required skills defined",
                    severity="warning",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="wo_has_skills",
                    passed=True,
                    message=f"Work order has {len(skills)} required skill(s)",
                    severity="info",
                )
            )

        # 4. High-risk types must have permits.
        if wo_type in _HIGH_RISK_WORK_ORDER_TYPES:
            permits = wo.get("required_permits", [])
            if not permits:
                results.append(
                    RuleResult(
                        rule_name="wo_high_risk_has_permits",
                        passed=False,
                        message=f"High-risk work order type '{wo_type}' has no required permits defined",
                        severity="error",
                    )
                )
            else:
                results.append(
                    RuleResult(
                        rule_name="wo_high_risk_has_permits",
                        passed=True,
                        message=f"High-risk work order has {len(permits)} permit(s)",
                        severity="info",
                    )
                )

        return results

    # -- main entry point ---------------------------------------------------

    def validate(self, domain: str, output_payload: dict) -> list[RuleResult]:
        """Main validation entry point.

        Routes to the appropriate validator based on *domain* key:
        - ``readiness`` — :meth:`validate_readiness_decision`
        - ``dispatch`` — :meth:`validate_dispatch_recommendation`
        - ``exception`` — :meth:`validate_field_exception`
        - ``work_order`` — :meth:`validate_work_order_completeness`

        Returns an error :class:`RuleResult` if the domain is unrecognised.
        """
        dispatch_map = {
            "readiness": self.validate_readiness_decision,
            "dispatch": self.validate_dispatch_recommendation,
            "exception": self.validate_field_exception,
            "work_order": self.validate_work_order_completeness,
        }

        handler = dispatch_map.get(domain)
        if handler is None:
            return [
                RuleResult(
                    rule_name="domain_recognised",
                    passed=False,
                    message=f"Unrecognised utilities-field validation domain '{domain}'; expected one of {sorted(dispatch_map.keys())}",
                    severity="error",
                )
            ]

        return handler(output_payload)
