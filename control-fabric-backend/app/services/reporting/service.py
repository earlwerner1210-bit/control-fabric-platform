"""Reporting service -- generate structured reports from workflow data."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.services.audit.service import AuditService, audit_service

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class _CaseStore:
    """In-memory case store stub (production reads from DB)."""

    _cases: dict[UUID, dict[str, Any]] = {}

    @classmethod
    def get(cls, case_id: UUID) -> dict[str, Any] | None:
        return cls._cases.get(case_id)

    @classmethod
    def put(cls, case_id: UUID, data: dict[str, Any]) -> None:
        cls._cases[case_id] = data


class ReportingService:
    """Generates structured reports for individual cases and management summaries."""

    def __init__(self, audit_svc: AuditService | None = None) -> None:
        self._audit = audit_svc or audit_service

    def generate_case_report(self, case_id: UUID) -> dict[str, Any]:
        """Build a full report for a single workflow case.

        Combines case metadata, audit timeline, and output payload into a
        structured report dict suitable for rendering or export.
        """
        case = _CaseStore.get(case_id)
        timeline = self._audit.get_timeline(case_id)

        report: dict[str, Any] = {
            "report_id": str(uuid4()),
            "case_id": str(case_id),
            "generated_at": _now().isoformat(),
            "case_metadata": {},
            "timeline_event_count": len(timeline),
            "timeline": [],
            "output_summary": {},
        }

        if case:
            report["case_metadata"] = {
                "workflow_type": case.get("workflow_type"),
                "status": case.get("status"),
                "verdict": case.get("verdict"),
                "created_at": str(case.get("created_at", "")),
                "updated_at": str(case.get("updated_at", "")),
            }
            report["output_summary"] = case.get("output_payload", {})

        report["timeline"] = [
            {
                "event_type": evt.get("event_type"),
                "resource_type": evt.get("resource_type"),
                "created_at": str(evt.get("created_at", "")),
                "payload_keys": list(evt.get("payload", {}).keys()),
            }
            for evt in timeline
        ]

        logger.info(
            "reporting.case_report: case=%s events=%d",
            case_id,
            len(timeline),
        )
        return report

    def generate_management_summary(
        self,
        tenant_id: UUID,
        date_range: tuple[datetime, datetime] | None = None,
    ) -> dict[str, Any]:
        """Produce an aggregated management summary across all cases for a tenant.

        In the stub implementation this returns skeleton metrics; the production
        version queries the database for real aggregates.
        """
        start = date_range[0] if date_range else datetime(2020, 1, 1, tzinfo=UTC)
        end = date_range[1] if date_range else _now()

        # Stub aggregates
        summary: dict[str, Any] = {
            "report_id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "generated_at": _now().isoformat(),
            "period": {
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
            "totals": {
                "cases_created": 0,
                "cases_completed": 0,
                "cases_failed": 0,
                "documents_ingested": 0,
                "control_objects_created": 0,
                "validation_pass_rate": None,
            },
            "margin_overview": {
                "total_billed": 0.0,
                "total_unbacked": 0.0,
                "leakage_count": 0,
                "penalty_exposure_count": 0,
            },
            "model_usage": {
                "total_inference_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            },
        }

        logger.info(
            "reporting.management_summary: tenant=%s period=%s..%s",
            tenant_id,
            start.date(),
            end.date(),
        )
        return summary


# Singleton
reporting_service = ReportingService()
