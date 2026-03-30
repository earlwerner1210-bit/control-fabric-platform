"""Wave 2 reconciliation audit integration — extends fabric audit hooks."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.audit import FabricAuditEvent, FabricAuditEventType, FabricAuditHook
from app.core.reconciliation.domain_types import (
    ReconciliationCase,
    ReconciliationCaseId,
    ReconciliationHash,
    ReconciliationOutcome,
    ReconciliationOutcomeType,
    ReconciliationRun,
    ReconciliationRunId,
)
from app.core.types import ControlObjectId, PlaneType


class ReconciliationAuditIntegration:
    """Emits reconciliation-specific audit events through the fabric audit hook."""

    def __init__(self, audit_hook: FabricAuditHook) -> None:
        self._audit = audit_hook

    def reconciliation_run_started(
        self,
        run_id: ReconciliationRunId,
        tenant_id: uuid.UUID,
        planes: list[PlaneType],
        actor: str = "reconciliation-engine",
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.RECONCILIATION_RUN_STARTED,
                tenant_id=tenant_id,
                actor=actor,
                detail=f"Reconciliation run {run_id} started for planes: {[p.value for p in planes]}",
                metadata={
                    "run_id": str(run_id),
                    "planes": [p.value for p in planes],
                },
            )
        )

    def reconciliation_run_completed(
        self,
        run_id: ReconciliationRunId,
        tenant_id: uuid.UUID,
        run_hash: ReconciliationHash,
        outcome_count: int,
        case_count: int,
        actor: str = "reconciliation-engine",
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.RECONCILIATION_RUN_COMPLETED,
                tenant_id=tenant_id,
                actor=actor,
                detail=(
                    f"Reconciliation run {run_id} completed: "
                    f"{outcome_count} outcomes, {case_count} cases"
                ),
                metadata={
                    "run_id": str(run_id),
                    "run_hash": run_hash,
                    "outcome_count": outcome_count,
                    "case_count": case_count,
                },
            )
        )

    def reconciliation_candidate_generated(
        self,
        run_id: ReconciliationRunId,
        tenant_id: uuid.UUID,
        source_object_id: ControlObjectId,
        target_object_id: ControlObjectId,
        match_method: str,
        actor: str = "reconciliation-engine",
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.RECONCILIATION_CANDIDATE_GENERATED,
                tenant_id=tenant_id,
                actor=actor,
                source_object_id=source_object_id,
                target_object_id=target_object_id,
                detail=f"Candidate generated via {match_method}: {source_object_id} → {target_object_id}",
                metadata={
                    "run_id": str(run_id),
                    "match_method": match_method,
                },
            )
        )

    def reconciliation_case_created(
        self,
        case: ReconciliationCase,
        actor: str = "reconciliation-engine",
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.RECONCILIATION_CASE_CREATED,
                tenant_id=case.tenant_id,
                actor=actor,
                detail=(
                    f"Reconciliation case {case.id} created: "
                    f"{case.outcome.outcome_type.value} [{case.priority.value}]"
                ),
                metadata={
                    "case_id": str(case.id),
                    "run_id": str(case.run_id),
                    "outcome_type": case.outcome.outcome_type.value,
                    "priority": case.priority.value,
                },
            )
        )

    def reconciliation_case_classified(
        self,
        case_id: ReconciliationCaseId,
        tenant_id: uuid.UUID,
        outcome_type: ReconciliationOutcomeType,
        actor: str = "reconciliation-engine",
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.RECONCILIATION_CASE_CLASSIFIED,
                tenant_id=tenant_id,
                actor=actor,
                detail=f"Case {case_id} classified as {outcome_type.value}",
                metadata={
                    "case_id": str(case_id),
                    "outcome_type": outcome_type.value,
                },
            )
        )

    def reconciliation_duplicate_detected(
        self,
        run_id: ReconciliationRunId,
        tenant_id: uuid.UUID,
        source_object_id: ControlObjectId,
        duplicate_count: int,
        actor: str = "reconciliation-engine",
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.RECONCILIATION_DUPLICATE_DETECTED,
                tenant_id=tenant_id,
                actor=actor,
                control_object_id=source_object_id,
                detail=(
                    f"Duplicate candidates detected for {source_object_id}: "
                    f"{duplicate_count} matches"
                ),
                metadata={
                    "run_id": str(run_id),
                    "duplicate_count": duplicate_count,
                },
            )
        )

    def reconciliation_coverage_gap_detected(
        self,
        run_id: ReconciliationRunId,
        tenant_id: uuid.UUID,
        plane: PlaneType,
        expected_kind: str,
        missing_count: int,
        actor: str = "reconciliation-engine",
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.RECONCILIATION_COVERAGE_GAP_DETECTED,
                tenant_id=tenant_id,
                actor=actor,
                plane=plane,
                detail=(
                    f"Coverage gap in {plane.value}: missing {missing_count} "
                    f"'{expected_kind}' objects"
                ),
                metadata={
                    "run_id": str(run_id),
                    "expected_kind": expected_kind,
                    "missing_count": missing_count,
                },
            )
        )

    def reconciliation_insufficient_evidence(
        self,
        run_id: ReconciliationRunId,
        tenant_id: uuid.UUID,
        object_id: ControlObjectId,
        missing_types: list[str],
        actor: str = "reconciliation-engine",
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.RECONCILIATION_INSUFFICIENT_EVIDENCE,
                tenant_id=tenant_id,
                actor=actor,
                control_object_id=object_id,
                detail=f"Insufficient evidence for {object_id}: missing {missing_types}",
                metadata={
                    "run_id": str(run_id),
                    "missing_types": missing_types,
                },
            )
        )

    def reconciliation_outcome_hashed(
        self,
        run_id: ReconciliationRunId,
        tenant_id: uuid.UUID,
        outcome_hash: ReconciliationHash,
        outcome_type: ReconciliationOutcomeType,
        actor: str = "reconciliation-engine",
    ) -> None:
        self._audit.emit(
            FabricAuditEvent(
                event_type=FabricAuditEventType.RECONCILIATION_OUTCOME_HASHED,
                tenant_id=tenant_id,
                actor=actor,
                detail=f"Outcome hashed: {outcome_type.value} → {outcome_hash[:16]}...",
                metadata={
                    "run_id": str(run_id),
                    "outcome_hash": outcome_hash,
                    "outcome_type": outcome_type.value,
                },
            )
        )
