"""Telco Ops deterministic validators for LLM and workflow outputs."""

from __future__ import annotations

from app.domain_packs.telco_ops.schemas import (
    EscalationLevel,
    ImpactLevel,
    ReconciliationStatus,
    ServiceState,
)
from app.schemas.validation import RuleResult

# Valid actions per incident state, mirroring ActionRuleEngine.VALID_TRANSITIONS.
_VALID_TRANSITIONS: dict[str, list[str]] = {
    "new": ["investigate", "assign_engineer", "escalate"],
    "acknowledged": ["investigate", "dispatch", "escalate"],
    "investigating": ["dispatch", "resolve", "escalate", "monitor"],
    "resolved": ["close", "reopen", "monitor"],
    "closed": ["reopen"],
}

_VALID_ESCALATION_LEVELS: set[str] = {e.value for e in EscalationLevel}
_VALID_SERVICE_STATES: set[str] = {s.value for s in ServiceState}
_VALID_IMPACT_LEVELS: set[str] = {i.value for i in ImpactLevel}
_VALID_RECONCILIATION_STATUSES: set[str] = {s.value for s in ReconciliationStatus}

# Customer-count thresholds that should correspond to each impact level.
_IMPACT_CUSTOMER_THRESHOLDS: dict[str, int] = {
    "critical": 1000,
    "major": 100,
    "minor": 10,
    "negligible": 0,
}


class TelcoOpsValidator:
    """Deterministic validator for telco-ops domain outputs.

    Every ``validate_*`` method accepts a plain dict (the LLM / workflow
    output payload) and returns a list of :class:`RuleResult` items
    describing which checks passed and which failed.
    """

    # ------------------------------------------------------------------
    # Escalation decision
    # ------------------------------------------------------------------

    def validate_escalation_decision(
        self, output_payload: dict
    ) -> list[RuleResult]:
        """Validate an escalation decision payload.

        Checks:
        1. ``level`` is a recognised escalation level.
        2. ``owner`` is assigned when ``escalate`` is ``True``.
        3. ``reason`` is present and non-empty.
        """
        results: list[RuleResult] = []
        escalate = output_payload.get("escalate", False)
        level = output_payload.get("level")
        owner = output_payload.get("owner", "")
        reason = output_payload.get("reason", "")

        # Rule 1 -- escalation level validity
        if escalate:
            level_valid = level is not None and level in _VALID_ESCALATION_LEVELS
            results.append(
                RuleResult(
                    rule_name="escalation_level_valid",
                    passed=level_valid,
                    message=(
                        f"Escalation level '{level}' is valid"
                        if level_valid
                        else f"Escalation level '{level}' is not recognised; "
                        f"expected one of {sorted(_VALID_ESCALATION_LEVELS)}"
                    ),
                    severity="error" if not level_valid else "info",
                )
            )
        else:
            # When not escalating, level should be absent or None.
            results.append(
                RuleResult(
                    rule_name="escalation_level_valid",
                    passed=True,
                    message="No escalation requested; level check skipped",
                    severity="info",
                )
            )

        # Rule 2 -- owner assigned when escalating
        if escalate:
            owner_assigned = bool(owner and owner.strip())
            results.append(
                RuleResult(
                    rule_name="escalation_owner_assigned",
                    passed=owner_assigned,
                    message=(
                        f"Escalation owner assigned: '{owner}'"
                        if owner_assigned
                        else "Escalation requested but no owner assigned"
                    ),
                    severity="error" if not owner_assigned else "info",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="escalation_owner_assigned",
                    passed=True,
                    message="No escalation requested; owner check skipped",
                    severity="info",
                )
            )

        # Rule 3 -- reason present
        reason_present = bool(reason and reason.strip())
        results.append(
            RuleResult(
                rule_name="escalation_reason_present",
                passed=reason_present,
                message=(
                    "Escalation reason provided"
                    if reason_present
                    else "Escalation decision is missing a reason"
                ),
                severity="warning" if not reason_present else "info",
            )
        )

        return results

    # ------------------------------------------------------------------
    # Next action
    # ------------------------------------------------------------------

    def validate_next_action(
        self, output_payload: dict
    ) -> list[RuleResult]:
        """Validate a next-action payload.

        Checks:
        1. ``action`` is a valid state transition for the current
           ``incident_state`` (if provided).
        2. ``owner`` is assigned when action is ``dispatch``.
        3. ``evidence_ids`` or ``reason`` provides supporting evidence.
        """
        results: list[RuleResult] = []
        action = output_payload.get("action", "")
        incident_state = output_payload.get("incident_state", "")
        owner = output_payload.get("owner", "")
        reason = output_payload.get("reason", "")
        evidence_ids = output_payload.get("evidence_ids", [])

        # Rule 1 -- valid state transition
        if incident_state:
            valid_actions = _VALID_TRANSITIONS.get(incident_state, [])
            transition_valid = action in valid_actions
            results.append(
                RuleResult(
                    rule_name="action_valid_transition",
                    passed=transition_valid,
                    message=(
                        f"Action '{action}' is valid from state '{incident_state}'"
                        if transition_valid
                        else f"Action '{action}' is not valid from state "
                        f"'{incident_state}'; valid actions: {valid_actions}"
                    ),
                    severity="error" if not transition_valid else "info",
                )
            )
        else:
            # Without incident_state we cannot validate transitions;
            # still flag as a warning.
            results.append(
                RuleResult(
                    rule_name="action_valid_transition",
                    passed=False,
                    message="Cannot validate state transition: 'incident_state' not provided in payload",
                    severity="warning",
                )
            )

        # Rule 2 -- owner assigned for dispatch
        if action == "dispatch":
            owner_assigned = bool(owner and owner.strip())
            results.append(
                RuleResult(
                    rule_name="action_dispatch_owner",
                    passed=owner_assigned,
                    message=(
                        f"Dispatch owner assigned: '{owner}'"
                        if owner_assigned
                        else "Action is 'dispatch' but no owner assigned"
                    ),
                    severity="error" if not owner_assigned else "info",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="action_dispatch_owner",
                    passed=True,
                    message=f"Action '{action}' does not require dispatch owner",
                    severity="info",
                )
            )

        # Rule 3 -- evidence present (reason or evidence_ids)
        has_evidence = bool(
            (reason and reason.strip()) or evidence_ids
        )
        results.append(
            RuleResult(
                rule_name="action_evidence_present",
                passed=has_evidence,
                message=(
                    "Supporting evidence or reason provided"
                    if has_evidence
                    else "No reason or evidence_ids supplied for next action"
                ),
                severity="warning" if not has_evidence else "info",
            )
        )

        return results

    # ------------------------------------------------------------------
    # Incident reconciliation
    # ------------------------------------------------------------------

    def validate_incident_reconciliation(
        self, output_payload: dict
    ) -> list[RuleResult]:
        """Validate an incident reconciliation payload.

        Checks:
        1. ``status`` is a recognised reconciliation status.
        2. Every mismatch entry carries a ``severity`` value.
        3. ``recommendations`` are present when status is ``mismatched``.
        """
        results: list[RuleResult] = []
        status = output_payload.get("status", "")
        mismatches = output_payload.get("mismatches", [])
        recommendations = output_payload.get("recommendations", [])

        # Rule 1 -- status validity
        status_valid = status in _VALID_RECONCILIATION_STATUSES
        results.append(
            RuleResult(
                rule_name="reconciliation_status_valid",
                passed=status_valid,
                message=(
                    f"Reconciliation status '{status}' is valid"
                    if status_valid
                    else f"Reconciliation status '{status}' is not recognised; "
                    f"expected one of {sorted(_VALID_RECONCILIATION_STATUSES)}"
                ),
                severity="error" if not status_valid else "info",
            )
        )

        # Rule 2 -- mismatches carry severity
        if mismatches:
            all_have_severity = all(
                isinstance(m, dict) and bool(m.get("severity", "").strip())
                for m in mismatches
            )
            bad_indices = [
                i
                for i, m in enumerate(mismatches)
                if not (isinstance(m, dict) and bool(m.get("severity", "").strip()))
            ]
            results.append(
                RuleResult(
                    rule_name="reconciliation_mismatch_severity",
                    passed=all_have_severity,
                    message=(
                        "All mismatches have a severity assigned"
                        if all_have_severity
                        else f"Mismatches at indices {bad_indices} are missing severity"
                    ),
                    severity="error" if not all_have_severity else "info",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="reconciliation_mismatch_severity",
                    passed=True,
                    message="No mismatches to validate",
                    severity="info",
                )
            )

        # Rule 3 -- recommendations present when mismatched
        if status == ReconciliationStatus.mismatched.value:
            has_recommendations = bool(recommendations)
            results.append(
                RuleResult(
                    rule_name="reconciliation_recommendations_present",
                    passed=has_recommendations,
                    message=(
                        f"{len(recommendations)} recommendation(s) provided for mismatched status"
                        if has_recommendations
                        else "Status is 'mismatched' but no recommendations provided"
                    ),
                    severity="error" if not has_recommendations else "info",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="reconciliation_recommendations_present",
                    passed=True,
                    message=f"Recommendations check not required for status '{status}'",
                    severity="info",
                )
            )

        return results

    # ------------------------------------------------------------------
    # Service state
    # ------------------------------------------------------------------

    def validate_service_state(
        self, state: dict
    ) -> list[RuleResult]:
        """Validate a service state payload.

        Checks:
        1. ``state`` is a recognised service state.
        2. ``impact_level`` is consistent with ``affected_customers`` count.
        3. ``recovery_eta_minutes`` is present when state is ``outage``.
        """
        results: list[RuleResult] = []
        service_state = state.get("state", "")
        impact_level = state.get("impact_level", "")
        affected_customers = state.get("affected_customers", 0)
        recovery_eta = state.get("recovery_eta_minutes")

        # Rule 1 -- state validity
        state_valid = service_state in _VALID_SERVICE_STATES
        results.append(
            RuleResult(
                rule_name="service_state_valid",
                passed=state_valid,
                message=(
                    f"Service state '{service_state}' is valid"
                    if state_valid
                    else f"Service state '{service_state}' is not recognised; "
                    f"expected one of {sorted(_VALID_SERVICE_STATES)}"
                ),
                severity="error" if not state_valid else "info",
            )
        )

        # Rule 2 -- impact level consistent with customer count
        if impact_level and impact_level in _VALID_IMPACT_LEVELS:
            threshold = _IMPACT_CUSTOMER_THRESHOLDS.get(impact_level, 0)
            # For critical/major, the customer count should meet the threshold.
            # For negligible/minor, the customer count should NOT exceed the
            # next tier's threshold.
            if impact_level == "critical":
                consistent = affected_customers >= _IMPACT_CUSTOMER_THRESHOLDS["critical"]
            elif impact_level == "major":
                consistent = (
                    affected_customers >= _IMPACT_CUSTOMER_THRESHOLDS["major"]
                )
            elif impact_level == "minor":
                consistent = (
                    affected_customers >= _IMPACT_CUSTOMER_THRESHOLDS["minor"]
                    and affected_customers < _IMPACT_CUSTOMER_THRESHOLDS["major"]
                )
            else:  # negligible
                consistent = affected_customers < _IMPACT_CUSTOMER_THRESHOLDS["minor"]

            results.append(
                RuleResult(
                    rule_name="service_impact_customer_consistency",
                    passed=consistent,
                    message=(
                        f"Impact '{impact_level}' is consistent with "
                        f"{affected_customers} affected customer(s)"
                        if consistent
                        else f"Impact '{impact_level}' appears inconsistent with "
                        f"{affected_customers} affected customer(s); "
                        f"expected threshold >= {threshold} for '{impact_level}'"
                    ),
                    severity="warning" if not consistent else "info",
                )
            )
        elif impact_level:
            results.append(
                RuleResult(
                    rule_name="service_impact_customer_consistency",
                    passed=False,
                    message=f"Impact level '{impact_level}' is not recognised; "
                    f"expected one of {sorted(_VALID_IMPACT_LEVELS)}",
                    severity="error",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="service_impact_customer_consistency",
                    passed=False,
                    message="Impact level not provided; cannot validate consistency",
                    severity="warning",
                )
            )

        # Rule 3 -- recovery ETA present for outage
        if service_state == ServiceState.outage.value:
            eta_present = recovery_eta is not None
            results.append(
                RuleResult(
                    rule_name="service_outage_recovery_eta",
                    passed=eta_present,
                    message=(
                        f"Recovery ETA provided: {recovery_eta} minutes"
                        if eta_present
                        else "Service is in outage but no recovery_eta_minutes provided"
                    ),
                    severity="error" if not eta_present else "info",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="service_outage_recovery_eta",
                    passed=True,
                    message=f"Recovery ETA check not required for state '{service_state}'",
                    severity="info",
                )
            )

        return results

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    _DOMAIN_ROUTER: dict[str, str] = {
        "escalation_decision": "validate_escalation_decision",
        "next_action": "validate_next_action",
        "incident_reconciliation": "validate_incident_reconciliation",
        "service_state": "validate_service_state",
    }

    def validate(
        self, domain: str, output_payload: dict
    ) -> list[RuleResult]:
        """Route to the appropriate validator based on *domain*.

        Supported domains:
        - ``escalation_decision``
        - ``next_action``
        - ``incident_reconciliation``
        - ``service_state``

        Raises :class:`ValueError` if *domain* is not recognised.
        """
        method_name = self._DOMAIN_ROUTER.get(domain)
        if method_name is None:
            raise ValueError(
                f"Unknown telco-ops validation domain '{domain}'; "
                f"supported: {sorted(self._DOMAIN_ROUTER)}"
            )
        method = getattr(self, method_name)
        return method(output_payload)
