"""Work order readiness workflow -- checks if a work order is ready for dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkOrderReadinessResult:
    """Result of a work order readiness check."""
    case_id: str
    work_order_id: str
    verdict: str = "ready"
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    status: str = "completed"


class WorkOrderReadinessWorkflow:
    """Orchestrates the work order readiness workflow.

    Steps:
    1. Load work order data
    2. Run readiness rules (skills, permits, materials, schedule)
    3. Run validation
    4. Record audit trail
    """

    def __init__(
        self,
        readiness_engine: Any = None,
        validator: Any = None,
        audit_logger: Any = None,
    ) -> None:
        self.readiness_engine = readiness_engine
        self.validator = validator
        self.audit_logger = audit_logger

    async def run(
        self,
        case_id: str,
        work_order: dict[str, Any],
        tenant_id: str,
        options: dict[str, Any] | None = None,
    ) -> WorkOrderReadinessResult:
        """Execute the readiness check workflow."""
        work_order_id = work_order.get("work_order_id", "unknown")
        blockers: list[str] = []
        warnings: list[str] = []
        matched_skills: list[str] = []
        missing_skills: list[str] = []
        verdict = "ready"

        if self.readiness_engine:
            result = self.readiness_engine.evaluate(work_order)
            verdict = result.verdict
            blockers = result.blockers
            warnings = result.warnings
            matched_skills = result.matched_skills
            missing_skills = result.missing_skills

        if self.validator:
            try:
                self.validator.validate({
                    "case_id": case_id,
                    "work_order_id": work_order_id,
                    "verdict": verdict,
                })
            except Exception:
                pass

        if self.audit_logger:
            try:
                await self.audit_logger.log(
                    case_id=case_id,
                    event_type="work_order.readiness_checked",
                    detail={"work_order_id": work_order_id, "verdict": verdict},
                )
            except Exception:
                pass

        return WorkOrderReadinessResult(
            case_id=case_id,
            work_order_id=work_order_id,
            verdict=verdict,
            blockers=blockers,
            warnings=warnings,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
        )
