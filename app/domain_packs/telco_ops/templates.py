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
    ReconciliationResult,
    RunbookReferenceObject,
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
            step_summaries.append({
                "step": step.step_number,
                "action": step.action,
                "automated": step.automated,
                "timeout": step.timeout_minutes,
            })

        confidence_label = "high" if applicability_score >= 0.8 else ("medium" if applicability_score >= 0.5 else "low")

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
            mismatch_details.append({
                "field": mm.field,
                "incident_value": mm.incident_value,
                "work_order_value": mm.work_order_value,
                "severity": mm.severity,
                "resolution": mm.resolution,
            })

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
            incident_summaries.append({
                "incident_id": inc.incident_id,
                "title": inc.title,
                "severity": inc.severity.value,
                "severity_label": severity_labels.get(inc.severity.value, "UNKNOWN"),
                "state": inc.state.value,
                "assigned_to": inc.assigned_to or "unassigned",
                "affected_services": inc.affected_services,
            })

        active_count = sum(
            1 for inc in incidents
            if inc.state.value not in ("resolved", "closed")
        )
        critical_count = sum(
            1 for inc in incidents
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
            "actions_taken_display": "\n".join(action_lines) if action_lines else "No actions recorded.",
            "pending_items": pending_items,
            "pending_items_display": "\n".join(pending_lines) if pending_lines else "No pending items.",
            "display_text": (
                f"Shift Handover | "
                f"Total: {len(incidents)} | Active: {active_count} | "
                f"Critical: {critical_count} | "
                f"Actions: {len(actions_taken)} | Pending: {len(pending_items)}"
            ),
        }
