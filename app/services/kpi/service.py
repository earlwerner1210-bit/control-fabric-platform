"""KPI and pilot metrics service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.kpi import (
    KpiMeasurementCreate,
    KpiMeasurementResponse,
    PilotKpiSummary,
    WorkflowKpiBreakdown,
)
from app.schemas.pilot_case import PilotCaseState


class KpiService:
    """Captures and aggregates pilot KPI measurements."""

    def __init__(self) -> None:
        self._measurements: dict[uuid.UUID, list[dict[str, Any]]] = {}

    def record_measurement(
        self,
        pilot_case_id: uuid.UUID,
        data: KpiMeasurementCreate,
    ) -> KpiMeasurementResponse:
        measurement = {
            "id": uuid.uuid4(),
            "pilot_case_id": pilot_case_id,
            "metric_name": data.metric_name,
            "metric_value": data.metric_value,
            "metric_unit": data.metric_unit,
            "dimension": data.dimension,
            "dimension_value": data.dimension_value,
            "metadata": data.metadata,
            "created_at": datetime.now(UTC),
        }
        self._measurements.setdefault(pilot_case_id, []).append(measurement)
        return KpiMeasurementResponse(**measurement)

    def get_case_measurements(
        self,
        pilot_case_id: uuid.UUID,
    ) -> list[KpiMeasurementResponse]:
        return [
            KpiMeasurementResponse(**m)
            for m in self._measurements.get(pilot_case_id, [])
        ]

    def compute_summary(
        self,
        cases: list[dict[str, Any]],
        comparisons: list[dict[str, Any]] | None = None,
        review_decisions: list[dict[str, Any]] | None = None,
    ) -> PilotKpiSummary:
        total = len(cases)
        if total == 0:
            return PilotKpiSummary()

        by_state: dict[str, int] = {}
        by_workflow: dict[str, int] = {}
        for c in cases:
            state = c.get("state", "unknown")
            state_str = state.value if isinstance(state, PilotCaseState) else str(state)
            by_state[state_str] = by_state.get(state_str, 0) + 1
            wt = c.get("workflow_type", "unknown")
            by_workflow[wt] = by_workflow.get(wt, 0) + 1

        approved = by_state.get("approved", 0) + by_state.get("exported", 0) + by_state.get("closed", 0)
        overridden = by_state.get("overridden", 0)
        escalated = by_state.get("escalated", 0)
        resolved = approved + overridden + escalated
        approval_rate = approved / resolved if resolved > 0 else 0.0
        override_rate = overridden / resolved if resolved > 0 else 0.0
        escalation_rate = escalated / resolved if resolved > 0 else 0.0

        exact_match = 0
        false_pos = 0
        false_neg = 0
        if comparisons:
            for comp in comparisons:
                mt = comp.get("match_type", "")
                mt_str = mt.value if hasattr(mt, "value") else str(mt)
                if mt_str == "exact_match":
                    exact_match += 1
                elif mt_str == "false_positive":
                    false_pos += 1
                elif mt_str == "false_negative":
                    false_neg += 1
            compared = len(comparisons)
            exact_match_rate = exact_match / compared if compared > 0 else 0.0
            fp_rate = false_pos / compared if compared > 0 else 0.0
            fn_rate = false_neg / compared if compared > 0 else 0.0
        else:
            exact_match_rate = 0.0
            fp_rate = 0.0
            fn_rate = 0.0

        avg_confidence = 0.0
        if review_decisions:
            confs = [d.get("confidence", 0.0) for d in review_decisions]
            avg_confidence = sum(confs) / len(confs) if confs else 0.0

        return PilotKpiSummary(
            total_cases=total,
            cases_by_state=by_state,
            cases_by_workflow_type=by_workflow,
            approval_rate=approval_rate,
            override_rate=override_rate,
            escalation_rate=escalation_rate,
            exact_match_rate=exact_match_rate,
            false_positive_rate=fp_rate,
            false_negative_rate=fn_rate,
            avg_reviewer_confidence=avg_confidence,
        )

    def compute_workflow_breakdown(
        self,
        cases: list[dict[str, Any]],
        comparisons: list[dict[str, Any]] | None = None,
    ) -> list[WorkflowKpiBreakdown]:
        by_workflow: dict[str, list[dict[str, Any]]] = {}
        for c in cases:
            wt = c.get("workflow_type", "unknown")
            by_workflow.setdefault(wt, []).append(c)

        comp_by_case: dict[str, dict[str, Any]] = {}
        if comparisons:
            for comp in comparisons:
                cid = str(comp.get("pilot_case_id", ""))
                comp_by_case[cid] = comp

        results = []
        for wt, wf_cases in by_workflow.items():
            total = len(wf_cases)
            approved = sum(1 for c in wf_cases if self._state_str(c) in ("approved", "exported", "closed"))
            overridden = sum(1 for c in wf_cases if self._state_str(c) == "overridden")
            escalated = sum(1 for c in wf_cases if self._state_str(c) == "escalated")
            rejected = sum(1 for c in wf_cases if self._state_str(c) == "closed" and c.get("_rejected"))

            fp = fn = em = 0
            for c in wf_cases:
                cid = str(c.get("id", ""))
                comp = comp_by_case.get(cid)
                if comp:
                    mt = comp.get("match_type", "")
                    mt_str = mt.value if hasattr(mt, "value") else str(mt)
                    if mt_str == "exact_match":
                        em += 1
                    elif mt_str == "false_positive":
                        fp += 1
                    elif mt_str == "false_negative":
                        fn += 1

            compared = sum(1 for c in wf_cases if str(c.get("id", "")) in comp_by_case)
            exact_rate = em / compared if compared > 0 else 0.0

            results.append(WorkflowKpiBreakdown(
                workflow_type=wt,
                total_cases=total,
                approved=approved,
                overridden=overridden,
                escalated=escalated,
                rejected=rejected,
                avg_confidence=0.0,
                avg_evidence_completeness=0.0,
                exact_match_rate=exact_rate,
                false_positive_count=fp,
                false_negative_count=fn,
            ))
        return results

    def _state_str(self, case: dict[str, Any]) -> str:
        state = case.get("state", "unknown")
        return state.value if isinstance(state, PilotCaseState) else str(state)
