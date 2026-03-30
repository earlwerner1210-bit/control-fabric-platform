"""Templates for rendering contract summaries, obligation registers, and margin reports.

Each template class takes a domain model and produces a human-readable text
representation suitable for reports, LLM context, or audit logs.
"""

from __future__ import annotations

from ..schemas.contract_schemas import (
    MarginLeakageDiagnosis,
    ObligationRegister,
    ParsedContract,
    PenaltyExposureSummary,
)


class ContractSummaryTemplate:
    """Renders a parsed contract into a structured text summary."""

    def render(self, contract: ParsedContract) -> str:
        """Render a ParsedContract into a human-readable summary string.

        Args:
            contract: The parsed contract to summarise.

        Returns:
            Multi-line formatted string.
        """
        lines: list[str] = []
        lines.append(f"# Contract Summary: {contract.title}")
        lines.append("")
        lines.append(f"**Contract ID:** {contract.contract_id}")
        lines.append(f"**Type:** {contract.contract_type.value}")
        lines.append(
            f"**Parties:** {', '.join(contract.parties) if contract.parties else 'Not specified'}"
        )

        if contract.effective_date:
            lines.append(f"**Effective Date:** {contract.effective_date.isoformat()}")
        if contract.expiry_date:
            lines.append(f"**Expiry Date:** {contract.expiry_date.isoformat()}")
        if contract.billing_category:
            lines.append(f"**Billing Model:** {contract.billing_category.value}")
        if contract.total_value is not None:
            lines.append(f"**Total Value:** {contract.currency} {contract.total_value:,.2f}")

        lines.append("")
        lines.append("## Key Metrics")
        lines.append(f"- Clauses extracted: {len(contract.clauses)}")
        lines.append(f"- SLA metrics: {len(contract.sla_entries)}")
        lines.append(f"- Rate card entries: {len(contract.rate_card)}")
        lines.append(f"- Obligations: {len(contract.obligations)}")
        lines.append(f"- Penalty conditions: {len(contract.penalties)}")
        lines.append(f"- Billable events: {len(contract.billable_events)}")

        if contract.sla_entries:
            lines.append("")
            lines.append("## SLA Targets")
            for sla in contract.sla_entries:
                lines.append(
                    f"- {sla.metric_name}: {sla.target_value}{sla.unit} ({sla.measurement_period})"
                )

        if contract.rate_card:
            lines.append("")
            lines.append("## Rate Card")
            for rc in contract.rate_card:
                lines.append(f"- {rc.role_or_item}: {rc.currency} {rc.rate:.2f}/{rc.rate_unit}")

        if contract.penalties:
            lines.append("")
            lines.append("## Penalty Conditions")
            for penalty in contract.penalties:
                amount_str = ""
                if penalty.amount is not None:
                    amount_str = f" ({penalty.currency} {penalty.amount:,.2f})"
                elif penalty.amount_formula:
                    amount_str = f" ({penalty.amount_formula})"
                lines.append(
                    f"- [{penalty.penalty_type}]{amount_str}: {penalty.trigger_condition[:120]}"
                )

        return "\n".join(lines)


class ObligationRegisterTemplate:
    """Renders an obligation register into a formatted report."""

    def render(self, register: ObligationRegister) -> str:
        """Render an ObligationRegister into a text report.

        Args:
            register: The obligation register to render.

        Returns:
            Multi-line formatted string.
        """
        lines: list[str] = []
        lines.append("# Obligation Register")
        lines.append("")
        lines.append(f"**Register ID:** {register.register_id}")
        lines.append(f"**Contracts:** {', '.join(register.contract_ids)}")
        lines.append(f"**Generated:** {register.generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append("")
        lines.append("| Status | Count |")
        lines.append("|--------|-------|")
        lines.append(f"| Open   | {register.total_open} |")
        lines.append(f"| Met    | {register.total_met} |")
        lines.append(f"| Breached | {register.total_breached} |")
        lines.append("")

        if register.obligations:
            lines.append("## Obligations")
            lines.append("")
            for ob in register.obligations:
                status_marker = {
                    "open": "[ ]",
                    "met": "[x]",
                    "breached": "[!]",
                    "waived": "[-]",
                }.get(ob.status, "[ ]")
                due_str = f" (due: {ob.due_date.isoformat()})" if ob.due_date else ""
                lines.append(
                    f"- {status_marker} **{ob.obligation_id}** — {ob.obligated_party}: {ob.description[:150]}{due_str}"
                )

        return "\n".join(lines)


class MarginReportTemplate:
    """Renders a margin leakage diagnosis into an executive report."""

    def render(
        self,
        diagnosis: MarginLeakageDiagnosis,
        penalty_summary: PenaltyExposureSummary | None = None,
    ) -> str:
        """Render a margin diagnosis into a structured report.

        Args:
            diagnosis: The margin leakage diagnosis.
            penalty_summary: Optional penalty exposure summary to include.

        Returns:
            Multi-line formatted string.
        """
        lines: list[str] = []
        verdict_label = {
            "healthy": "HEALTHY",
            "at_risk": "AT RISK",
            "leaking": "LEAKING",
            "critical": "CRITICAL",
        }.get(diagnosis.verdict, diagnosis.verdict.upper())

        lines.append("# Margin Leakage Report")
        lines.append("")
        lines.append(f"**Verdict:** {verdict_label}")
        if diagnosis.total_estimated_leakage is not None:
            lines.append(
                f"**Estimated Total Leakage:** {diagnosis.currency} "
                f"{diagnosis.total_estimated_leakage:,.2f}"
            )
        lines.append("")

        if diagnosis.executive_summary:
            lines.append("## Executive Summary")
            lines.append("")
            lines.append(diagnosis.executive_summary)
            lines.append("")

        if diagnosis.leakage_drivers:
            lines.append("## Leakage Drivers")
            lines.append("")
            for driver in diagnosis.leakage_drivers:
                lines.append(f"- {driver.value.replace('_', ' ').title()}")
            lines.append("")

        if diagnosis.recovery_recommendations:
            lines.append("## Recovery Recommendations")
            lines.append("")
            for idx, rec in enumerate(diagnosis.recovery_recommendations, 1):
                lines.append(
                    f"### {idx}. {rec.driver.value.replace('_', ' ').title()} [{rec.priority.upper()}]"
                )
                lines.append(f"**Action:** {rec.action}")
                if rec.estimated_recovery is not None:
                    lines.append(
                        f"**Estimated Recovery:** {rec.currency} {rec.estimated_recovery:,.2f}"
                    )
                lines.append("")

        if penalty_summary:
            lines.append("## Penalty Exposure")
            lines.append("")
            lines.append(f"- Total penalty conditions: {penalty_summary.total_penalties}")
            lines.append(f"- Unmitigated: {len(penalty_summary.unmitigated_penalties)}")
            if penalty_summary.total_exposure_amount is not None:
                lines.append(
                    f"- Total exposure: {penalty_summary.currency} "
                    f"{penalty_summary.total_exposure_amount:,.2f}"
                )
            lines.append("")

        return "\n".join(lines)
