"""Margin diagnosis workflow -- analyzes billing data for margin leakage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarginDiagnosisResult:
    """Result of a margin diagnosis workflow run."""
    case_id: str
    billing_record_id: str
    verdict: str = "healthy"
    leakage_amount: float | None = None
    leakage_reasons: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    status: str = "completed"


class MarginDiagnosisWorkflow:
    """Orchestrates the margin diagnosis workflow.

    Steps:
    1. Load billing data and contract terms
    2. Run billability rules
    3. Run leakage detection
    4. Generate recommendations
    5. Record audit trail
    """

    def __init__(
        self,
        billability_engine: Any = None,
        leakage_engine: Any = None,
        validator: Any = None,
        audit_logger: Any = None,
    ) -> None:
        self.billability_engine = billability_engine
        self.leakage_engine = leakage_engine
        self.validator = validator
        self.audit_logger = audit_logger

    async def run(
        self,
        case_id: str,
        billing_record_id: str,
        contract: Any = None,
        work_history: list[Any] | None = None,
        tenant_id: str = "",
        options: dict[str, Any] | None = None,
    ) -> MarginDiagnosisResult:
        """Execute the margin diagnosis workflow."""
        verdict = "healthy"
        leakage_amount: float | None = None
        leakage_reasons: list[str] = []
        recommendations: list[str] = []

        # Run leakage detection
        if self.leakage_engine and contract and work_history:
            triggers = self.leakage_engine.evaluate(contract, work_history)
            if triggers:
                leakage_amount = sum(t.estimated_impact for t in triggers)
                leakage_reasons = [t.description for t in triggers]
                if leakage_amount and leakage_amount > 50000:
                    verdict = "critical"
                elif leakage_amount and leakage_amount > 5000:
                    verdict = "leaking"
                elif leakage_amount and leakage_amount > 0:
                    verdict = "at_risk"
                recommendations = [
                    "Review identified leakage triggers",
                    "Align billing rates with contract terms",
                ]

        if self.audit_logger:
            try:
                await self.audit_logger.log(
                    case_id=case_id,
                    event_type="margin.diagnosed",
                    detail={
                        "billing_record_id": billing_record_id,
                        "verdict": verdict,
                        "leakage_amount": leakage_amount,
                    },
                )
            except Exception:
                pass

        return MarginDiagnosisResult(
            case_id=case_id,
            billing_record_id=billing_record_id,
            verdict=verdict,
            leakage_amount=leakage_amount,
            leakage_reasons=leakage_reasons,
            recommendations=recommendations,
        )
