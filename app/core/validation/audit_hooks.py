"""Wave 3 validation audit integration — typed audit events for validation chain."""

from __future__ import annotations

import uuid

from app.core.audit import FabricAuditEvent, FabricAuditEventType, FabricAuditHook
from app.core.validation.domain_types import (
    ValidationDecision,
    ValidationReportHash,
    ValidationRunId,
    W3ValidationStatus,
)


class ValidationAuditIntegration:
    """Emits typed audit events for Wave 3 validation chain operations."""

    def __init__(self, audit_hook: FabricAuditHook) -> None:
        self._audit = audit_hook

    def validation_run_started(
        self,
        run_id: ValidationRunId,
        tenant_id: uuid.UUID,
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.VALIDATION_RUN_STARTED,
                tenant_id=tenant_id,
                detail=f"Validation run {run_id} started",
                metadata={"run_id": str(run_id)},
            )
        )

    def validation_run_completed(
        self,
        run_id: ValidationRunId,
        tenant_id: uuid.UUID,
        status: W3ValidationStatus,
        decision: ValidationDecision,
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.VALIDATION_RUN_COMPLETED,
                tenant_id=tenant_id,
                detail=f"Validation run {run_id} completed: {status.value}, decision={decision.value}",
                metadata={
                    "run_id": str(run_id),
                    "status": status.value,
                    "decision": decision.value,
                },
            )
        )

    def validation_step_completed(
        self,
        run_id: ValidationRunId,
        tenant_id: uuid.UUID,
        rule_id: str,
        passed: bool,
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.VALIDATION_STEP_COMPLETED,
                tenant_id=tenant_id,
                detail=f"Validation step {rule_id}: {'passed' if passed else 'failed'}",
                metadata={
                    "run_id": str(run_id),
                    "rule_id": rule_id,
                    "passed": passed,
                },
            )
        )

    def validation_failed(
        self,
        run_id: ValidationRunId,
        tenant_id: uuid.UUID,
        failure_count: int,
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.VALIDATION_FAILED,
                tenant_id=tenant_id,
                detail=f"Validation run {run_id} has {failure_count} failures",
                metadata={
                    "run_id": str(run_id),
                    "failure_count": failure_count,
                },
            )
        )

    def validation_decision_recorded(
        self,
        run_id: ValidationRunId,
        tenant_id: uuid.UUID,
        decision: ValidationDecision,
        report_hash: ValidationReportHash,
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.VALIDATION_DECISION_RECORDED,
                tenant_id=tenant_id,
                detail=f"Validation decision: {decision.value} (hash={report_hash})",
                metadata={
                    "run_id": str(run_id),
                    "decision": decision.value,
                    "report_hash": str(report_hash),
                },
            )
        )

    def validation_report_hashed(
        self,
        run_id: ValidationRunId,
        tenant_id: uuid.UUID,
        report_hash: ValidationReportHash,
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.VALIDATION_REPORT_HASHED,
                tenant_id=tenant_id,
                detail=f"Validation report hashed: {report_hash}",
                metadata={
                    "run_id": str(run_id),
                    "report_hash": str(report_hash),
                },
            )
        )
