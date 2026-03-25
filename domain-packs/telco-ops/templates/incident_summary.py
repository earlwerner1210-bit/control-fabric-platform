"""Templates for rendering incident summaries and operational notes.

Each template class takes a domain model and produces a human-readable text
representation suitable for reports, handoffs, or LLM context.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..schemas.telco_schemas import (
    IncidentSummary,
    OpsNote,
    ParsedIncident,
)
from ..taxonomy.telco_taxonomy import IncidentSeverity, IncidentState


class IncidentSummaryTemplate:
    """Renders an incident into a structured summary."""

    def render(self, incident: ParsedIncident) -> str:
        """Render a ParsedIncident into a human-readable summary.

        Args:
            incident: The incident to summarise.

        Returns:
            Multi-line formatted string.
        """
        lines: list[str] = []

        severity_labels = {
            IncidentSeverity.p1: "P1 - CRITICAL",
            IncidentSeverity.p2: "P2 - HIGH",
            IncidentSeverity.p3: "P3 - MEDIUM",
            IncidentSeverity.p4: "P4 - LOW",
        }

        lines.append(f"# Incident Summary: {incident.incident_id}")
        lines.append("")
        lines.append(f"**Title:** {incident.title}")
        lines.append(f"**Severity:** {severity_labels.get(incident.severity, incident.severity.value)}")
        lines.append(f"**State:** {incident.state.value}")
        lines.append(f"**Escalation Level:** {incident.escalation_level.value.upper()}")

        if incident.assigned_to:
            lines.append(f"**Assigned To:** {incident.assigned_to}")
        if incident.reporter:
            lines.append(f"**Reported By:** {incident.reporter}")

        # Duration
        if incident.reported_at:
            lines.append(f"**Reported At:** {incident.reported_at.isoformat()}")
            if incident.resolved_at:
                duration = (incident.resolved_at - incident.reported_at).total_seconds() / 60
                lines.append(f"**Resolved At:** {incident.resolved_at.isoformat()}")
                lines.append(f"**Duration:** {duration:.0f} minutes")
            else:
                now = datetime.now(timezone.utc)
                reported = incident.reported_at
                if reported.tzinfo is None:
                    reported = reported.replace(tzinfo=timezone.utc)
                elapsed = (now - reported).total_seconds() / 60
                lines.append(f"**Elapsed:** {elapsed:.0f} minutes (ongoing)")

        lines.append("")

        # Description
        if incident.description and incident.description != incident.title:
            lines.append("## Description")
            # Truncate long descriptions
            desc = incident.description[:1000]
            if len(incident.description) > 1000:
                desc += "..."
            lines.append(desc)
            lines.append("")

        # Affected services
        if incident.affected_services:
            lines.append("## Affected Services")
            total_customers = 0
            for svc in incident.affected_services:
                lines.append(
                    f"- **{svc.service_name}**: {svc.state.value} "
                    f"({svc.affected_customers:,} customers, {svc.region or 'all regions'})"
                )
                total_customers += svc.affected_customers
            lines.append(f"\n**Total Affected Customers:** {total_customers:,}")
            lines.append("")

        # Recurring incident
        if incident.is_recurring:
            lines.append(f"## Recurrence")
            lines.append(f"This is a **recurring incident** (occurrence #{incident.recurrence_count}).")
            if incident.related_incident_ids:
                lines.append(f"Related incidents: {', '.join(incident.related_incident_ids)}")
            lines.append("")

        # Root cause and resolution
        if incident.root_cause:
            lines.append("## Root Cause")
            lines.append(incident.root_cause)
            lines.append("")

        if incident.resolution_notes:
            lines.append("## Resolution")
            lines.append(incident.resolution_notes)
            lines.append("")

        # Tags
        if incident.tags:
            lines.append(f"**Tags:** {', '.join(incident.tags)}")

        return "\n".join(lines)

    def render_compact(self, incident: ParsedIncident) -> str:
        """Render a compact one-line summary suitable for dashboards.

        Args:
            incident: The incident to summarise.

        Returns:
            Single-line string.
        """
        svc_count = len(incident.affected_services)
        customer_count = sum(s.affected_customers for s in incident.affected_services)
        owner = incident.assigned_to or "UNASSIGNED"

        return (
            f"[{incident.severity.value.upper()}] {incident.incident_id}: "
            f"{incident.title} | {incident.state.value} | "
            f"{svc_count} services, {customer_count:,} customers | "
            f"Owner: {owner}"
        )


class OpsNoteTemplate:
    """Renders an operational note for incident handoff."""

    def render(self, note: OpsNote) -> str:
        """Render an OpsNote into a formatted handoff note.

        Args:
            note: The operational note to render.

        Returns:
            Multi-line formatted string.
        """
        lines: list[str] = []
        lines.append(f"# Ops Note: {note.note_id}")
        lines.append("")
        lines.append(f"**Incident:** {note.incident_id}")
        lines.append(f"**Author:** {note.author}")
        lines.append(f"**Generated:** {note.generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append("")

        lines.append("## Summary")
        lines.append(note.summary)
        lines.append("")

        if note.service_state_explanation:
            lines.append("## Service Impact")
            lines.append(note.service_state_explanation)
            lines.append("")

        lines.append("## Next Action")
        na = note.next_action
        lines.append(f"- **Action:** {na.action}")
        lines.append(f"- **Type:** {na.action_type}")
        if na.owner:
            lines.append(f"- **Owner:** {na.owner}")
        lines.append(f"- **Priority:** {na.priority}")
        if na.estimated_minutes:
            lines.append(f"- **Est. Time:** {na.estimated_minutes:.0f} minutes")
        if na.rationale:
            lines.append(f"- **Rationale:** {na.rationale}")
        lines.append("")

        if note.escalation:
            esc = note.escalation
            lines.append("## Escalation")
            lines.append(f"- **Level:** {esc.level.value.upper()}")
            if esc.owner:
                lines.append(f"- **Owner:** {esc.owner}")
            lines.append(f"- **Reason:** {esc.reason}")
            lines.append(f"- **Urgency:** {esc.urgency}")
            lines.append(f"- **Should Escalate:** {'Yes' if esc.should_escalate else 'No'}")
            lines.append("")

        if note.runbook_ref:
            lines.append("## Runbook Reference")
            lines.append(f"Applicable runbook: {note.runbook_ref}")
            lines.append("")

        return "\n".join(lines)
