"""Telco Ops deterministic validators for LLM and workflow outputs."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain_packs.telco_ops.schemas import (
    EscalationDecision,
    EscalationLevel,
    ImpactLevel,
    IncidentState,
    NextAction,
    ParsedIncident,
    ReconciliationResult,
    ReconciliationStatus,
    RunbookReferenceObject,
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

# Known owners for escalation validation
_KNOWN_OWNERS: set[str] = {
    "service_desk", "engineering_team", "senior_engineering",
    "service_delivery_manager", "on_call_engineer", "noc",
}

# Minimum escalation levels per severity
_SEVERITY_MIN_LEVELS: dict[str, str] = {"p1": "l3", "p2": "l2"}
_LEVEL_ORDER: dict[str, int] = {"l1": 1, "l2": 2, "l3": 3, "management": 4}


class TelcoOpsValidator:
    """Deterministic validator for telco-ops domain outputs.

    Every ``validate_*`` method accepts either typed domain objects or plain
    dicts (for LLM / workflow output payloads) and returns a list of
    :class:`RuleResult` items describing which checks passed and which failed.
    """

    # ==================================================================
    # Dict-based validators (for raw LLM / workflow payloads)
    # ==================================================================

    # ------------------------------------------------------------------
    # Escalation decision (dict)
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
    # Next action (dict)
    # ------------------------------------------------------------------

    def validate_next_action(
        self,
        action_or_payload: NextAction | dict,
        incident: ParsedIncident | None = None,
    ) -> list[RuleResult]:
        """Validate a next-action payload or typed object.

        Accepts either a :class:`NextAction` + :class:`ParsedIncident` pair
        or a plain dict payload (backward-compatible).

        Checks:
        1. ``action`` is a valid state transition for the current incident state.
        2. Owner is present when action requires one.
        3. Supporting evidence or reason is provided.
        4. SLA breach tag requires escalation action.
        """
        # Normalise input
        if isinstance(action_or_payload, dict) and incident is None:
            return self._validate_next_action_dict(action_or_payload)
        if isinstance(action_or_payload, NextAction) and incident is not None:
            return self._validate_next_action_typed(action_or_payload, incident)
        # Fallback for dict + incident
        if isinstance(action_or_payload, dict):
            return self._validate_next_action_dict(action_or_payload)
        raise TypeError("Expected NextAction with incident, or dict payload")

    def _validate_next_action_dict(self, output_payload: dict) -> list[RuleResult]:
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

    def _validate_next_action_typed(
        self,
        action: NextAction,
        incident: ParsedIncident,
    ) -> list[RuleResult]:
        results: list[RuleResult] = []

        # 1. Invalid action for current state
        valid = set(_VALID_TRANSITIONS.get(incident.state.value, []))
        action_valid = action.action in valid
        results.append(RuleResult(
            rule_name="invalid_action_for_state",
            passed=action_valid,
            message=(
                f"Action '{action.action}' is valid for state '{incident.state.value}'"
                if action_valid
                else f"Action '{action.action}' is not valid for state '{incident.state.value}'. Valid: {valid}"
            ),
            severity="error" if not action_valid else "info",
        ))

        # 2. Missing owner on action
        needs_owner = action.action in {"dispatch", "assign_engineer", "escalate", "resolve"}
        has_owner = bool(action.owner)
        results.append(RuleResult(
            rule_name="missing_owner_on_action",
            passed=not needs_owner or has_owner,
            message=(
                "Owner assigned" if has_owner else f"Action '{action.action}' requires an owner but none is set"
            ),
            severity="warning" if needs_owner and not has_owner else "info",
        ))

        # 3. Action without evidence
        has_evidence = bool(action.evidence_ids)
        results.append(RuleResult(
            rule_name="action_without_evidence",
            passed=has_evidence,
            message="Evidence IDs provided" if has_evidence else "No evidence IDs attached to action",
            severity="warning" if not has_evidence else "info",
        ))

        # 4. SLA breach without escalation
        sla_tags = {"sla_breach", "sla-breach", "sla_warning"}
        has_sla_breach = bool(set(incident.tags) & sla_tags)
        is_escalation = action.action == "escalate"
        sla_ok = not has_sla_breach or is_escalation
        results.append(RuleResult(
            rule_name="sla_breach_without_escalation",
            passed=sla_ok,
            message=(
                "No SLA breach or escalation is the proposed action"
                if sla_ok
                else "SLA breach detected but action is not escalation"
            ),
            severity="error" if not sla_ok else "info",
        ))

        return results

    # ------------------------------------------------------------------
    # Escalation validation (typed)
    # ------------------------------------------------------------------

    def validate_escalation(
        self,
        decision: EscalationDecision,
        incident: ParsedIncident,
    ) -> list[RuleResult]:
        """Validate a typed escalation decision against an incident."""
        results: list[RuleResult] = []

        # 1. Unsupported escalation owner
        owner_known = decision.owner in _KNOWN_OWNERS or not decision.escalate
        results.append(RuleResult(
            rule_name="unsupported_escalation_owner",
            passed=owner_known,
            message=(
                f"Owner '{decision.owner}' is recognised"
                if owner_known
                else f"Owner '{decision.owner}' is not in the known owner list"
            ),
            severity="warning" if not owner_known else "info",
        ))

        # 2. Escalation without reason
        has_reason = bool(decision.reason.strip()) if decision.escalate else True
        results.append(RuleResult(
            rule_name="escalation_without_reason",
            passed=has_reason,
            message="Escalation reason provided" if has_reason else "Escalation requested but no reason given",
            severity="error" if not has_reason else "info",
        ))

        # 3. Wrong level for severity
        level_ok = True
        if decision.escalate and decision.level:
            min_level = _SEVERITY_MIN_LEVELS.get(incident.severity.value)
            if min_level:
                if _LEVEL_ORDER.get(decision.level.value, 0) < _LEVEL_ORDER.get(min_level, 0):
                    level_ok = False
        results.append(RuleResult(
            rule_name="wrong_level_for_severity",
            passed=level_ok,
            message=(
                "Escalation level is appropriate for severity"
                if level_ok
                else (
                    f"Severity {incident.severity.value} requires at least "
                    f"{_SEVERITY_MIN_LEVELS.get(incident.severity.value)} but got "
                    f"{decision.level.value if decision.level else 'none'}"
                )
            ),
            severity="error" if not level_ok else "info",
        ))

        # 4. Escalation on closed incident
        on_closed = decision.escalate and incident.state == IncidentState.closed
        results.append(RuleResult(
            rule_name="escalation_on_closed_incident",
            passed=not on_closed,
            message=(
                "Incident is not closed"
                if not on_closed
                else "Cannot escalate a closed incident — reopen first"
            ),
            severity="error" if on_closed else "info",
        ))

        return results

    # ------------------------------------------------------------------
    # Reconciliation validation (typed)
    # ------------------------------------------------------------------

    def validate_reconciliation(
        self,
        result: ReconciliationResult,
    ) -> list[RuleResult]:
        """Validate a typed reconciliation result."""
        results: list[RuleResult] = []

        # 1. Mismatches without recommendations
        has_mismatches = bool(result.mismatches)
        has_recs = bool(result.recommendations)
        mm_rec_ok = not has_mismatches or has_recs
        results.append(RuleResult(
            rule_name="mismatches_without_recommendations",
            passed=mm_rec_ok,
            message=(
                "Recommendations provided for mismatches"
                if mm_rec_ok
                else "Mismatches detected but no recommendations given"
            ),
            severity="warning" if not mm_rec_ok else "info",
        ))

        # 2. Aligned but contradictions present
        aligned_with_mismatches = (
            result.status == ReconciliationStatus.aligned and has_mismatches
        )
        results.append(RuleResult(
            rule_name="aligned_but_contradictions_present",
            passed=not aligned_with_mismatches,
            message=(
                "Status consistent with mismatch list"
                if not aligned_with_mismatches
                else "Status is 'aligned' but mismatches are present"
            ),
            severity="error" if aligned_with_mismatches else "info",
        ))

        # 3. Missing evidence for mismatch
        evidence_ok = True
        for mm in result.mismatches:
            if not mm.incident_value and not mm.work_order_value:
                evidence_ok = False
                break
        results.append(RuleResult(
            rule_name="missing_evidence_for_mismatch",
            passed=evidence_ok,
            message=(
                "All mismatches have at least one evidence value"
                if evidence_ok
                else "One or more mismatches have no incident or work-order value"
            ),
            severity="warning" if not evidence_ok else "info",
        ))

        return results

    # ------------------------------------------------------------------
    # Incident reconciliation (dict — legacy)
    # ------------------------------------------------------------------

    def validate_incident_reconciliation(
        self, output_payload: dict
    ) -> list[RuleResult]:
        """Validate an incident reconciliation payload (dict).

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
    # Service state (dict)
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
    # Runbook recommendation validation (typed)
    # ------------------------------------------------------------------

    def validate_runbook_recommendation(
        self,
        runbook: RunbookReferenceObject,
        incident: ParsedIncident,
    ) -> list[RuleResult]:
        """Validate whether a runbook recommendation is appropriate."""
        results: list[RuleResult] = []

        # 1. Runbook not applicable to service
        if runbook.applicable_services and incident.affected_services:
            overlap = set(runbook.applicable_services) & set(incident.affected_services)
            svc_ok = bool(overlap)
        else:
            svc_ok = True
        results.append(RuleResult(
            rule_name="runbook_not_applicable_to_service",
            passed=svc_ok,
            message=(
                "Runbook services match incident"
                if svc_ok
                else (
                    f"Runbook services {runbook.applicable_services} "
                    f"do not overlap with incident services {incident.affected_services}"
                )
            ),
            severity="error" if not svc_ok else "info",
        ))

        # 2. Runbook severity mismatch
        if runbook.applicable_severity:
            sev_ok = incident.severity.value in runbook.applicable_severity
        else:
            sev_ok = True
        results.append(RuleResult(
            rule_name="runbook_severity_mismatch",
            passed=sev_ok,
            message=(
                "Severity matches runbook applicability"
                if sev_ok
                else (
                    f"Incident severity {incident.severity.value} "
                    f"not in runbook's applicable severity {runbook.applicable_severity}"
                )
            ),
            severity="warning" if not sev_ok else "info",
        ))

        # 3. Outdated runbook (> 1 year)
        outdated = False
        if runbook.last_updated:
            try:
                updated_dt = datetime.fromisoformat(
                    runbook.last_updated.replace("Z", "+00:00")
                )
                age_days = (datetime.now(timezone.utc) - updated_dt).days
                outdated = age_days > 365
            except (ValueError, TypeError):
                pass
        results.append(RuleResult(
            rule_name="outdated_runbook",
            passed=not outdated,
            message=(
                "Runbook is up to date"
                if not outdated
                else f"Runbook last updated on {runbook.last_updated} — over 1 year old"
            ),
            severity="warning" if outdated else "info",
        ))

        return results

    # ------------------------------------------------------------------
    # Dispatch recommendation validation (typed)
    # ------------------------------------------------------------------

    def validate_dispatch_recommendation(
        self,
        dispatch_needed: bool,
        incident: ParsedIncident,
        context: dict,
    ) -> list[RuleResult]:
        """Validate whether a dispatch recommendation is sound."""
        results: list[RuleResult] = []

        # 1. Dispatch without work order
        has_work_order = context.get("has_work_order", False)
        wo_ok = not dispatch_needed or has_work_order
        results.append(RuleResult(
            rule_name="dispatch_without_work_order",
            passed=wo_ok,
            message=(
                "Work order exists or dispatch not needed"
                if wo_ok
                else "Dispatch recommended but no work order has been created"
            ),
            severity="error" if not wo_ok else "info",
        ))

        # 2. Remote not attempted first
        remote_attempted = context.get("remote_attempted", False)
        remote_ok = not dispatch_needed or remote_attempted
        results.append(RuleResult(
            rule_name="remote_not_attempted_first",
            passed=remote_ok,
            message=(
                "Remote resolution was attempted or dispatch not needed"
                if remote_ok
                else "Dispatch recommended but remote resolution has not been attempted"
            ),
            severity="warning" if not remote_ok else "info",
        ))

        # 3. Dispatch on resolved incident
        on_resolved = dispatch_needed and incident.state in (
            IncidentState.resolved, IncidentState.closed,
        )
        results.append(RuleResult(
            rule_name="dispatch_on_resolved_incident",
            passed=not on_resolved,
            message=(
                "Incident is not resolved/closed"
                if not on_resolved
                else "Dispatch recommended on a resolved/closed incident"
            ),
            severity="error" if on_resolved else "info",
        ))

        return results

    # ------------------------------------------------------------------
    # Main entry point (dict router)
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
