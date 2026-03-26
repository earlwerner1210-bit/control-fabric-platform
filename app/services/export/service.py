"""Export and reporting service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.report import (
    CaseExportRequest,
    CaseExportResponse,
    DecisionSummaryExport,
    ExportFormat,
    PilotReportSummary,
    ReviewSummaryExport,
)


class ExportService:
    """Generates exportable case summaries and pilot reports."""

    def __init__(self) -> None:
        self._exports: dict[uuid.UUID, list[dict[str, Any]]] = {}

    def export_case(
        self,
        pilot_case_id: uuid.UUID,
        exported_by: uuid.UUID,
        case_data: dict[str, Any],
        request: CaseExportRequest,
        evidence: dict[str, Any] | None = None,
        review: dict[str, Any] | None = None,
        kpis: list[dict[str, Any]] | None = None,
        feedback: list[dict[str, Any]] | None = None,
        baseline: dict[str, Any] | None = None,
    ) -> CaseExportResponse:
        content: dict[str, Any] = {
            "case": self._serialize_case(case_data),
        }

        if request.include_evidence and evidence:
            content["evidence"] = evidence
        if request.include_review and review:
            content["review"] = review
        if request.include_kpis and kpis:
            content["kpis"] = kpis
        if request.include_feedback and feedback:
            content["feedback"] = feedback
        if request.include_baseline and baseline:
            content["baseline"] = baseline

        if request.format == ExportFormat.MARKDOWN:
            content["markdown"] = self._render_markdown(content)

        export = {
            "id": uuid.uuid4(),
            "pilot_case_id": pilot_case_id,
            "format": request.format,
            "exported_by": exported_by,
            "content": content,
            "created_at": datetime.now(UTC),
        }
        self._exports.setdefault(pilot_case_id, []).append(export)
        return CaseExportResponse(**export)

    def get_exports(self, pilot_case_id: uuid.UUID) -> list[CaseExportResponse]:
        return [CaseExportResponse(**e) for e in self._exports.get(pilot_case_id, [])]

    def generate_pilot_report(
        self,
        cases: list[dict[str, Any]],
        kpi_summary: dict[str, Any] | None = None,
        feedback_summary: dict[str, Any] | None = None,
    ) -> PilotReportSummary:
        by_state: dict[str, int] = {}
        by_workflow: dict[str, int] = {}
        decision_summaries: list[DecisionSummaryExport] = []
        review_summaries: list[ReviewSummaryExport] = []

        for c in cases:
            state = c.get("state", "unknown")
            state_str = state.value if hasattr(state, "value") else str(state)
            by_state[state_str] = by_state.get(state_str, 0) + 1

            wt = c.get("workflow_type", "unknown")
            by_workflow[wt] = by_workflow.get(wt, 0) + 1

            decision_summaries.append(DecisionSummaryExport(
                pilot_case_id=c.get("id", uuid.uuid4()),
                title=c.get("title", ""),
                workflow_type=wt,
                state=state_str,
            ))

        return PilotReportSummary(
            generated_at=datetime.now(UTC),
            total_cases=len(cases),
            cases_by_state=by_state,
            cases_by_workflow=by_workflow,
            decision_summaries=decision_summaries,
            review_summaries=review_summaries,
            kpi_summary=kpi_summary or {},
            feedback_summary=feedback_summary or {},
        )

    def _serialize_case(self, case: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for k, v in case.items():
            if isinstance(v, uuid.UUID):
                result[k] = str(v)
            elif isinstance(v, datetime):
                result[k] = v.isoformat()
            elif hasattr(v, "value"):
                result[k] = v.value
            else:
                result[k] = v
        return result

    def _render_markdown(self, content: dict[str, Any]) -> str:
        lines = ["# Pilot Case Export", ""]
        case = content.get("case", {})
        lines.append(f"## {case.get('title', 'Untitled Case')}")
        lines.append(f"- **Workflow Type:** {case.get('workflow_type', 'N/A')}")
        lines.append(f"- **State:** {case.get('state', 'N/A')}")
        lines.append(f"- **Severity:** {case.get('severity', 'N/A')}")
        lines.append(f"- **Business Impact:** {case.get('business_impact', 'N/A')}")
        lines.append("")

        if "evidence" in content:
            lines.append("## Evidence")
            evidence = content["evidence"]
            lines.append(f"- **Completeness:** {evidence.get('completeness_score', 'N/A')}")
            lines.append(f"- **Chain Stages:** {', '.join(evidence.get('chain_stages', []))}")
            lines.append("")

        if "review" in content:
            lines.append("## Review")
            review = content["review"]
            if isinstance(review, dict):
                lines.append(f"- **Decisions:** {len(review.get('decisions', []))}")
                lines.append(f"- **Notes:** {len(review.get('notes', []))}")
            lines.append("")

        if "baseline" in content:
            lines.append("## Baseline Comparison")
            baseline = content["baseline"]
            if isinstance(baseline, dict):
                lines.append(f"- **Expected:** {baseline.get('expected_outcome', 'N/A')}")
                lines.append(f"- **Platform:** {baseline.get('platform_outcome', 'N/A')}")
                lines.append(f"- **Match Type:** {baseline.get('match_type', 'N/A')}")
            lines.append("")

        return "\n".join(lines)
