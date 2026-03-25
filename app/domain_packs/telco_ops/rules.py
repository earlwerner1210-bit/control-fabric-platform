"""Telco Ops business rules – escalation, action, ownership, runbook, reconciliation, dispatch."""

from __future__ import annotations

import uuid
from typing import Any

from app.domain_packs.telco_ops.schemas import (
    EscalationDecision,
    EscalationLevel,
    ImpactLevel,
    IncidentSeverity,
    IncidentState,
    NextAction,
    ParsedIncident,
    ParsedRunbook,
    ReconciliationMismatch,
    ReconciliationResult,
    ReconciliationStatus,
    RunbookReferenceObject,
    RunbookStep,
    ServiceState,
    ServiceStateObject,
)
from app.schemas.validation import RuleResult


# ---------------------------------------------------------------------------
# EscalationRuleEngine
# ---------------------------------------------------------------------------


class EscalationRuleEngine:
    """Determine escalation requirements for incidents."""

    def evaluate(
        self,
        incident: ParsedIncident,
        service_state: ServiceState | None = None,
        sla_breached: bool = False,
        repeat_count: int = 0,
    ) -> EscalationDecision:
        should_escalate = False
        level: EscalationLevel | None = None
        reason = ""

        # Rule 1: Severity-based escalation
        if incident.severity in (IncidentSeverity.p1,):
            should_escalate = True
            level = EscalationLevel.l3
            reason = "P1 incident requires immediate L3 escalation"
        elif incident.severity == IncidentSeverity.p2:
            should_escalate = True
            level = EscalationLevel.l2
            reason = "P2 incident requires L2 escalation"

        # Rule 2: SLA breach escalation
        if sla_breached:
            should_escalate = True
            level = EscalationLevel.management if level == EscalationLevel.l3 else EscalationLevel.l3
            reason = f"SLA breach detected. {reason}"

        # Rule 3: Repeated incident
        if repeat_count >= 3:
            should_escalate = True
            if level is None or level.value < EscalationLevel.l2.value:
                level = EscalationLevel.l2
            reason = f"Repeated incident (count: {repeat_count}). {reason}"

        # Rule 4: Cross-domain impact
        if service_state == ServiceState.outage:
            should_escalate = True
            level = EscalationLevel.l3
            reason = f"Service outage detected. {reason}"

        # Rule 5: Multiple critical services affected
        critical_services = {"core_network", "voice_platform", "billing", "hss", "mme"}
        affected_critical = set(incident.affected_services) & critical_services
        if len(affected_critical) >= 2:
            should_escalate = True
            level = EscalationLevel.management
            reason = f"Multiple critical services affected: {', '.join(affected_critical)}. {reason}"

        # Rule 6: P2 with SLA breach -> management
        if incident.severity == IncidentSeverity.p2 and sla_breached:
            level = EscalationLevel.management
            reason = f"P2 incident with SLA breach requires management escalation. {reason}"

        owner = self._determine_owner(level) if should_escalate else ""

        return EscalationDecision(
            escalate=should_escalate,
            level=level,
            owner=owner,
            reason=reason.strip(),
        )

    def _determine_owner(self, level: EscalationLevel | None) -> str:
        owners = {
            EscalationLevel.l1: "service_desk",
            EscalationLevel.l2: "engineering_team",
            EscalationLevel.l3: "senior_engineering",
            EscalationLevel.management: "service_delivery_manager",
        }
        return owners.get(level, "unassigned") if level else "unassigned"


# ---------------------------------------------------------------------------
# ActionRuleEngine
# ---------------------------------------------------------------------------


class ActionRuleEngine:
    """Determine next best action for an incident."""

    VALID_TRANSITIONS: dict[str, list[str]] = {
        "new": ["investigate", "assign_engineer", "escalate"],
        "acknowledged": ["investigate", "dispatch", "escalate"],
        "investigating": ["dispatch", "resolve", "escalate", "monitor"],
        "resolved": ["close", "reopen", "monitor"],
        "closed": ["reopen"],
    }

    def evaluate(
        self,
        incident_state: IncidentState,
        service_state: ServiceState | None = None,
        has_runbook: bool = False,
        has_assigned_owner: bool = False,
    ) -> NextAction:
        valid_actions = self.VALID_TRANSITIONS.get(incident_state.value, ["investigate"])

        # Determine best action
        if incident_state == IncidentState.new:
            if not has_assigned_owner:
                action = "assign_engineer"
                reason = "Incident not yet assigned"
            else:
                action = "investigate"
                reason = "Begin investigation"
        elif incident_state == IncidentState.investigating:
            if service_state == ServiceState.outage:
                action = "escalate"
                reason = "Service outage requires escalation"
            elif has_runbook:
                action = "dispatch"
                reason = "Runbook available, dispatch for resolution"
            else:
                action = "investigate"
                reason = "Continue investigation"
        elif incident_state == IncidentState.resolved:
            action = "close"
            reason = "Incident resolved, ready for closure"
        else:
            action = valid_actions[0] if valid_actions else "investigate"
            reason = "Default action for current state"

        return NextAction(
            action=action,
            reason=reason,
            priority="high" if service_state == ServiceState.outage else "normal",
        )

    # -- extended validations -----------------------------------------------

    def validate_state_transition(
        self,
        current_state: IncidentState,
        proposed_action: str,
    ) -> bool:
        """Return True if *proposed_action* is valid from *current_state*."""
        valid = self.VALID_TRANSITIONS.get(current_state.value, [])
        return proposed_action in valid

    def check_runbook_completion(
        self,
        runbook: ParsedRunbook,
        executed_steps: list[int],
    ) -> dict:
        """Check whether all runbook steps have been attempted."""
        total = len(runbook.steps)
        completed = len(set(executed_steps))
        pending = [
            s.get("step_number", i + 1)
            for i, s in enumerate(runbook.steps)
            if (i + 1) not in set(executed_steps)
        ]
        return {
            "total_steps": total,
            "completed_steps": completed,
            "pending_step_numbers": pending,
            "all_complete": completed >= total,
            "completion_pct": round(completed / total * 100, 1) if total else 100.0,
        }

    def check_sla_window(
        self,
        severity: IncidentSeverity,
        elapsed_minutes: int,
    ) -> dict:
        """Return SLA status and remaining time."""
        sla_limits: dict[str, int] = {
            "p1": 60,
            "p2": 240,
            "p3": 480,
            "p4": 1440,
        }
        limit = sla_limits.get(severity.value, 1440)
        remaining = max(0, limit - elapsed_minutes)
        pct_used = round(elapsed_minutes / limit * 100, 1) if limit else 100.0
        if remaining == 0:
            status = "breached"
        elif pct_used >= 80:
            status = "warning"
        else:
            status = "within"
        return {
            "sla_limit_minutes": limit,
            "elapsed_minutes": elapsed_minutes,
            "remaining_minutes": remaining,
            "pct_used": pct_used,
            "status": status,
        }

    def recommend_parallel_actions(
        self,
        incident: ParsedIncident,
        service_state: ServiceState | None = None,
    ) -> list[str]:
        """Suggest actions that can run in parallel for the incident."""
        parallel: list[str] = []
        if incident.state == IncidentState.investigating:
            parallel.append("monitor")
            if service_state == ServiceState.degraded:
                parallel.append("contact_customer")
            if len(incident.affected_services) > 1:
                parallel.append("isolate_affected_services")
        if incident.state == IncidentState.acknowledged:
            parallel.append("investigate")
            parallel.append("notify_stakeholders")
        return parallel


# ---------------------------------------------------------------------------
# OwnershipRuleEngine
# ---------------------------------------------------------------------------


class OwnershipRuleEngine:
    """Determine incident ownership based on service and severity."""

    def determine_owner(
        self,
        severity: IncidentSeverity,
        affected_services: list[str],
        escalation_level: EscalationLevel | None = None,
    ) -> str:
        if escalation_level == EscalationLevel.management:
            return "service_delivery_manager"
        if escalation_level == EscalationLevel.l3:
            return "senior_engineering"
        if severity == IncidentSeverity.p1:
            return "on_call_engineer"
        if severity == IncidentSeverity.p2:
            return "engineering_team"
        return "service_desk"


# ---------------------------------------------------------------------------
# RunbookRuleEngine
# ---------------------------------------------------------------------------


class RunbookRuleEngine:
    """Runbook recommendation, validation, and step tracking."""

    def recommend_runbook(
        self,
        incident: ParsedIncident,
        available_runbooks: list[RunbookReferenceObject],
    ) -> RunbookReferenceObject | None:
        """Pick the best runbook for an incident using weighted scoring."""
        if not available_runbooks:
            return None

        best: RunbookReferenceObject | None = None
        best_score = -1.0

        for rb in available_runbooks:
            score = 0.0
            # Service overlap (+3 each)
            shared = set(incident.affected_services) & set(rb.applicable_services)
            score += len(shared) * 3.0
            # Severity match (+5)
            if incident.severity.value in rb.applicable_severity:
                score += 5.0
            # Success rate bonus
            score += rb.success_rate * 2.0
            # Prefer shorter runbooks (less risk)
            if rb.estimated_time_minutes and rb.estimated_time_minutes < 60:
                score += 1.0

            if score > best_score:
                best_score = score
                best = rb

        return best if best_score > 0 else None

    def validate_runbook_applicability(
        self,
        runbook: RunbookReferenceObject,
        incident: ParsedIncident,
    ) -> list[RuleResult]:
        """Validate whether a runbook is appropriate for the incident."""
        results: list[RuleResult] = []

        # Service applicability
        if runbook.applicable_services and incident.affected_services:
            overlap = set(runbook.applicable_services) & set(incident.affected_services)
            results.append(RuleResult(
                rule_name="runbook_service_match",
                passed=bool(overlap),
                message=f"Service overlap: {overlap}" if overlap else "No matching services",
                severity="error" if not overlap else "info",
            ))

        # Severity applicability
        if runbook.applicable_severity:
            sev_match = incident.severity.value in runbook.applicable_severity
            results.append(RuleResult(
                rule_name="runbook_severity_match",
                passed=sev_match,
                message=(
                    f"Severity {incident.severity.value} is applicable"
                    if sev_match
                    else f"Severity {incident.severity.value} not in {runbook.applicable_severity}"
                ),
                severity="warning" if not sev_match else "info",
            ))

        # Freshness check
        if runbook.last_updated:
            results.append(RuleResult(
                rule_name="runbook_freshness",
                passed=True,  # caller can refine with real date comparison
                message=f"Runbook last updated: {runbook.last_updated}",
                severity="info",
            ))

        return results

    def check_runbook_step_completion(
        self,
        runbook: RunbookReferenceObject,
        executed_steps: list[int],
    ) -> dict:
        """Return completion status of runbook steps."""
        total = len(runbook.steps)
        executed_set = set(executed_steps)
        completed = [s for s in runbook.steps if s.step_number in executed_set]
        pending = [s for s in runbook.steps if s.step_number not in executed_set]
        return {
            "total": total,
            "completed": len(completed),
            "pending": len(pending),
            "pending_steps": [s.step_number for s in pending],
            "all_complete": len(pending) == 0,
        }

    def suggest_next_runbook_step(
        self,
        runbook: RunbookReferenceObject,
        completed_steps: list[int],
    ) -> RunbookStep | None:
        """Return the next step to execute, or None if all complete."""
        completed_set = set(completed_steps)
        for step in sorted(runbook.steps, key=lambda s: s.step_number):
            if step.step_number not in completed_set:
                return step
        return None


# ---------------------------------------------------------------------------
# ReconciliationRuleEngine
# ---------------------------------------------------------------------------


class ReconciliationRuleEngine:
    """Reconcile incident state against work orders and service states."""

    # -- state alignment maps -----------------------------------------------

    _INCIDENT_TO_WO_STATE: dict[str, list[str]] = {
        "new": ["open", "new", "pending"],
        "acknowledged": ["open", "assigned", "in_progress"],
        "investigating": ["in_progress", "assigned"],
        "resolved": ["completed", "resolved", "done"],
        "closed": ["completed", "closed", "done"],
    }

    def reconcile_incident_and_work_order(
        self,
        incident_state: dict,
        work_order_state: dict,
    ) -> ReconciliationResult:
        """Compare incident and work-order state dicts for consistency."""
        mismatches: list[ReconciliationMismatch] = []
        recommendations: list[str] = []

        # 1. State alignment
        inc_state = incident_state.get("state", "")
        wo_state = work_order_state.get("state", work_order_state.get("status", ""))
        expected_wo_states = self._INCIDENT_TO_WO_STATE.get(inc_state, [])
        if wo_state and expected_wo_states and wo_state not in expected_wo_states:
            mismatches.append(ReconciliationMismatch(
                field="state",
                incident_value=inc_state,
                work_order_value=wo_state,
                severity="error",
                resolution=f"Expected work-order state in {expected_wo_states} for incident state '{inc_state}'",
            ))
            recommendations.append(f"Align work-order state to match incident state '{inc_state}'")

        # 2. Ownership consistency
        inc_owner = incident_state.get("assigned_to", "")
        wo_owner = work_order_state.get("assigned_to", work_order_state.get("technician", ""))
        if inc_owner and wo_owner and inc_owner != wo_owner:
            mismatches.append(ReconciliationMismatch(
                field="assigned_to",
                incident_value=inc_owner,
                work_order_value=wo_owner,
                severity="warning",
                resolution="Verify whether separate owners are intentional",
            ))

        # 3. Timeline consistency (dispatch should be after acknowledgment)
        inc_ack = incident_state.get("acknowledged_at", "")
        wo_created = work_order_state.get("created_at", "")
        if inc_ack and wo_created and wo_created < inc_ack:
            mismatches.append(ReconciliationMismatch(
                field="timeline",
                incident_value=f"acknowledged_at={inc_ack}",
                work_order_value=f"created_at={wo_created}",
                severity="warning",
                resolution="Work order created before incident acknowledgment — verify sequence",
            ))

        # 4. Resolution alignment
        inc_resolution = incident_state.get("root_cause", "")
        wo_resolution = work_order_state.get("work_performed", "")
        if inc_state == "resolved" and wo_state in ("completed", "done"):
            if inc_resolution and wo_resolution and inc_resolution.lower() != wo_resolution.lower():
                mismatches.append(ReconciliationMismatch(
                    field="resolution",
                    incident_value=inc_resolution,
                    work_order_value=wo_resolution,
                    severity="info",
                    resolution="Review whether root cause and work performed are consistent",
                ))

        # Determine overall status
        if not mismatches:
            status = ReconciliationStatus.aligned
            confidence = 1.0
        elif all(m.severity in ("info",) for m in mismatches):
            status = ReconciliationStatus.partial
            confidence = 0.8
        elif any(m.severity == "error" for m in mismatches):
            status = ReconciliationStatus.mismatched
            confidence = 0.4
        else:
            status = ReconciliationStatus.partial
            confidence = 0.6

        return ReconciliationResult(
            status=status,
            mismatches=mismatches,
            recommendations=recommendations,
            confidence=confidence,
        )

    def reconcile_incident_and_service_state(
        self,
        incident: ParsedIncident,
        service_state: ServiceStateObject,
    ) -> ReconciliationResult:
        """Check consistency between incident and service state."""
        mismatches: list[ReconciliationMismatch] = []
        recommendations: list[str] = []

        # 1. Severity vs impact alignment
        severity_impact_map: dict[str, list[str]] = {
            "p1": ["critical", "major"],
            "p2": ["major", "critical"],
            "p3": ["minor", "major"],
            "p4": ["negligible", "minor"],
        }
        expected_impacts = severity_impact_map.get(incident.severity.value, [])
        if expected_impacts and service_state.impact_level.value not in expected_impacts:
            mismatches.append(ReconciliationMismatch(
                field="impact_level",
                incident_value=f"severity={incident.severity.value}",
                work_order_value=f"impact={service_state.impact_level.value}",
                severity="warning",
                resolution=f"Incident severity {incident.severity.value} typically maps to impact {expected_impacts}",
            ))
            recommendations.append("Review severity/impact alignment")

        # 2. Affected service match
        if service_state.service_name and incident.affected_services:
            if service_state.service_name not in incident.affected_services:
                mismatches.append(ReconciliationMismatch(
                    field="affected_services",
                    incident_value=str(incident.affected_services),
                    work_order_value=service_state.service_name,
                    severity="error",
                    resolution="Service state refers to a service not listed in the incident",
                ))

        # 3. Resolution state consistency
        if incident.state == IncidentState.resolved and service_state.state == ServiceState.outage:
            mismatches.append(ReconciliationMismatch(
                field="resolution_state",
                incident_value="resolved",
                work_order_value="outage",
                severity="critical",
                resolution="Incident marked resolved but service still in outage — verify resolution",
            ))
            recommendations.append("Re-open incident or confirm service has recovered")

        if incident.state == IncidentState.closed and service_state.state in (ServiceState.outage, ServiceState.degraded):
            mismatches.append(ReconciliationMismatch(
                field="resolution_state",
                incident_value="closed",
                work_order_value=service_state.state.value,
                severity="critical",
                resolution="Incident closed but service not fully restored",
            ))
            recommendations.append("Re-open incident — service still impacted")

        # Overall status
        if not mismatches:
            status = ReconciliationStatus.aligned
            confidence = 1.0
        elif any(m.severity == "critical" for m in mismatches):
            status = ReconciliationStatus.mismatched
            confidence = 0.2
        elif any(m.severity == "error" for m in mismatches):
            status = ReconciliationStatus.mismatched
            confidence = 0.4
        else:
            status = ReconciliationStatus.partial
            confidence = 0.7

        return ReconciliationResult(
            status=status,
            mismatches=mismatches,
            recommendations=recommendations,
            confidence=confidence,
        )


# ---------------------------------------------------------------------------
# DispatchNeedEngine
# ---------------------------------------------------------------------------


class DispatchNeedEngine:
    """Determine whether an on-site dispatch is required."""

    _HARDWARE_KEYWORDS = {
        "hardware", "disk", "power", "psu", "fan", "chassis", "nic",
        "card", "module", "physical", "cable", "fiber", "antenna",
    }

    def determine_dispatch_need(
        self,
        incident: ParsedIncident,
        service_state: ServiceStateObject | None = None,
        has_remote_resolution: bool = False,
    ) -> dict:
        """Evaluate whether a field dispatch is needed."""
        reasons: list[str] = []

        # 1. Severity requires on-site?
        severity_requires = incident.severity in (IncidentSeverity.p1,) and (
            service_state is not None and service_state.state == ServiceState.outage
        )
        if severity_requires:
            reasons.append("P1 outage typically requires on-site presence")

        # 2. Hardware failure detected?
        text = f"{incident.title} {incident.description}".lower()
        hardware_failure = any(kw in text for kw in self._HARDWARE_KEYWORDS)
        if hardware_failure:
            reasons.append("Hardware-related keywords detected in incident")

        # 3. Remote resolution exhausted?
        remote_exhausted = has_remote_resolution is False and incident.state == IncidentState.investigating
        # If explicitly told remote was attempted but didn't work
        if "remote" in text and ("failed" in text or "unsuccessful" in text):
            remote_exhausted = True
            reasons.append("Remote resolution attempt was unsuccessful")

        # 4. Customer requested on-site?
        customer_requested = "onsite" in text or "on-site" in text or "customer requested" in text.lower()
        if customer_requested:
            reasons.append("Customer has requested on-site support")

        # 5. SLA requires physical presence?
        sla_requires = False
        if "sla" in " ".join(incident.tags).lower() and incident.severity in (IncidentSeverity.p1, IncidentSeverity.p2):
            sla_requires = True
            reasons.append("SLA terms may require physical presence for this severity")

        dispatch_needed = severity_requires or hardware_failure or remote_exhausted or customer_requested or sla_requires

        return {
            "dispatch_needed": dispatch_needed,
            "severity_requires_onsite": severity_requires,
            "hardware_failure_detected": hardware_failure,
            "remote_resolution_exhausted": remote_exhausted,
            "customer_requested_onsite": customer_requested,
            "sla_requires_physical_presence": sla_requires,
            "reasons": reasons,
        }
