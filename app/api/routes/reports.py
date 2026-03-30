"""Export and reporting API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.schemas.report import (
    BaselineComparisonResult,
    BaselineComparisonSummary,
    BaselineExpectation,
    CaseExportRequest,
    CaseExportResponse,
    PilotReportSummary,
)
from app.services.baseline import BaselineComparisonService
from app.services.export import ExportService

router = APIRouter(tags=["reports"])

_export_service = ExportService()
_baseline_service = BaselineComparisonService()

DEMO_USER = uuid.UUID("00000000-0000-0000-0000-000000000098")


@router.post(
    "/pilot-cases/{pilot_case_id}/export",
    response_model=CaseExportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def export_case(pilot_case_id: uuid.UUID, data: CaseExportRequest):
    case_data = {
        "id": pilot_case_id,
        "title": "Exported Case",
        "workflow_type": "unknown",
        "state": "exported",
    }
    return _export_service.export_case(pilot_case_id, DEMO_USER, case_data, data)


@router.get("/pilot-cases/{pilot_case_id}/report", response_model=CaseExportResponse)
async def get_case_report(pilot_case_id: uuid.UUID):
    exports = _export_service.get_exports(pilot_case_id)
    if not exports:
        raise HTTPException(status_code=404, detail="No export found for this case")
    return exports[-1]


@router.get("/pilot-reports/summary", response_model=PilotReportSummary)
async def get_pilot_report_summary():
    return _export_service.generate_pilot_report([])


@router.post(
    "/pilot-cases/{pilot_case_id}/baseline",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
async def store_baseline(pilot_case_id: uuid.UUID, data: BaselineExpectation):
    return _baseline_service.store_expectation(pilot_case_id, data)


@router.get("/pilot-cases/{pilot_case_id}/baseline", response_model=dict)
async def get_baseline(pilot_case_id: uuid.UUID):
    exp = _baseline_service.get_expectation(pilot_case_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="No baseline expectation found")
    return exp


@router.post(
    "/pilot-cases/{pilot_case_id}/baseline/compare",
    response_model=BaselineComparisonResult,
)
async def compare_baseline(
    pilot_case_id: uuid.UUID,
    platform_outcome: str | None = None,
    reviewer_outcome: str | None = None,
):
    try:
        return _baseline_service.compare(pilot_case_id, platform_outcome, reviewer_outcome)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/pilot-reports/overrides", response_model=dict)
async def get_override_report():
    return {
        "generated_at": None,
        "total_overrides": 0,
        "total_escalations": 0,
        "overrides_by_reason": {},
        "escalations_by_route": {},
        "override_rate": 0.0,
        "escalation_rate": 0.0,
    }


@router.get("/pilot-reports/baseline-comparison", response_model=BaselineComparisonSummary)
async def get_baseline_report():
    return _baseline_service.get_summary()
