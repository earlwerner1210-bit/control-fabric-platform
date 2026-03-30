"""Pilot reporting service — generates reports for pilot case lifecycle."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.reporting import (
    BaselineComparisonReport,
    OverrideEscalationReport,
    PilotCaseReport,
    PilotSummaryReport,
    ReviewerKpiBreakdown,
    WorkflowBreakdownReport,
)


class PilotReportingService:
    """Generates reports for pilot case operations.

    Works with in-memory service layer for pilot cases, reviews,
    approvals, evidence, baselines, KPIs, and feedback.
    """

    def __init__(
        self,
        case_service: Any = None,
        review_service: Any = None,
        approval_service: Any = None,
        evidence_service: Any = None,
        baseline_service: Any = None,
        kpi_service: Any = None,
        feedback_service: Any = None,
    ) -> None:
        self.case_service = case_service
        self.review_service = review_service
        self.approval_service = approval_service
        self.evidence_service = evidence_service
        self.baseline_service = baseline_service
        self.kpi_service = kpi_service
        self.feedback_service = feedback_service

    def get_pilot_case_report(
        self,
        pilot_case_id: uuid.UUID,
    ) -> PilotCaseReport | None:
        """Generate a detailed report for a single pilot case."""
        if not self.case_service:
            return None

        case = self.case_service.get_case(pilot_case_id)
        if case is None:
            return None

        # Evidence completeness
        evidence_completeness = 0.0
        if self.evidence_service:
            bundle = self.evidence_service.get_bundle(pilot_case_id)
            if bundle:
                evidence_completeness = bundle.completeness_score

        # Review outcome
        review_outcome = None
        reviewer_confidence = None
        if self.review_service:
            summary = self.review_service.get_summary(pilot_case_id)
            if summary:
                review_outcome = summary.latest_outcome.value if summary.latest_outcome else None
                reviewer_confidence = summary.confidence

        # Approval type, override, escalation
        approval_type = None
        override_reason = None
        escalation_route = None
        if self.approval_service:
            approvals = self.approval_service.get_approvals(pilot_case_id)
            if approvals:
                approval_type = "approval"
            overrides = self.approval_service.get_overrides(pilot_case_id)
            if overrides:
                approval_type = "override"
                override_reason = (
                    overrides[-1].override_reason.value
                    if hasattr(overrides[-1].override_reason, "value")
                    else str(overrides[-1].override_reason)
                )
            escalations = self.approval_service.get_escalations(pilot_case_id)
            if escalations:
                approval_type = "escalation"
                escalation_route = (
                    escalations[-1].escalation_route.value
                    if hasattr(escalations[-1].escalation_route, "value")
                    else str(escalations[-1].escalation_route)
                )

        # Baseline
        baseline_match_type = None
        if self.baseline_service:
            comp = self.baseline_service.get_comparison(pilot_case_id)
            if comp:
                baseline_match_type = (
                    comp.match_type.value
                    if hasattr(comp.match_type, "value")
                    else str(comp.match_type)
                )

        # KPIs
        kpi_measurements = []
        if self.kpi_service:
            measurements = self.kpi_service.get_case_measurements(pilot_case_id)
            kpi_measurements = [
                {"metric_name": m.metric_name, "metric_value": m.metric_value} for m in measurements
            ]

        # Feedback count
        feedback_count = 0
        if self.feedback_service:
            feedback = self.feedback_service.get_case_feedback(pilot_case_id)
            feedback_count = len(feedback)

        # Timeline
        timeline_events = len(self.case_service.get_timeline(pilot_case_id))

        return PilotCaseReport(
            pilot_case_id=case.id,
            title=case.title,
            workflow_type=case.workflow_type,
            state=case.state.value if hasattr(case.state, "value") else str(case.state),
            severity=case.severity.value if hasattr(case.severity, "value") else str(case.severity),
            business_impact=case.business_impact.value
            if hasattr(case.business_impact, "value")
            else str(case.business_impact),
            evidence_completeness=evidence_completeness,
            review_outcome=review_outcome,
            reviewer_confidence=reviewer_confidence,
            approval_type=approval_type,
            override_reason=override_reason,
            escalation_route=escalation_route,
            baseline_match_type=baseline_match_type,
            kpi_measurements=kpi_measurements,
            feedback_count=feedback_count,
            timeline_events=timeline_events,
            created_at=case.created_at,
        )

    def get_pilot_summary_report(
        self,
        tenant_id: uuid.UUID,
    ) -> PilotSummaryReport:
        """Generate a summary report across all pilot cases for a tenant."""
        if not self.case_service:
            return PilotSummaryReport(generated_at=datetime.now(UTC), total_cases=0)

        cases, total = self.case_service.list_cases(tenant_id, page_size=1000)

        by_state: dict[str, int] = {}
        by_workflow: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        confidences: list[float] = []
        evidence_scores: list[float] = []

        for case in cases:
            state = case.state.value if hasattr(case.state, "value") else str(case.state)
            by_state[state] = by_state.get(state, 0) + 1
            by_workflow[case.workflow_type] = by_workflow.get(case.workflow_type, 0) + 1
            sev = case.severity.value if hasattr(case.severity, "value") else str(case.severity)
            by_severity[sev] = by_severity.get(sev, 0) + 1

            if self.evidence_service:
                bundle = self.evidence_service.get_bundle(case.id)
                if bundle:
                    evidence_scores.append(bundle.completeness_score)

            if self.review_service:
                summary = self.review_service.get_summary(case.id)
                if summary and summary.confidence:
                    confidences.append(summary.confidence)

        resolved = sum(
            by_state.get(s, 0)
            for s in ("approved", "overridden", "escalated", "exported", "closed")
        )
        approved = (
            by_state.get("approved", 0) + by_state.get("exported", 0) + by_state.get("closed", 0)
        )
        overridden = by_state.get("overridden", 0)
        escalated = by_state.get("escalated", 0)

        return PilotSummaryReport(
            generated_at=datetime.now(UTC),
            total_cases=total,
            cases_by_state=by_state,
            cases_by_workflow=by_workflow,
            cases_by_severity=by_severity,
            approval_rate=approved / resolved if resolved > 0 else 0.0,
            override_rate=overridden / resolved if resolved > 0 else 0.0,
            escalation_rate=escalated / resolved if resolved > 0 else 0.0,
            avg_evidence_completeness=sum(evidence_scores) / len(evidence_scores)
            if evidence_scores
            else 0.0,
            avg_reviewer_confidence=sum(confidences) / len(confidences) if confidences else 0.0,
        )

    def get_workflow_breakdown_report(
        self,
        tenant_id: uuid.UUID,
    ) -> list[WorkflowBreakdownReport]:
        """Generate per-workflow-type breakdown report."""
        if not self.case_service:
            return []

        cases, _ = self.case_service.list_cases(tenant_id, page_size=1000)
        by_workflow: dict[str, list[Any]] = {}
        for case in cases:
            by_workflow.setdefault(case.workflow_type, []).append(case)

        results = []
        for wt, wf_cases in by_workflow.items():
            total = len(wf_cases)
            state_counts: dict[str, int] = {}
            for c in wf_cases:
                s = c.state.value if hasattr(c.state, "value") else str(c.state)
                state_counts[s] = state_counts.get(s, 0) + 1

            results.append(
                WorkflowBreakdownReport(
                    workflow_type=wt,
                    total_cases=total,
                    approved=state_counts.get("approved", 0) + state_counts.get("exported", 0),
                    overridden=state_counts.get("overridden", 0),
                    escalated=state_counts.get("escalated", 0),
                    pending_review=state_counts.get("under_review", 0),
                )
            )

        return results

    def get_override_escalation_report(
        self,
        tenant_id: uuid.UUID,
    ) -> OverrideEscalationReport:
        """Generate override and escalation summary report."""
        if not self.case_service:
            return OverrideEscalationReport(generated_at=datetime.now(UTC))

        cases, total = self.case_service.list_cases(tenant_id, page_size=1000)

        overrides_by_reason: dict[str, int] = {}
        escalations_by_route: dict[str, int] = {}
        override_cases: list[dict[str, Any]] = []
        escalation_cases: list[dict[str, Any]] = []

        for case in cases:
            state = case.state.value if hasattr(case.state, "value") else str(case.state)

            if state == "overridden" and self.approval_service:
                overrides = self.approval_service.get_overrides(case.id)
                for o in overrides:
                    reason = (
                        o.override_reason.value
                        if hasattr(o.override_reason, "value")
                        else str(o.override_reason)
                    )
                    overrides_by_reason[reason] = overrides_by_reason.get(reason, 0) + 1
                    override_cases.append(
                        {
                            "pilot_case_id": str(case.id),
                            "title": case.title,
                            "override_reason": reason,
                        }
                    )

            if state == "escalated" and self.approval_service:
                escalations = self.approval_service.get_escalations(case.id)
                for e in escalations:
                    route = (
                        e.escalation_route.value
                        if hasattr(e.escalation_route, "value")
                        else str(e.escalation_route)
                    )
                    escalations_by_route[route] = escalations_by_route.get(route, 0) + 1
                    escalation_cases.append(
                        {
                            "pilot_case_id": str(case.id),
                            "title": case.title,
                            "escalation_route": route,
                        }
                    )

        resolved = sum(
            1
            for c in cases
            if (c.state.value if hasattr(c.state, "value") else str(c.state))
            in ("approved", "overridden", "escalated", "exported", "closed")
        )

        return OverrideEscalationReport(
            generated_at=datetime.now(UTC),
            total_overrides=len(override_cases),
            total_escalations=len(escalation_cases),
            overrides_by_reason=overrides_by_reason,
            escalations_by_route=escalations_by_route,
            override_cases=override_cases,
            escalation_cases=escalation_cases,
            override_rate=len(override_cases) / resolved if resolved > 0 else 0.0,
            escalation_rate=len(escalation_cases) / resolved if resolved > 0 else 0.0,
        )

    def get_baseline_comparison_report(
        self,
        tenant_id: uuid.UUID,
    ) -> BaselineComparisonReport:
        """Generate baseline comparison summary report."""
        if not self.baseline_service:
            return BaselineComparisonReport(generated_at=datetime.now(UTC), total_compared=0)

        summary = self.baseline_service.get_summary()

        return BaselineComparisonReport(
            generated_at=datetime.now(UTC),
            total_compared=summary.total_compared,
            exact_matches=summary.exact_matches,
            partial_matches=summary.partial_matches,
            false_positives=summary.false_positives,
            false_negatives=summary.false_negatives,
            useful_not_correct=summary.useful_not_correct,
            accuracy_rate=summary.accuracy_rate,
        )

    def get_reviewer_kpi_breakdown(
        self,
        tenant_id: uuid.UUID,
    ) -> list[ReviewerKpiBreakdown]:
        """Generate per-reviewer KPI breakdown."""
        if not self.case_service or not self.review_service:
            return []

        cases, _ = self.case_service.list_cases(tenant_id, page_size=1000)
        reviewer_stats: dict[uuid.UUID, dict[str, Any]] = {}

        for case in cases:
            review = self.review_service.get_review(case.id)
            if not review:
                continue

            for decision in review.get("decisions", []):
                rid = decision.get("reviewer_id")
                if not rid:
                    continue

                if rid not in reviewer_stats:
                    reviewer_stats[rid] = {
                        "total_reviews": 0,
                        "accepted": 0,
                        "rejected": 0,
                        "escalated": 0,
                        "confidences": [],
                        "override_count": 0,
                    }

                stats = reviewer_stats[rid]
                stats["total_reviews"] += 1
                outcome = decision.get("outcome", "")
                if outcome == "accept":
                    stats["accepted"] += 1
                elif outcome == "reject":
                    stats["rejected"] += 1
                elif outcome == "escalate":
                    stats["escalated"] += 1

                conf = decision.get("confidence")
                if conf is not None:
                    stats["confidences"].append(conf)

        results = []
        for rid, stats in reviewer_stats.items():
            confs = stats["confidences"]
            results.append(
                ReviewerKpiBreakdown(
                    reviewer_id=rid,
                    total_reviews=stats["total_reviews"],
                    accepted=stats["accepted"],
                    rejected=stats["rejected"],
                    escalated=stats["escalated"],
                    avg_confidence=sum(confs) / len(confs) if confs else 0.0,
                    override_count=stats["override_count"],
                    agreement_rate=stats["accepted"] / stats["total_reviews"]
                    if stats["total_reviews"] > 0
                    else 0.0,
                )
            )

        return results
