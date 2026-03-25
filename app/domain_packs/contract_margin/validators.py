"""Contract & Margin deterministic validators."""

from __future__ import annotations

from typing import Any

from app.schemas.validation import RuleResult


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_VERDICTS = frozenset({
    "billable",
    "non_billable",
    "under_recovery",
    "penalty_risk",
    "unknown",
})

_CONFIDENCE_THRESHOLD = 0.5

_REQUIRED_LEAKAGE_FIELDS = frozenset({
    "trigger_type",
    "description",
    "severity",
})


# ---------------------------------------------------------------------------
# ContractMarginValidator
# ---------------------------------------------------------------------------


class ContractMarginValidator:
    """Deterministic validation of contract margin outputs.

    Every public ``validate_*`` method returns a list of :class:`RuleResult`
    objects so that results can be aggregated by the validator service.
    """

    # -- contract compile validation ----------------------------------------

    def validate_contract_compile(self, output_payload: dict) -> list[RuleResult]:
        """Validate contract compile outputs for structural completeness."""
        results: list[RuleResult] = []

        # Rule 1: has clauses
        clauses = output_payload.get("clauses", [])
        results.append(RuleResult(
            rule_name="has_clauses",
            passed=len(clauses) > 0,
            message=f"Compile produced {len(clauses)} clause(s)"
            if clauses
            else "No clauses found in compile output",
            severity="error" if not clauses else "info",
        ))

        # Rule 2: has SLA entries
        sla_entries = output_payload.get("sla_entries", [])
        results.append(RuleResult(
            rule_name="has_sla_entries",
            passed=len(sla_entries) > 0,
            message=f"Compile produced {len(sla_entries)} SLA entry/entries"
            if sla_entries
            else "No SLA entries found in compile output",
            severity="warning" if not sla_entries else "info",
        ))

        # Rule 3: obligations present
        obligations = output_payload.get("obligations", [])
        results.append(RuleResult(
            rule_name="obligations_present",
            passed=len(obligations) > 0,
            message=f"Compile produced {len(obligations)} obligation(s)"
            if obligations
            else "No obligations found in compile output",
            severity="warning" if not obligations else "info",
        ))

        # Rule 4: rate card present
        rate_card = output_payload.get("rate_card_entries", [])
        results.append(RuleResult(
            rule_name="rate_card_present",
            passed=len(rate_card) > 0,
            message=f"Compile produced {len(rate_card)} rate card entry/entries"
            if rate_card
            else "No rate card entries found in compile output",
            severity="warning" if not rate_card else "info",
        ))

        # Rule 5: scope boundaries defined
        scope_boundaries = output_payload.get("scope_boundaries", [])
        results.append(RuleResult(
            rule_name="scope_boundaries_defined",
            passed=len(scope_boundaries) > 0,
            message=f"Compile produced {len(scope_boundaries)} scope boundary/boundaries"
            if scope_boundaries
            else "No scope boundaries found in compile output",
            severity="warning" if not scope_boundaries else "info",
        ))

        return results

    # -- billability decision validation ------------------------------------

    def validate_billability_decision(self, decision: dict) -> list[RuleResult]:
        """Validate a billability decision for required fields and thresholds."""
        results: list[RuleResult] = []

        # Rule 1: confidence threshold
        confidence = decision.get("confidence")
        if confidence is None:
            results.append(RuleResult(
                rule_name="confidence_threshold",
                passed=False,
                message="Confidence value is missing from billability decision",
                severity="error",
            ))
        else:
            meets_threshold = confidence >= _CONFIDENCE_THRESHOLD
            results.append(RuleResult(
                rule_name="confidence_threshold",
                passed=meets_threshold,
                message=f"Confidence {confidence:.2f} meets threshold"
                if meets_threshold
                else f"Confidence {confidence:.2f} is below minimum threshold of {_CONFIDENCE_THRESHOLD}",
                severity="error" if not meets_threshold else "info",
            ))

        # Rule 2: rate applied
        billable = decision.get("billable", False)
        rate_applied = decision.get("rate_applied")
        if billable:
            has_rate = rate_applied is not None and rate_applied > 0
            results.append(RuleResult(
                rule_name="rate_applied",
                passed=has_rate,
                message=f"Rate of {rate_applied} applied to billable decision"
                if has_rate
                else "Billable decision is missing an applied rate",
                severity="error" if not has_rate else "info",
            ))
        else:
            # Non-billable decisions do not require a rate
            results.append(RuleResult(
                rule_name="rate_applied",
                passed=True,
                message="Non-billable decision; rate not required",
                severity="info",
            ))

        # Rule 3: evidence present
        evidence_ids = decision.get("evidence_ids", [])
        has_evidence = len(evidence_ids) > 0
        results.append(RuleResult(
            rule_name="evidence_present",
            passed=has_evidence,
            message=f"Decision backed by {len(evidence_ids)} evidence item(s)"
            if has_evidence
            else "No evidence IDs provided for billability decision",
            severity="warning" if not has_evidence else "info",
        ))

        return results

    # -- margin diagnosis validation ----------------------------------------

    def validate_margin_diagnosis(self, diagnosis: dict) -> list[RuleResult]:
        """Validate margin diagnosis output for completeness and consistency."""
        results: list[RuleResult] = []

        # Rule 1: verdict is valid
        verdict = diagnosis.get("verdict", "")
        verdict_valid = verdict in _VALID_VERDICTS
        results.append(RuleResult(
            rule_name="verdict_valid",
            passed=verdict_valid,
            message=f"Verdict '{verdict}' is valid"
            if verdict_valid
            else f"Verdict '{verdict}' is not a recognized verdict value",
            severity="error" if not verdict_valid else "info",
        ))

        # Rule 2: evidence present
        evidence_ids = diagnosis.get("evidence_ids", [])
        has_evidence = len(evidence_ids) > 0
        results.append(RuleResult(
            rule_name="evidence_present",
            passed=has_evidence,
            message=f"Diagnosis backed by {len(evidence_ids)} evidence item(s)"
            if has_evidence
            else "No evidence IDs provided for margin diagnosis",
            severity="warning" if not has_evidence else "info",
        ))

        # Rule 3: recovery recommendations when leakage detected
        leakage_verdicts = {"under_recovery", "penalty_risk"}
        if verdict in leakage_verdicts:
            recovery = diagnosis.get("recovery_recommendations", [])
            has_recovery = len(recovery) > 0
            results.append(RuleResult(
                rule_name="recovery_recommendations_present",
                passed=has_recovery,
                message=f"{len(recovery)} recovery recommendation(s) provided for leakage verdict"
                if has_recovery
                else f"Verdict '{verdict}' indicates leakage but no recovery recommendations provided",
                severity="error" if not has_recovery else "info",
            ))
        else:
            results.append(RuleResult(
                rule_name="recovery_recommendations_present",
                passed=True,
                message="No leakage verdict; recovery recommendations not required",
                severity="info",
            ))

        # Rule 4: confidence threshold
        confidence = diagnosis.get("confidence")
        if confidence is None:
            results.append(RuleResult(
                rule_name="confidence_threshold",
                passed=False,
                message="Confidence value is missing from margin diagnosis",
                severity="error",
            ))
        else:
            meets_threshold = confidence >= _CONFIDENCE_THRESHOLD
            results.append(RuleResult(
                rule_name="confidence_threshold",
                passed=meets_threshold,
                message=f"Diagnosis confidence {confidence:.2f} meets threshold"
                if meets_threshold
                else f"Diagnosis confidence {confidence:.2f} is below minimum threshold of {_CONFIDENCE_THRESHOLD}",
                severity="error" if not meets_threshold else "info",
            ))

        return results

    # -- leakage trigger validation -----------------------------------------

    def validate_leakage_triggers(self, triggers: list[dict]) -> list[RuleResult]:
        """Validate that leakage triggers have all required fields."""
        results: list[RuleResult] = []

        if not triggers:
            results.append(RuleResult(
                rule_name="leakage_triggers_present",
                passed=True,
                message="No leakage triggers to validate",
                severity="info",
            ))
            return results

        results.append(RuleResult(
            rule_name="leakage_triggers_present",
            passed=True,
            message=f"{len(triggers)} leakage trigger(s) to validate",
            severity="info",
        ))

        for idx, trigger in enumerate(triggers):
            missing_fields = _REQUIRED_LEAKAGE_FIELDS - set(trigger.keys())
            if missing_fields:
                results.append(RuleResult(
                    rule_name=f"leakage_trigger_{idx}_required_fields",
                    passed=False,
                    message=f"Trigger at index {idx} is missing required fields: {', '.join(sorted(missing_fields))}",
                    severity="error",
                ))
            else:
                results.append(RuleResult(
                    rule_name=f"leakage_trigger_{idx}_required_fields",
                    passed=True,
                    message=f"Trigger at index {idx} has all required fields",
                    severity="info",
                ))

            # Validate severity value when present
            severity_val = trigger.get("severity", "")
            valid_severities = {"info", "warning", "error", "critical"}
            if severity_val and severity_val not in valid_severities:
                results.append(RuleResult(
                    rule_name=f"leakage_trigger_{idx}_severity_valid",
                    passed=False,
                    message=f"Trigger at index {idx} has invalid severity '{severity_val}'",
                    severity="warning",
                ))
            elif severity_val:
                results.append(RuleResult(
                    rule_name=f"leakage_trigger_{idx}_severity_valid",
                    passed=True,
                    message=f"Trigger at index {idx} severity '{severity_val}' is valid",
                    severity="info",
                ))

        return results

    # -- main entry point ---------------------------------------------------

    def validate(self, domain: str, output_payload: dict) -> list[RuleResult]:
        """Route to specific validators based on payload content.

        Inspects the keys present in *output_payload* to determine which
        validation methods to invoke.  All applicable rule results are
        aggregated and returned.
        """
        results: list[RuleResult] = []

        # Contract compile output — identified by presence of 'clauses' key
        if "clauses" in output_payload:
            results.extend(self.validate_contract_compile(output_payload))

        # Billability decision — identified by presence of 'billable' key
        if "billable" in output_payload:
            results.extend(self.validate_billability_decision(output_payload))

        # Margin diagnosis — identified by presence of 'verdict' key
        if "verdict" in output_payload:
            results.extend(self.validate_margin_diagnosis(output_payload))

        # Leakage triggers — identified by presence of 'leakage_triggers' key
        if "leakage_triggers" in output_payload:
            triggers = output_payload["leakage_triggers"]
            if isinstance(triggers, list):
                results.extend(self.validate_leakage_triggers(triggers))

        # If nothing matched, report an unrecognized payload
        if not results:
            results.append(RuleResult(
                rule_name="payload_recognized",
                passed=False,
                message=f"Unrecognized payload structure for domain '{domain}'; "
                        f"no applicable validators found",
                severity="warning",
            ))

        return results
