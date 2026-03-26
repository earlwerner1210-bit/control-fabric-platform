"""Templates for rendering field readiness summaries and dispatch reports.

Each template class takes a domain model and produces a human-readable text
representation suitable for reports, LLM context, or audit logs.
"""

from __future__ import annotations

from ..schemas.field_schemas import (
    DispatchRecommendation,
    EngineerProfile,
    ParsedWorkOrder,
    ReadinessDecision,
)
from ..taxonomy.field_taxonomy import ReadinessStatus


class ReadinessSummaryTemplate:
    """Renders a readiness decision into a structured text summary."""

    def render(
        self,
        decision: ReadinessDecision,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> str:
        """Render a ReadinessDecision into a human-readable summary.

        Args:
            decision: The readiness decision to render.
            work_order: The work order being assessed.
            engineer: The engineer being considered.

        Returns:
            Multi-line formatted string.
        """
        status_labels = {
            ReadinessStatus.ready: "READY FOR DISPATCH",
            ReadinessStatus.blocked: "BLOCKED",
            ReadinessStatus.conditional: "CONDITIONAL",
            ReadinessStatus.escalate: "REQUIRES ESCALATION",
        }

        lines: list[str] = []
        lines.append("# Readiness Assessment Summary")
        lines.append("")
        lines.append(f"**Work Order:** {work_order.work_order_id} - {work_order.title}")
        lines.append(f"**Type:** {work_order.work_order_type.value}")
        lines.append(f"**Priority:** {work_order.priority}")
        lines.append(f"**Engineer:** {engineer.name} ({engineer.employee_number or 'N/A'})")
        lines.append(f"**Status:** {status_labels.get(decision.status, decision.status.value)}")
        lines.append(f"**Confidence:** {decision.confidence:.0%}")
        lines.append("")

        # Skill fit section
        sf = decision.skill_fit
        lines.append("## Skill Fit Analysis")
        lines.append(f"- Overall fit: {sf.overall_fit:.0%}")
        if sf.matched_skills:
            lines.append(f"- Matched: {', '.join(sf.matched_skills)}")
        if sf.missing_skills:
            lines.append(f"- Missing: {', '.join(sf.missing_skills)}")
        if sf.partially_matched:
            lines.append(f"- Partial match: {', '.join(sf.partially_matched)}")
        lines.append("")

        # Blockers
        if decision.blockers:
            lines.append("## Blockers")
            for blocker in decision.blockers:
                severity_marker = "[!]" if blocker.severity == "blocking" else "[~]"
                lines.append(f"- {severity_marker} **{blocker.category}**: {blocker.description}")
                if blocker.resolution_action:
                    lines.append(f"  - Action: {blocker.resolution_action}")
                if blocker.estimated_resolution_hours:
                    lines.append(
                        f"  - Est. resolution: {blocker.estimated_resolution_hours:.0f} hours"
                    )
            lines.append("")

        # Missing prerequisites
        if decision.missing_prerequisites:
            lines.append("## Missing Prerequisites")
            for prereq in decision.missing_prerequisites:
                lines.append(f"- {prereq}")
            lines.append("")

        # Recommendation
        lines.append("## Recommendation")
        lines.append(decision.recommendation)

        return "\n".join(lines)


class DispatchReportTemplate:
    """Renders a dispatch recommendation into a formatted report."""

    def render(
        self,
        recommendation: DispatchRecommendation,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile | None = None,
    ) -> str:
        """Render a DispatchRecommendation into a text report.

        Args:
            recommendation: The dispatch recommendation.
            work_order: The work order.
            engineer: Optional engineer profile.

        Returns:
            Multi-line formatted string.
        """
        lines: list[str] = []
        lines.append("# Dispatch Report")
        lines.append("")
        lines.append(f"**Work Order:** {recommendation.work_order_id}")
        lines.append(f"**Title:** {work_order.title}")
        lines.append(f"**Type:** {work_order.work_order_type.value}")
        lines.append(f"**Priority:** {work_order.priority}")
        lines.append(f"**Site:** {work_order.site_address or 'Not specified'}")

        if work_order.scheduled_date:
            time_str = ""
            if work_order.scheduled_time_start:
                time_str = f" {work_order.scheduled_time_start.strftime('%H:%M')}"
                if work_order.scheduled_time_end:
                    time_str += f" - {work_order.scheduled_time_end.strftime('%H:%M')}"
            lines.append(f"**Scheduled:** {work_order.scheduled_date.isoformat()}{time_str}")

        lines.append("")
        lines.append(
            f"**Dispatch Approved:** {'Yes' if recommendation.dispatch_approved else 'No'}"
        )

        if engineer:
            lines.append(f"**Assigned Engineer:** {engineer.name}")
        elif recommendation.recommended_engineer_id:
            lines.append(f"**Recommended Engineer ID:** {recommendation.recommended_engineer_id}")

        if recommendation.estimated_travel_time_minutes is not None:
            lines.append(
                f"**Est. Travel Time:** {recommendation.estimated_travel_time_minutes:.0f} minutes"
            )

        lines.append("")

        # Readiness summary
        r = recommendation.readiness
        status_labels = {
            ReadinessStatus.ready: "READY",
            ReadinessStatus.blocked: "BLOCKED",
            ReadinessStatus.conditional: "CONDITIONAL",
            ReadinessStatus.escalate: "ESCALATE",
        }
        lines.append("## Readiness")
        lines.append(f"- Status: {status_labels.get(r.status, r.status.value)}")
        lines.append(f"- Confidence: {r.confidence:.0%}")
        lines.append(f"- Skill fit: {r.skill_fit.overall_fit:.0%}")

        if r.blockers:
            lines.append(f"- Blockers: {len(r.blockers)}")
        lines.append("")

        # Special instructions
        if recommendation.special_instructions:
            lines.append("## Special Instructions")
            for instr in recommendation.special_instructions:
                lines.append(f"- {instr}")
            lines.append("")

        # Alternatives
        if recommendation.alternative_engineers:
            lines.append("## Alternative Engineers")
            for alt_id in recommendation.alternative_engineers:
                lines.append(f"- {alt_id}")
            lines.append("")

        # Recommendation text
        lines.append("## Recommendation")
        lines.append(r.recommendation)

        return "\n".join(lines)
