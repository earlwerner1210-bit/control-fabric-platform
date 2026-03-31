"""
Compliance reporting and analytics API.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, Query, Response

from app.core.auth.middleware import CurrentUser, get_current_user
from app.core.reporting.analytics import analytics_engine
from app.core.reporting.compliance_report import (
    CONTROL_FRAMEWORKS,
    compliance_report_generator,
)
from app.core.reporting.readiness_checker import readiness_checker

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/report/{tenant_id}")
def get_compliance_report(
    tenant_id: str,
    period_days: int = Query(default=30, ge=7, le=365),
    frameworks: str = Query(default=""),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """
    Generate a governance posture report for a tenant.
    Covers NIS2, Ofcom, SOC2, and ISO 27001 control mapping.
    """
    framework_list = [f.strip() for f in frameworks.split(",") if f.strip()] or None
    report = compliance_report_generator.generate(
        tenant_id=tenant_id,
        period_days=period_days,
        frameworks=framework_list,
    )
    result = asdict(report)
    result["generated_at"] = report.generated_at
    result["report_hash"] = report.report_hash
    return result


@router.get("/report/{tenant_id}/export")
def export_compliance_report(
    tenant_id: str,
    period_days: int = Query(default=30),
    format: str = Query(default="csv"),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Download compliance report as CSV or JSON."""
    report = compliance_report_generator.generate(tenant_id=tenant_id, period_days=period_days)
    if format == "json":
        content = json.dumps(asdict(report), indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="compliance-report-{tenant_id}.json"'
            },
        )
    rows = compliance_report_generator.to_csv_rows(report)
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="compliance-report-{tenant_id}.csv"'
        },
    )


@router.get("/coverage")
def get_control_frameworks() -> dict:
    """List all supported compliance frameworks and their controls."""
    return {
        "frameworks": [
            {
                "name": name,
                "control_count": len(controls),
                "controls": [
                    {
                        "control_id": c["control_id"],
                        "control": c["control"],
                        "article": c["article"],
                    }
                    for c in controls
                ],
            }
            for name, controls in CONTROL_FRAMEWORKS.items()
        ]
    }


@router.get("/analytics/{tenant_id}")
def get_analytics(
    tenant_id: str,
    period_days: int = Query(default=30),
    granularity: str = Query(default="weekly"),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Time-series trend data for the governance dashboard."""
    return analytics_engine.get_trends(
        tenant_id=tenant_id,
        period_days=period_days,
        granularity=granularity,
    )


@router.get("/analytics/{tenant_id}/performance")
def get_performance(
    tenant_id: str,
    period_days: int = Query(default=30),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Team and service performance analytics."""
    return analytics_engine.get_performance(tenant_id, period_days)


@router.get("/readiness")
def get_readiness() -> dict:
    """Production readiness check — run before every demo and deployment."""
    report = readiness_checker.check()
    return {
        "passed": report.passed,
        "score": report.score,
        "grade": report.grade,
        "ready_for": report.ready_for,
        "blocking_failures": report.blocking_failures,
        "warnings": report.warnings,
        "checks": [asdict(c) for c in report.checks],
        "generated_at": report.generated_at,
    }


@router.get("/packs/example")
def get_example_pack() -> dict:
    """Return an example pack definition for enterprise customers."""
    from app.core.pack_authoring.sdk import build_example_telecom_pack

    pack = build_example_telecom_pack()
    return {
        "example": pack.to_dict(),
        "instructions": {
            "step_1": "Copy this definition and customise rule_id, description, and planes",
            "step_2": "POST /packs/install with your customised JSON to load the pack",
            "step_3": "GET /pack-ecosystem/test/{pack_id} to validate your pack",
            "step_4": "GET /pack-ecosystem/compatibility to check for conflicts with existing packs",
        },
        "python_sdk": (
            "from app.core.pack_authoring.sdk import PackBuilder\n"
            "pack = PackBuilder('my-pack-v1')\\\n"
            "    .name('My Custom Pack')\\\n"
            "    .description('Company-specific governance rules')\\\n"
            "    .domain('telecom')\\\n"
            "    .add_rule(rule_id='RULE-001', description='...', "
            "source_plane='operations', target_plane='compliance')\\\n"
            "    .build()\n"
            "domain_pack = pack.to_domain_pack()  # Convert and load"
        ),
    }
