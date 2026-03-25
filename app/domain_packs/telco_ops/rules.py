"""Telco Ops business rules – escalation, action, ownership, runbook, reconciliation, dispatch."""

from __future__ import annotations

import uuid
from typing import Any

from app.domain_packs.telco_ops.schemas import (
    ClosureGate,
    ClosurePrerequisite,
    EscalationDecision,
    EscalationLevel,
    ImpactLevel,
    IncidentSeverity,
    IncidentState,
    MajorIncidentRecord,
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
    VodafoneSLADefinition,
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


# ---------------------------------------------------------------------------
# Vodafone UK managed-services engines
# ---------------------------------------------------------------------------

_VODAFONE_CRITICAL_DOMAINS = {"core_network", "billing_mediation"}
_VODAFONE_WARNING_THRESHOLD = 0.80


class VodafoneSLAEngine:
    """Evaluate SLA status against Vodafone managed-services definitions."""

    def check_sla_status(
        self,
        incident: ParsedIncident,
        sla_definitions: list[VodafoneSLADefinition],
        current_time_minutes: int,
    ) -> dict:
        """Return SLA compliance status for *incident*.

        Returns
        -------
        dict with keys:
            response_sla, resolution_sla  – "within" | "warning" | "breached"
            update_overdue                – bool
            minutes_to_breach             – int (resolution)
            bridge_call_required          – bool
        """
        # Find matching SLA definition
        sla: VodafoneSLADefinition | None = None
        for defn in sla_definitions:
            if defn.severity == incident.severity:
                sla = defn
                break

        if sla is None:
            return {
                "response_sla": "within",
                "resolution_sla": "within",
                "update_overdue": False,
                "minutes_to_breach": 0,
                "bridge_call_required": False,
            }

        # Response SLA
        response_status = self._threshold_status(
            current_time_minutes, sla.response_time_minutes
        )

        # Resolution SLA
        resolution_status = self._threshold_status(
            current_time_minutes, sla.resolution_time_minutes
        )

        minutes_to_breach = max(0, sla.resolution_time_minutes - current_time_minutes)

        # Update overdue check
        update_overdue = False
        if sla.update_frequency_minutes > 0 and current_time_minutes > 0:
            update_overdue = (current_time_minutes % sla.update_frequency_minutes) == 0 or current_time_minutes > sla.update_frequency_minutes

        return {
            "response_sla": response_status,
            "resolution_sla": resolution_status,
            "update_overdue": update_overdue,
            "minutes_to_breach": minutes_to_breach,
            "bridge_call_required": sla.bridge_call_required,
        }

    def calculate_service_credit(
        self,
        sla_breaches: list[dict],
        credit_rules: list,
    ) -> dict:
        """Calculate total service credit based on breach count and severity.

        Each entry in *sla_breaches* should contain:
            severity (str), breach_type (str: "response" | "resolution"),
            breach_minutes (int).

        *credit_rules* is a list of dicts with:
            severity (str), per_breach_pct (float), max_pct (float).

        Returns dict with total_credit_pct, breach_count, breakdown.
        """
        # Build rule lookup
        rule_map: dict[str, dict] = {}
        for rule in credit_rules:
            rule_map[rule.get("severity", "")] = rule

        breakdown: list[dict] = []
        total_credit_pct = 0.0

        for breach in sla_breaches:
            sev = breach.get("severity", "p3")
            rule = rule_map.get(sev, {"per_breach_pct": 1.0, "max_pct": 10.0})
            credit = rule.get("per_breach_pct", 1.0)
            breakdown.append({
                "severity": sev,
                "breach_type": breach.get("breach_type", "resolution"),
                "breach_minutes": breach.get("breach_minutes", 0),
                "credit_pct": credit,
            })
            total_credit_pct += credit

        # Apply max cap from highest-severity rule
        max_cap = max((r.get("max_pct", 100.0) for r in credit_rules), default=100.0)
        total_credit_pct = min(total_credit_pct, max_cap)

        return {
            "total_credit_pct": round(total_credit_pct, 2),
            "breach_count": len(sla_breaches),
            "breakdown": breakdown,
        }

    @staticmethod
    def _threshold_status(elapsed: int, limit: int) -> str:
        if elapsed >= limit:
            return "breached"
        if elapsed >= limit * _VODAFONE_WARNING_THRESHOLD:
            return "warning"
        return "within"


class VodafoneEscalationEngine:
    """Vodafone-specific escalation rules for managed services."""

    _LEVEL_ORDER = {"l1": 1, "l2": 2, "l3": 3, "management": 4}

    def evaluate(
        self,
        incident: ParsedIncident,
        sla_status: dict,
        service_domain: str,
        repeat_count: int = 0,
    ) -> EscalationDecision:
        """Determine escalation per Vodafone managed-services rules.

        Rules applied in priority order:
        1. P1 -> L3 + bridge call + MIM process
        2. P2 with outage -> L3 + bridge call
        3. P2 without outage -> L2
        4. P3 -> L1 (escalate to L2 if SLA at warning)
        5. Core network or billing domain -> auto-elevate by 1 level
        6. SLA breached -> escalate to management
        7. Repeated incident (3+ in 30 days) -> L3
        """
        should_escalate = False
        level: EscalationLevel | None = None
        reasons: list[str] = []

        is_outage = any(
            s in ("outage",)
            for s in [t.lower() for t in incident.tags]
        ) or sla_status.get("bridge_call_required", False)

        # Rule 1: P1 -> L3 + bridge + MIM
        if incident.severity == IncidentSeverity.p1:
            should_escalate = True
            level = EscalationLevel.l3
            reasons.append("P1 incident: L3 escalation with bridge call and MIM process")

        # Rule 2: P2 with outage -> L3 + bridge
        elif incident.severity == IncidentSeverity.p2 and is_outage:
            should_escalate = True
            level = EscalationLevel.l3
            reasons.append("P2 incident with outage: L3 escalation with bridge call")

        # Rule 3: P2 without outage -> L2
        elif incident.severity == IncidentSeverity.p2:
            should_escalate = True
            level = EscalationLevel.l2
            reasons.append("P2 incident without outage: L2 escalation")

        # Rule 4: P3 -> L1, escalate to L2 if SLA at warning
        elif incident.severity == IncidentSeverity.p3:
            sla_res = sla_status.get("resolution_sla", "within")
            if sla_res == "warning":
                should_escalate = True
                level = EscalationLevel.l2
                reasons.append("P3 incident with SLA at warning: escalated to L2")
            else:
                level = EscalationLevel.l1
                reasons.append("P3 incident: L1 handling")

        # Rule 5: Critical domain -> elevate by 1 level
        if service_domain in _VODAFONE_CRITICAL_DOMAINS:
            if level is not None:
                current_order = self._LEVEL_ORDER.get(level.value, 1)
                for lev, order in sorted(self._LEVEL_ORDER.items(), key=lambda x: x[1]):
                    if order == current_order + 1:
                        level = EscalationLevel(lev)
                        should_escalate = True
                        reasons.append(
                            f"Critical domain '{service_domain}': escalation elevated by 1 level to {level.value}"
                        )
                        break

        # Rule 6: SLA breached -> management
        if sla_status.get("resolution_sla") == "breached":
            should_escalate = True
            level = EscalationLevel.management
            reasons.append("SLA breached: management escalation required")

        # Rule 7: Repeated incident (3+ in 30 days) -> L3
        if repeat_count >= 3:
            should_escalate = True
            if level is None or self._LEVEL_ORDER.get(level.value, 0) < self._LEVEL_ORDER.get("l3", 3):
                level = EscalationLevel.l3
            reasons.append(f"Repeated incident ({repeat_count} occurrences in 30 days): L3 escalation")

        owner = self._determine_owner(level) if should_escalate else ""

        return EscalationDecision(
            escalate=should_escalate,
            level=level,
            owner=owner,
            reason="; ".join(reasons),
        )

    @staticmethod
    def _determine_owner(level: EscalationLevel | None) -> str:
        owners = {
            EscalationLevel.l1: "vodafone_service_desk",
            EscalationLevel.l2: "vodafone_engineering_team",
            EscalationLevel.l3: "vodafone_senior_engineering",
            EscalationLevel.management: "vodafone_service_delivery_manager",
        }
        return owners.get(level, "unassigned") if level else "unassigned"


class VodafoneClosureEngine:
    """Validate incident closure against Vodafone managed-services prerequisites."""

    def validate_closure(
        self,
        incident: ParsedIncident,
        closure_gates: list[ClosureGate],
        major_incident: MajorIncidentRecord | None = None,
    ) -> list[RuleResult]:
        """Evaluate whether the incident may be closed.

        Rules:
        1. Service must be restored
        2. Customer must be notified
        3. P1/P2: RCA must be submitted or at least planned
        4. P1/P2: Problem record must exist
        5. Major incident: bridge call must have occurred, customer comms sent
        6. All mandatory closure gates must be satisfied
        """
        results: list[RuleResult] = []

        # Build gate lookup
        gate_map: dict[str, ClosureGate] = {g.prerequisite.value: g for g in closure_gates}

        # Rule 1: Service must be restored
        service_restored_gate = gate_map.get(ClosurePrerequisite.service_restored.value)
        restored = service_restored_gate is not None and service_restored_gate.satisfied
        results.append(RuleResult(
            rule_name="vodafone_closure_service_restored",
            passed=restored,
            message="Service has been restored" if restored else "Service has not been confirmed as restored",
            severity="error" if not restored else "info",
        ))

        # Rule 2: Customer must be notified
        customer_notified_gate = gate_map.get(ClosurePrerequisite.customer_notified.value)
        notified = customer_notified_gate is not None and customer_notified_gate.satisfied
        results.append(RuleResult(
            rule_name="vodafone_closure_customer_notified",
            passed=notified,
            message="Customer has been notified" if notified else "Customer has not been notified of resolution",
            severity="error" if not notified else "info",
        ))

        # Rule 3: P1/P2 -> RCA submitted or planned
        if incident.severity in (IncidentSeverity.p1, IncidentSeverity.p2):
            rca_gate = gate_map.get(ClosurePrerequisite.rca_submitted.value)
            rca_ok = rca_gate is not None and rca_gate.satisfied
            # Also accept if major_incident shows RCA in progress or submitted
            if not rca_ok and major_incident:
                rca_ok = major_incident.rca_status in ("in_progress", "submitted", "accepted")
            results.append(RuleResult(
                rule_name="vodafone_closure_rca_required",
                passed=rca_ok,
                message=(
                    "RCA submitted or in progress"
                    if rca_ok
                    else f"RCA required for {incident.severity.value} incident but not submitted"
                ),
                severity="error" if not rca_ok else "info",
            ))

        # Rule 4: P1/P2 -> Problem record must exist
        if incident.severity in (IncidentSeverity.p1, IncidentSeverity.p2):
            problem_gate = gate_map.get(ClosurePrerequisite.problem_record_created.value)
            problem_ok = problem_gate is not None and problem_gate.satisfied
            if not problem_ok and major_incident:
                problem_ok = bool(major_incident.problem_record_id)
            results.append(RuleResult(
                rule_name="vodafone_closure_problem_record",
                passed=problem_ok,
                message=(
                    "Problem record exists"
                    if problem_ok
                    else f"Problem record required for {incident.severity.value} incident but not created"
                ),
                severity="error" if not problem_ok else "info",
            ))

        # Rule 5: Major incident -> bridge call + customer comms
        if major_incident is not None:
            bridge_ok = bool(major_incident.bridge_call_id)
            results.append(RuleResult(
                rule_name="vodafone_closure_bridge_call",
                passed=bridge_ok,
                message=(
                    "Bridge call was conducted"
                    if bridge_ok
                    else "Major incident closure requires a bridge call record"
                ),
                severity="error" if not bridge_ok else "info",
            ))

            comms_ok = bool(major_incident.customer_comms_sent)
            results.append(RuleResult(
                rule_name="vodafone_closure_customer_comms",
                passed=comms_ok,
                message=(
                    f"{len(major_incident.customer_comms_sent)} customer communication(s) sent"
                    if comms_ok
                    else "Major incident closure requires at least one customer communication"
                ),
                severity="error" if not comms_ok else "info",
            ))

        # Rule 6: All mandatory closure gates must be satisfied
        unsatisfied_mandatory = [
            g for g in closure_gates if g.mandatory and not g.satisfied
        ]
        all_gates_ok = len(unsatisfied_mandatory) == 0
        results.append(RuleResult(
            rule_name="vodafone_closure_all_mandatory_gates",
            passed=all_gates_ok,
            message=(
                "All mandatory closure gates satisfied"
                if all_gates_ok
                else (
                    f"{len(unsatisfied_mandatory)} mandatory gate(s) unsatisfied: "
                    + ", ".join(g.prerequisite.value for g in unsatisfied_mandatory)
                )
            ),
            severity="error" if not all_gates_ok else "info",
        ))

        return results


class VodafoneDispatchEngine:
    """Vodafone-specific dispatch decision rules."""

    _HARDWARE_CATEGORIES = {"hardware_failure"}
    _POWER_CATEGORIES = {"power_failure"}
    _FIBRE_CATEGORIES = {"fibre_cut"}
    _SECURITY_CATEGORIES = {"security_incident"}
    _SOFTWARE_CATEGORIES = {"software_bug", "config_error"}

    def should_dispatch(
        self,
        incident: ParsedIncident,
        remote_remediation_attempted: bool,
        has_runbook: bool,
        service_domain: str,
        incident_category: str = "",
    ) -> NextAction:
        """Determine whether a field dispatch is required.

        Rules:
        1. Dispatch only valid when remote remediation exhausted (or N/A for hardware)
        2. Hardware failures -> dispatch immediately
        3. Power failures -> dispatch + vendor coordination
        4. Fibre cut -> dispatch + NRSWA coordination
        5. Software/config -> remote first, dispatch only if remote fails
        6. Security -> isolate first, then dispatch if physical access needed
        """
        text = f"{incident.title} {incident.description}".lower()
        category = incident_category or self._infer_category(text)

        # Rule 2: Hardware failures -> immediate dispatch
        if category in self._HARDWARE_CATEGORIES or "hardware" in text:
            return NextAction(
                action="dispatch",
                owner="vodafone_field_engineering",
                reason="Hardware failure detected: immediate field dispatch required",
                priority="critical" if incident.severity == IncidentSeverity.p1 else "high",
            )

        # Rule 3: Power failures -> dispatch + vendor coordination
        if category in self._POWER_CATEGORIES or "power" in text:
            return NextAction(
                action="dispatch",
                owner="vodafone_field_engineering",
                reason="Power failure: field dispatch with vendor coordination required",
                priority="critical" if incident.severity == IncidentSeverity.p1 else "high",
            )

        # Rule 4: Fibre cut -> dispatch + NRSWA coordination
        if category in self._FIBRE_CATEGORIES or "fibre cut" in text or "fiber cut" in text:
            return NextAction(
                action="dispatch",
                owner="vodafone_field_engineering",
                reason="Fibre cut: field dispatch with NRSWA permit coordination required",
                priority="critical" if incident.severity == IncidentSeverity.p1 else "high",
            )

        # Rule 6: Security -> isolate first
        if category in self._SECURITY_CATEGORIES or "security" in text:
            if not remote_remediation_attempted:
                return NextAction(
                    action="isolate",
                    owner="vodafone_security_team",
                    reason="Security incident: isolate affected systems before dispatch",
                    priority="critical",
                )
            return NextAction(
                action="dispatch",
                owner="vodafone_field_engineering",
                reason="Security incident: physical access required after isolation",
                priority="high",
            )

        # Rule 5: Software/config -> remote first
        if category in self._SOFTWARE_CATEGORIES or any(
            kw in text for kw in ("software", "config", "bug", "patch")
        ):
            if not remote_remediation_attempted:
                return NextAction(
                    action="remote_remediation",
                    owner="vodafone_engineering_team",
                    reason="Software/config issue: attempt remote remediation before dispatch",
                    priority="high" if incident.severity in (IncidentSeverity.p1, IncidentSeverity.p2) else "normal",
                )
            return NextAction(
                action="dispatch",
                owner="vodafone_field_engineering",
                reason="Remote remediation unsuccessful: field dispatch required",
                priority="high",
            )

        # Rule 1: Generic — dispatch only if remote exhausted
        if remote_remediation_attempted:
            return NextAction(
                action="dispatch",
                owner="vodafone_field_engineering",
                reason="Remote remediation exhausted: field dispatch required",
                priority="high" if incident.severity in (IncidentSeverity.p1, IncidentSeverity.p2) else "normal",
            )

        return NextAction(
            action="remote_remediation",
            owner="vodafone_engineering_team",
            reason="Attempt remote remediation before considering field dispatch",
            priority="normal",
        )

    @staticmethod
    def _infer_category(text: str) -> str:
        """Best-effort category from free text."""
        mapping = [
            ("hardware_failure", ["hardware", "disk", "psu", "fan", "chassis", "card", "module"]),
            ("power_failure", ["power", "ups", "generator", "mains"]),
            ("fibre_cut", ["fibre cut", "fiber cut", "fibre break", "fiber break"]),
            ("security_incident", ["security", "breach", "intrusion", "ddos", "malware"]),
            ("software_bug", ["software", "bug", "crash", "core dump", "segfault"]),
            ("config_error", ["config", "misconfigured", "acl", "policy"]),
        ]
        for cat, keywords in mapping:
            if any(kw in text for kw in keywords):
                return cat
        return ""
