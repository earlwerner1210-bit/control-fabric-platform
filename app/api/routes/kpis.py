"""API routes for KPI and pilot metrics."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.kpi import (
    KpiMeasurementCreate,
    KpiMeasurementResponse,
    PilotKpiSummary,
    WorkflowKpiBreakdown,
)
from app.schemas.reporting import ReviewerKpiBreakdown

router = APIRouter(prefix="/api/v1", tags=["kpis"])

# In-memory storage for now
_measurements: dict[uuid.UUID, list[dict]] = {}
_all_case_data: list[dict] = []


@router.get(
    "/pilot-cases/{pilot_case_id}/kpis",
    response_model=list[KpiMeasurementResponse],
)
async def get_case_kpis(
    pilot_case_id: uuid.UUID,
) -> list[KpiMeasurementResponse]:
    entries = _measurements.get(pilot_case_id, [])
    return [KpiMeasurementResponse(**e) for e in entries]


@router.post(
    "/pilot-cases/{pilot_case_id}/kpis",
    response_model=KpiMeasurementResponse,
)
async def record_kpi(
    pilot_case_id: uuid.UUID,
    data: KpiMeasurementCreate,
) -> KpiMeasurementResponse:
    from datetime import UTC, datetime

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
    _measurements.setdefault(pilot_case_id, []).append(measurement)
    return KpiMeasurementResponse(**measurement)


@router.get(
    "/pilot-cases/kpis/summary",
    response_model=PilotKpiSummary,
)
async def get_kpi_summary() -> PilotKpiSummary:
    return PilotKpiSummary()


@router.get(
    "/pilot-cases/kpis/workflows",
    response_model=list[WorkflowKpiBreakdown],
)
async def get_workflow_kpis() -> list[WorkflowKpiBreakdown]:
    return []


@router.get(
    "/pilot-cases/kpis/reviewers",
    response_model=list[ReviewerKpiBreakdown],
)
async def get_reviewer_kpis() -> list[ReviewerKpiBreakdown]:
    return []
