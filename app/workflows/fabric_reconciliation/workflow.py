"""Fabric Reconciliation Workflow — Temporal-style orchestration for cross-plane reconciliation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class FabricReconciliationInput:
    tenant_id: str
    scope_planes: list[str] = field(default_factory=list)
    scope_domains: list[str] = field(default_factory=list)
    include_retired: bool = False
    auto_resolve_info: bool = True
    escalate_critical: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FabricReconciliationOutput:
    run_id: str
    status: str
    total_objects_scanned: int = 0
    total_conflicts: int = 0
    auto_resolved: int = 0
    escalated: int = 0
    unresolved: int = 0
    conflicts_by_type: dict[str, int] = field(default_factory=dict)
    conflicts_by_severity: dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: str | None = None


class FabricReconciliationActivities:
    """Activity implementations for the reconciliation workflow."""

    def build_fabric_snapshot(
        self,
        tenant_id: str,
        scope_planes: list[str],
        scope_domains: list[str],
    ) -> dict[str, Any]:
        return {
            "snapshot_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "scope_planes": scope_planes,
            "scope_domains": scope_domains,
            "status": "ready",
            "object_count": 0,
        }

    def run_contradiction_check(
        self,
        tenant_id: str,
        snapshot_id: str,
    ) -> list[dict[str, Any]]:
        return []

    def run_dependency_check(
        self,
        tenant_id: str,
        snapshot_id: str,
    ) -> list[dict[str, Any]]:
        return []

    def run_confidence_divergence_check(
        self,
        tenant_id: str,
        snapshot_id: str,
    ) -> list[dict[str, Any]]:
        return []

    def run_authorization_gap_check(
        self,
        tenant_id: str,
        snapshot_id: str,
    ) -> list[dict[str, Any]]:
        return []

    def run_stale_reference_check(
        self,
        tenant_id: str,
        snapshot_id: str,
    ) -> list[dict[str, Any]]:
        return []

    def run_boundary_violation_check(
        self,
        tenant_id: str,
        snapshot_id: str,
    ) -> list[dict[str, Any]]:
        return []

    def auto_resolve_conflicts(
        self,
        conflicts: list[dict[str, Any]],
        auto_resolve_info: bool,
    ) -> dict[str, Any]:
        auto_resolved = 0
        if auto_resolve_info:
            for c in conflicts:
                if c.get("severity") == "info":
                    c["resolution"] = "auto_resolved"
                    auto_resolved += 1
        return {"auto_resolved": auto_resolved, "conflicts": conflicts}

    def escalate_critical_conflicts(
        self,
        conflicts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        escalated = 0
        for c in conflicts:
            if (
                c.get("severity") == "critical"
                and c.get("resolution", "unresolved") == "unresolved"
            ):
                c["resolution"] = "escalated"
                escalated += 1
        return {"escalated": escalated, "conflicts": conflicts}

    def record_reconciliation_run(
        self,
        tenant_id: str,
        run_id: str,
        conflicts: list[dict[str, Any]],
        total_objects: int,
        duration_ms: float,
    ) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "recorded": True,
            "total_conflicts": len(conflicts),
        }


class FabricReconciliationWorkflow:
    """Orchestrates cross-plane reconciliation as a multi-step workflow."""

    def __init__(self, activities: FabricReconciliationActivities) -> None:
        self._activities = activities

    def run(self, input: FabricReconciliationInput) -> FabricReconciliationOutput:
        start = datetime.now(UTC)
        run_id = str(uuid.uuid4())
        all_conflicts: list[dict[str, Any]] = []

        try:
            # Step 1: Build snapshot
            snapshot = self._activities.build_fabric_snapshot(
                tenant_id=input.tenant_id,
                scope_planes=input.scope_planes,
                scope_domains=input.scope_domains,
            )
            snapshot_id = snapshot["snapshot_id"]

            # Step 2: Run all conflict checks
            contradictions = self._activities.run_contradiction_check(input.tenant_id, snapshot_id)
            all_conflicts.extend(contradictions)

            dependencies = self._activities.run_dependency_check(input.tenant_id, snapshot_id)
            all_conflicts.extend(dependencies)

            confidence = self._activities.run_confidence_divergence_check(
                input.tenant_id, snapshot_id
            )
            all_conflicts.extend(confidence)

            auth_gaps = self._activities.run_authorization_gap_check(input.tenant_id, snapshot_id)
            all_conflicts.extend(auth_gaps)

            stale = self._activities.run_stale_reference_check(input.tenant_id, snapshot_id)
            all_conflicts.extend(stale)

            boundary = self._activities.run_boundary_violation_check(input.tenant_id, snapshot_id)
            all_conflicts.extend(boundary)

            # Step 3: Auto-resolve info-level conflicts
            auto_result = self._activities.auto_resolve_conflicts(
                all_conflicts, input.auto_resolve_info
            )
            all_conflicts = auto_result["conflicts"]
            auto_resolved = auto_result["auto_resolved"]

            # Step 4: Escalate critical conflicts
            escalated = 0
            if input.escalate_critical:
                esc_result = self._activities.escalate_critical_conflicts(all_conflicts)
                all_conflicts = esc_result["conflicts"]
                escalated = esc_result["escalated"]

            end = datetime.now(UTC)
            duration_ms = (end - start).total_seconds() * 1000

            # Step 5: Record run
            self._activities.record_reconciliation_run(
                tenant_id=input.tenant_id,
                run_id=run_id,
                conflicts=all_conflicts,
                total_objects=snapshot.get("object_count", 0),
                duration_ms=duration_ms,
            )

            by_type: dict[str, int] = {}
            by_severity: dict[str, int] = {}
            unresolved = 0
            for c in all_conflicts:
                ct = c.get("conflict_type", "unknown")
                by_type[ct] = by_type.get(ct, 0) + 1
                cs = c.get("severity", "unknown")
                by_severity[cs] = by_severity.get(cs, 0) + 1
                if c.get("resolution", "unresolved") == "unresolved":
                    unresolved += 1

            return FabricReconciliationOutput(
                run_id=run_id,
                status="completed",
                total_objects_scanned=snapshot.get("object_count", 0),
                total_conflicts=len(all_conflicts),
                auto_resolved=auto_resolved,
                escalated=escalated,
                unresolved=unresolved,
                conflicts_by_type=by_type,
                conflicts_by_severity=by_severity,
                duration_ms=duration_ms,
            )

        except Exception as e:
            return FabricReconciliationOutput(
                run_id=run_id,
                status="failed",
                error=str(e),
            )
