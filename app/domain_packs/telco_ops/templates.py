"""Telco Ops rendering templates.

Each template class provides a ``render`` static method that returns a
structured dict ready for serialisation / API response.
"""

from __future__ import annotations

from typing import Any

from app.domain_packs.telco_ops.schemas import (
    EscalationDecision,
    NextAction,
    ParsedIncident,
    ReconciliationMismatch,
    ReconciliationResult,
    ReconciliationStatus,
    RunbookReferenceObject,
    ServiceStateObject,
)

# ---------------------------------------------------------------------------
# IncidentNoteTemplate
# ---------------------------------------------------------------------------


class IncidentNoteTemplate:
    """Render an incident analysis into a structured note."""

    @staticmethod
    def render(incident: ParsedIncident, analysis: dict) -> dict:
        severity_labels = {"p1": "CRITICAL", "p2": "HIGH", "p3": "MEDIUM", "p4": "LOW"}
        label = severity_labels.get(incident.severity.value, "UNKNOWN")

        summary_parts = [
            f"[{label}] {incident.title or 'Untitled incident'} ({incident.incident_id})",
        ]
        if incident.affected_services:
            summary_parts.append(f"Affected services: {', '.join(incident.affected_services)}")
        if incident.assigned_to:
            summary_parts.append(f"Assigned to: {incident.assigned_to}")

        return {
            "template": "incident_note",
            "incident_id": incident.incident_id,
            "severity": incident.severity.value,
            "severity_label": label,
            "state": incident.state.value,
            "headline": summary_parts[0],
            "body": "\n".join(summary_parts),
            "analysis_summary": analysis.get("summary", ""),
            "root_cause": analysis.get("root_cause", "Under investigation"),
            "impact": analysis.get("impact", ""),
            "recommended_actions": analysis.get("recommended_actions", []),
            "tags": incident.tags,
            "created_at": incident.created_at,
        }


# ---------------------------------------------------------------------------
# NextActionNoteTemplate
# ---------------------------------------------------------------------------


class NextActionNoteTemplate:
    """Render a next-action recommendation into a structured note."""

    @staticmethod
    def render(action: NextAction, rationale: str) -> dict:
        priority_emoji_map = {"critical": "!!!", "high": "!!", "normal": "!", "low": ""}
        urgency = priority_emoji_map.get(action.priority, "")

        return {
            "template": "next_action_note",
            "action": action.action,
            "owner": action.owner or "unassigned",
            "priority": action.priority,
            "urgency_marker": urgency,
            "reason": action.reason,
            "rationale": rationale,
            "evidence_ids": [str(eid) for eid in action.evidence_ids],
            "display_text": (
                f"{'[' + action.priority.upper() + '] ' if action.priority else ''}"
                f"Action: {action.action} | Owner: {action.owner or 'unassigned'} | "
                f"Reason: {action.reason}"
            ),
        }


# ---------------------------------------------------------------------------
# RunbookSummaryTemplate
# ---------------------------------------------------------------------------


class RunbookSummaryTemplate:
    """Render a runbook recommendation summary."""

    @staticmethod
    def render(runbook: RunbookReferenceObject, applicability_score: float) -> dict:
        step_summaries = []
        for step in runbook.steps:
            step_summaries.append(
                {
                    "step": step.step_number,
                    "action": step.action,
                    "automated": step.automated,
                    "timeout": step.timeout_minutes,
                }
            )

        confidence_label = (
            "high"
            if applicability_score >= 0.8
            else ("medium" if applicability_score >= 0.5 else "low")
        )

        return {
            "template": "runbook_summary",
            "runbook_id": runbook.runbook_id,
            "title": runbook.title,
            "applicable_services": runbook.applicable_services,
            "applicable_severity": runbook.applicable_severity,
            "estimated_time_minutes": runbook.estimated_time_minutes,
            "success_rate": runbook.success_rate,
            "last_updated": runbook.last_updated,
            "step_count": len(runbook.steps),
            "steps": step_summaries,
            "automated_step_count": sum(1 for s in runbook.steps if s.automated),
            "applicability_score": applicability_score,
            "confidence_label": confidence_label,
            "display_text": (
                f"Runbook: {runbook.title} ({runbook.runbook_id}) | "
                f"Confidence: {confidence_label} ({applicability_score:.0%}) | "
                f"Est. time: {runbook.estimated_time_minutes} min | "
                f"Success rate: {runbook.success_rate:.0%}"
            ),
        }


# ---------------------------------------------------------------------------
# EscalationNoteTemplate
# ---------------------------------------------------------------------------


class EscalationNoteTemplate:
    """Render an escalation decision into a structured note."""

    @staticmethod
    def render(escalation: EscalationDecision, ownership_chain: list[str]) -> dict:
        level_str = escalation.level.value if escalation.level else "none"
        chain_str = " → ".join(ownership_chain) if ownership_chain else "Not defined"

        return {
            "template": "escalation_note",
            "escalate": escalation.escalate,
            "level": level_str,
            "owner": escalation.owner,
            "reason": escalation.reason,
            "evidence_ids": [str(eid) for eid in escalation.evidence_ids],
            "ownership_chain": ownership_chain,
            "ownership_chain_display": chain_str,
            "display_text": (
                f"Escalation {'REQUIRED' if escalation.escalate else 'not required'} | "
                f"Level: {level_str} | Owner: {escalation.owner or 'N/A'} | "
                f"Chain: {chain_str}"
            ),
        }


# ---------------------------------------------------------------------------
# ReconciliationSummaryTemplate
# ---------------------------------------------------------------------------


class ReconciliationSummaryTemplate:
    """Render a reconciliation result into a structured summary."""

    @staticmethod
    def render(result: ReconciliationResult, context: dict) -> dict:
        status_labels = {
            "aligned": "ALIGNED",
            "mismatched": "MISMATCH DETECTED",
            "partial": "PARTIALLY ALIGNED",
            "unknown": "UNKNOWN",
        }
        label = status_labels.get(result.status.value, "UNKNOWN")

        mismatch_details = []
        for mm in result.mismatches:
            mismatch_details.append(
                {
                    "field": mm.field,
                    "incident_value": mm.incident_value,
                    "work_order_value": mm.work_order_value,
                    "severity": mm.severity,
                    "resolution": mm.resolution,
                }
            )

        return {
            "template": "reconciliation_summary",
            "status": result.status.value,
            "status_label": label,
            "confidence": result.confidence,
            "mismatch_count": len(result.mismatches),
            "mismatches": mismatch_details,
            "recommendations": result.recommendations,
            "context": context,
            "display_text": (
                f"Reconciliation: {label} | "
                f"Confidence: {result.confidence:.0%} | "
                f"Mismatches: {len(result.mismatches)} | "
                f"Recommendations: {len(result.recommendations)}"
            ),
        }


# ---------------------------------------------------------------------------
# OpsShiftHandoverTemplate
# ---------------------------------------------------------------------------


class OpsShiftHandoverTemplate:
    """Render a shift-handover summary covering multiple incidents."""

    @staticmethod
    def render(
        incidents: list[ParsedIncident],
        actions_taken: list[dict],
        pending_items: list[dict],
    ) -> dict:
        severity_labels = {"p1": "CRITICAL", "p2": "HIGH", "p3": "MEDIUM", "p4": "LOW"}

        incident_summaries = []
        for inc in incidents:
            incident_summaries.append(
                {
                    "incident_id": inc.incident_id,
                    "title": inc.title,
                    "severity": inc.severity.value,
                    "severity_label": severity_labels.get(inc.severity.value, "UNKNOWN"),
                    "state": inc.state.value,
                    "assigned_to": inc.assigned_to or "unassigned",
                    "affected_services": inc.affected_services,
                }
            )

        active_count = sum(1 for inc in incidents if inc.state.value not in ("resolved", "closed"))
        critical_count = sum(
            1
            for inc in incidents
            if inc.severity.value in ("p1", "p2") and inc.state.value not in ("resolved", "closed")
        )

        action_lines = []
        for a in actions_taken:
            action_lines.append(
                f"- [{a.get('timestamp', '')}] {a.get('action', '')} "
                f"on {a.get('incident_id', 'N/A')} by {a.get('actor', 'unknown')}"
            )

        pending_lines = []
        for p in pending_items:
            pending_lines.append(
                f"- {p.get('description', '')} "
                f"(incident: {p.get('incident_id', 'N/A')}, "
                f"priority: {p.get('priority', 'normal')})"
            )

        return {
            "template": "ops_shift_handover",
            "total_incidents": len(incidents),
            "active_incidents": active_count,
            "critical_active_incidents": critical_count,
            "incidents": incident_summaries,
            "actions_taken": actions_taken,
            "actions_taken_display": "\n".join(action_lines)
            if action_lines
            else "No actions recorded.",
            "pending_items": pending_items,
            "pending_items_display": "\n".join(pending_lines)
            if pending_lines
            else "No pending items.",
            "display_text": (
                f"Shift Handover | "
                f"Total: {len(incidents)} | Active: {active_count} | "
                f"Critical: {critical_count} | "
                f"Actions: {len(actions_taken)} | Pending: {len(pending_items)}"
            ),
        }


# ---------------------------------------------------------------------------
# IncidentSummaryTemplate
# ---------------------------------------------------------------------------


class IncidentSummaryTemplate:
    """Render a structured incident summary combining incident data,
    escalation decisions, next actions, and service states."""

    @staticmethod
    def render(
        incident: ParsedIncident,
        escalation: EscalationDecision | None = None,
        next_action: NextAction | None = None,
        service_states: list[ServiceStateObject] | None = None,
    ) -> dict[str, Any]:
        service_states = service_states or []

        # Build service state overview
        service_state_entries = [
            {
                "service_id": ss.service_id,
                "service_name": ss.service_name,
                "state": ss.state.value,
                "impact_level": ss.impact_level.value,
                "affected_customers": ss.affected_customers,
                "recovery_eta_minutes": ss.recovery_eta_minutes,
            }
            for ss in service_states
        ]

        total_affected_customers = sum(ss.affected_customers for ss in service_states)

        # Determine overall service health from the worst state observed
        state_priority = {
            "outage": 0,
            "degraded": 1,
            "maintenance": 2,
            "provisioning": 3,
            "active": 4,
        }
        if service_states:
            worst_state = min(
                service_states,
                key=lambda ss: state_priority.get(ss.state.value, 99),
            )
            overall_service_health = worst_state.state.value
        else:
            overall_service_health = "unknown"

        # Build escalation summary
        escalation_summary: dict[str, Any] | None = None
        if escalation is not None:
            escalation_summary = {
                "escalate": escalation.escalate,
                "level": escalation.level.value if escalation.level else None,
                "owner": escalation.owner or None,
                "reason": escalation.reason or None,
            }

        # Build next action summary
        next_action_summary: dict[str, Any] | None = None
        if next_action is not None:
            next_action_summary = {
                "action": next_action.action,
                "owner": next_action.owner or None,
                "reason": next_action.reason or None,
                "priority": next_action.priority,
                "evidence_count": len(next_action.evidence_ids),
            }

        # Compose the title-line summary
        severity_label = incident.severity.value.upper()
        state_label = incident.state.value.replace("_", " ").title()
        summary_line = (
            f"[{severity_label}] {incident.title or incident.incident_id} - {state_label}"
        )
        if escalation and escalation.escalate and escalation.level:
            summary_line += f" | Escalated to {escalation.level.value.upper()}"

        return {
            "incident_id": incident.incident_id,
            "title": incident.title,
            "severity": incident.severity.value,
            "state": incident.state.value,
            "summary": summary_line,
            "affected_services": incident.affected_services,
            "reported_by": incident.reported_by,
            "assigned_to": incident.assigned_to,
            "created_at": incident.created_at,
            "updated_at": incident.updated_at,
            "tag_count": len(incident.tags),
            "escalation": escalation_summary,
            "next_action": next_action_summary,
            "service_states": service_state_entries,
            "overall_service_health": overall_service_health,
            "total_affected_customers": total_affected_customers,
            "service_count": len(service_states),
        }


# ---------------------------------------------------------------------------
# OpsNoteTemplate
# ---------------------------------------------------------------------------


class OpsNoteTemplate:
    """Render a concise operational note suitable for hand-off, shift logs,
    or ticketing system updates."""

    @staticmethod
    def render(
        incident: ParsedIncident,
        next_action: NextAction | None = None,
        runbook_ref: str | None = None,
        escalation: EscalationDecision | None = None,
    ) -> dict[str, Any]:
        # Build the narrative summary
        severity_label = incident.severity.value.upper()
        lines: list[str] = [
            f"{severity_label} incident '{incident.title or incident.incident_id}' "
            f"is currently {incident.state.value}.",
        ]

        if incident.affected_services:
            lines.append(f"Affected services: {', '.join(incident.affected_services)}.")

        if next_action:
            action_text = (
                f"Next action: {next_action.action}"
                + (f" (owner: {next_action.owner})" if next_action.owner else "")
                + "."
            )
            if next_action.reason:
                action_text += f" Reason: {next_action.reason}."
            lines.append(action_text)

        if escalation and escalation.escalate:
            esc_text = (
                f"Escalated to {escalation.level.value.upper() if escalation.level else 'UNKNOWN'}"
            )
            if escalation.owner:
                esc_text += f" (owner: {escalation.owner})"
            esc_text += "."
            if escalation.reason:
                esc_text += f" {escalation.reason}."
            lines.append(esc_text)

        if runbook_ref:
            lines.append(f"Runbook reference: {runbook_ref}.")

        narrative = " ".join(lines)

        # Collect evidence IDs from all sources, deduplicated
        evidence_ids: list[str] = []
        seen: set[str] = set()
        for source in (next_action, escalation):
            if source is not None:
                for eid in source.evidence_ids:
                    eid_str = str(eid)
                    if eid_str not in seen:
                        seen.add(eid_str)
                        evidence_ids.append(eid_str)

        return {
            "summary": narrative,
            "next_action": next_action.action if next_action else None,
            "next_action_owner": next_action.owner if next_action else None,
            "next_action_priority": next_action.priority if next_action else None,
            "runbook_ref": runbook_ref,
            "escalation_level": (
                escalation.level.value if escalation and escalation.level else None
            ),
            "escalation_owner": (escalation.owner if escalation and escalation.escalate else None),
            "incident_id": incident.incident_id,
            "severity": incident.severity.value,
            "state": incident.state.value,
            "affected_services": incident.affected_services,
            "evidence_ids": evidence_ids,
        }


# ---------------------------------------------------------------------------
# ReconciliationReportTemplate
# ---------------------------------------------------------------------------


class ReconciliationReportTemplate:
    """Render a structured reconciliation report from status, mismatches,
    and recommendations."""

    @staticmethod
    def render(
        status: ReconciliationStatus,
        mismatches: list[ReconciliationMismatch] | None = None,
        recommendations: list[str] | None = None,
    ) -> dict[str, Any]:
        mismatches = mismatches or []
        recommendations = recommendations or []

        # Categorise mismatches by severity
        severity_counts: dict[str, int] = {}
        mismatch_entries: list[dict[str, Any]] = []
        for m in mismatches:
            sev = m.severity or "info"
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            mismatch_entries.append(
                {
                    "field": m.field,
                    "incident_value": m.incident_value,
                    "work_order_value": m.work_order_value,
                    "severity": sev,
                    "resolution": m.resolution,
                }
            )

        # Determine a human-readable verdict
        if status == ReconciliationStatus.aligned:
            verdict = "All records are aligned. No action required."
        elif status == ReconciliationStatus.mismatched:
            critical_count = severity_counts.get("critical", 0)
            error_count = severity_counts.get("error", 0)
            verdict = (
                f"Records are mismatched with {critical_count} critical and "
                f"{error_count} error-level discrepancies. Immediate review required."
            )
        elif status == ReconciliationStatus.partial:
            verdict = "Records are partially aligned. Review warnings before closing."
        else:
            verdict = "Reconciliation status is unknown. Manual review recommended."

        # Determine whether the report requires action
        requires_action = (
            status
            in (
                ReconciliationStatus.mismatched,
                ReconciliationStatus.unknown,
            )
            or severity_counts.get("critical", 0) > 0
        )

        return {
            "report_type": "incident_reconciliation",
            "status": status.value,
            "verdict": verdict,
            "requires_action": requires_action,
            "mismatch_count": len(mismatches),
            "mismatches": mismatch_entries,
            "severity_breakdown": severity_counts,
            "recommendation_count": len(recommendations),
            "recommendations": recommendations,
        }
