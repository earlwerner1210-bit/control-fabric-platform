"""Reconciliation Engine — cross-plane conflict detection and resolution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.control_fabric import ControlLinkType, ControlPlane
from app.schemas.reconciliation import (
    ConflictResolution,
    ConflictResolutionRequest,
    ConflictSeverity,
    ConflictType,
    ReconciliationConflictResponse,
    ReconciliationRunRequest,
    ReconciliationRunResponse,
    ReconciliationSummary,
)
from app.services.control_fabric.service import ControlFabricService


class ReconciliationEngine:
    """Detects cross-plane conflicts and inconsistencies in the control fabric."""

    def __init__(self, fabric_service: ControlFabricService) -> None:
        self._fabric = fabric_service
        self._runs: dict[uuid.UUID, dict[str, Any]] = {}
        self._conflicts: dict[uuid.UUID, dict[str, Any]] = {}

    def run_reconciliation(
        self,
        request: ReconciliationRunRequest,
    ) -> ReconciliationRunResponse:
        start = datetime.now(UTC)
        run_id = uuid.uuid4()

        objects, total = self._fabric.query_objects(request.tenant_id)

        if request.scope_planes:
            objects = [o for o in objects if o.plane in request.scope_planes]
        if request.scope_domains:
            objects = [o for o in objects if o.domain in request.scope_domains]
        if not request.include_retired:
            objects = [o for o in objects if o.status.value != "retired"]

        conflicts: list[dict[str, Any]] = []
        obj_map = {o.id: o for o in objects}

        # 1. Contradiction detection
        if not request.conflict_types or ConflictType.CONTRADICTION in request.conflict_types:
            contradictions = self._fabric.get_contradictions(request.tenant_id)
            for link in contradictions:
                src = obj_map.get(link.source_id)
                tgt = obj_map.get(link.target_id)
                if src and tgt:
                    conflicts.append(
                        self._make_conflict(
                            run_id=run_id,
                            conflict_type=ConflictType.CONTRADICTION,
                            severity=ConflictSeverity.ERROR,
                            source_object_id=link.source_id,
                            target_object_id=link.target_id,
                            source_plane=src.plane,
                            target_plane=tgt.plane,
                            description=(
                                f"Contradiction between {src.label} ({src.plane.value}) "
                                f"and {tgt.label} ({tgt.plane.value})"
                            ),
                        )
                    )

        # 2. Missing dependency detection
        if not request.conflict_types or ConflictType.MISSING_DEPENDENCY in request.conflict_types:
            for obj in objects:
                deps = self._fabric.get_links_for_object(obj.id, direction="outgoing")
                for link in deps:
                    if link.link_type == ControlLinkType.DEPENDS_ON:
                        if link.target_id not in obj_map:
                            conflicts.append(
                                self._make_conflict(
                                    run_id=run_id,
                                    conflict_type=ConflictType.MISSING_DEPENDENCY,
                                    severity=ConflictSeverity.WARNING,
                                    source_object_id=obj.id,
                                    target_object_id=link.target_id,
                                    source_plane=obj.plane,
                                    target_plane=None,
                                    description=(
                                        f"{obj.label} depends on missing object {link.target_id}"
                                    ),
                                )
                            )

        # 3. Confidence divergence detection
        if (
            not request.conflict_types
            or ConflictType.CONFIDENCE_DIVERGENCE in request.conflict_types
        ):
            for obj in objects:
                links = self._fabric.get_links_for_object(obj.id, direction="outgoing")
                for link in links:
                    if link.link_type in (
                        ControlLinkType.SATISFIES,
                        ControlLinkType.DEPENDS_ON,
                    ):
                        target = obj_map.get(link.target_id)
                        if target and abs(obj.confidence - target.confidence) > 0.3:
                            conflicts.append(
                                self._make_conflict(
                                    run_id=run_id,
                                    conflict_type=ConflictType.CONFIDENCE_DIVERGENCE,
                                    severity=ConflictSeverity.INFO,
                                    source_object_id=obj.id,
                                    target_object_id=target.id,
                                    source_plane=obj.plane,
                                    target_plane=target.plane,
                                    description=(
                                        f"Confidence divergence: {obj.label} ({obj.confidence:.2f}) "
                                        f"vs {target.label} ({target.confidence:.2f})"
                                    ),
                                )
                            )

        # 4. Domain boundary violation
        if (
            not request.conflict_types
            or ConflictType.DOMAIN_BOUNDARY_VIOLATION in request.conflict_types
        ):
            for obj in objects:
                links = self._fabric.get_links_for_object(obj.id, direction="outgoing")
                for link in links:
                    if link.link_type == ControlLinkType.AUTHORIZES:
                        target = obj_map.get(link.target_id)
                        if target and obj.domain != target.domain:
                            conflicts.append(
                                self._make_conflict(
                                    run_id=run_id,
                                    conflict_type=ConflictType.DOMAIN_BOUNDARY_VIOLATION,
                                    severity=ConflictSeverity.WARNING,
                                    source_object_id=obj.id,
                                    target_object_id=target.id,
                                    source_plane=obj.plane,
                                    target_plane=target.plane,
                                    description=(
                                        f"Cross-domain authorization: {obj.label} ({obj.domain}) "
                                        f"authorizes {target.label} ({target.domain})"
                                    ),
                                )
                            )

        # 5. Authorization gap detection
        if not request.conflict_types or ConflictType.AUTHORIZATION_GAP in request.conflict_types:
            for obj in objects:
                if obj.control_type in ("billing_adjustment", "dispatch_order"):
                    incoming = self._fabric.get_links_for_object(obj.id, direction="incoming")
                    has_auth = any(l.link_type == ControlLinkType.AUTHORIZES for l in incoming)
                    if not has_auth:
                        conflicts.append(
                            self._make_conflict(
                                run_id=run_id,
                                conflict_type=ConflictType.AUTHORIZATION_GAP,
                                severity=ConflictSeverity.CRITICAL,
                                source_object_id=obj.id,
                                target_object_id=None,
                                source_plane=obj.plane,
                                target_plane=None,
                                description=(
                                    f"{obj.label} ({obj.control_type}) has no authorization link"
                                ),
                            )
                        )

        # 6. Stale reference detection
        if not request.conflict_types or ConflictType.STALE_REFERENCE in request.conflict_types:
            for obj in objects:
                if obj.status.value == "superseded":
                    incoming = self._fabric.get_links_for_object(obj.id, direction="incoming")
                    for link in incoming:
                        src = obj_map.get(link.source_id)
                        if src and src.status.value == "active":
                            conflicts.append(
                                self._make_conflict(
                                    run_id=run_id,
                                    conflict_type=ConflictType.STALE_REFERENCE,
                                    severity=ConflictSeverity.WARNING,
                                    source_object_id=link.source_id,
                                    target_object_id=obj.id,
                                    source_plane=src.plane if src else obj.plane,
                                    target_plane=obj.plane,
                                    description=(
                                        f"Active object {src.label} references "
                                        f"superseded object {obj.label}"
                                    ),
                                )
                            )

        end = datetime.now(UTC)
        duration_ms = (end - start).total_seconds() * 1000

        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for c in conflicts:
            ct = c["conflict_type"].value
            by_type[ct] = by_type.get(ct, 0) + 1
            cs = c["severity"].value
            by_severity[cs] = by_severity.get(cs, 0) + 1

        run = {
            "id": run_id,
            "tenant_id": request.tenant_id,
            "status": "completed",
            "total_objects_scanned": len(objects),
            "total_conflicts": len(conflicts),
            "conflicts_by_type": by_type,
            "conflicts_by_severity": by_severity,
            "scope_planes": [
                p.value if hasattr(p, "value") else str(p) for p in request.scope_planes
            ],
            "scope_domains": request.scope_domains,
            "duration_ms": duration_ms,
            "metadata": request.metadata,
            "created_at": start,
        }
        self._runs[run_id] = run

        conflict_responses = []
        for c in conflicts:
            self._conflicts[c["id"]] = c
            conflict_responses.append(ReconciliationConflictResponse(**c))

        return ReconciliationRunResponse(
            **run,
            conflicts=conflict_responses,
        )

    def get_run(self, run_id: uuid.UUID) -> ReconciliationRunResponse | None:
        run = self._runs.get(run_id)
        if run is None:
            return None
        conflicts = [
            ReconciliationConflictResponse(**c)
            for c in self._conflicts.values()
            if c["run_id"] == run_id
        ]
        return ReconciliationRunResponse(**run, conflicts=conflicts)

    def resolve_conflict(
        self,
        conflict_id: uuid.UUID,
        request: ConflictResolutionRequest,
    ) -> ReconciliationConflictResponse | None:
        conflict = self._conflicts.get(conflict_id)
        if conflict is None:
            return None
        conflict["resolution"] = request.resolution
        conflict["resolution_detail"] = request.resolution_detail
        return ReconciliationConflictResponse(**conflict)

    def get_summary(self, tenant_id: uuid.UUID) -> ReconciliationSummary:
        runs = [r for r in self._runs.values() if r["tenant_id"] == tenant_id]
        all_conflicts = [
            c for c in self._conflicts.values() if c["run_id"] in {r["id"] for r in runs}
        ]

        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_plane_pair: dict[str, int] = {}
        unresolved = 0
        for c in all_conflicts:
            ct = c["conflict_type"].value
            by_type[ct] = by_type.get(ct, 0) + 1
            cs = c["severity"].value
            by_severity[cs] = by_severity.get(cs, 0) + 1
            if c["resolution"] == ConflictResolution.UNRESOLVED:
                unresolved += 1
            sp = (
                c["source_plane"].value
                if hasattr(c["source_plane"], "value")
                else str(c["source_plane"])
            )
            tp = c["target_plane"]
            if tp:
                tp_v = tp.value if hasattr(tp, "value") else str(tp)
                pair = f"{sp}->{tp_v}"
            else:
                pair = f"{sp}->none"
            by_plane_pair[pair] = by_plane_pair.get(pair, 0) + 1

        return ReconciliationSummary(
            total_runs=len(runs),
            total_conflicts=len(all_conflicts),
            unresolved_conflicts=unresolved,
            conflicts_by_type=by_type,
            conflicts_by_severity=by_severity,
            conflicts_by_plane_pair=by_plane_pair,
            avg_conflicts_per_run=len(all_conflicts) / len(runs) if runs else 0.0,
        )

    def _make_conflict(
        self,
        run_id: uuid.UUID,
        conflict_type: ConflictType,
        severity: ConflictSeverity,
        source_object_id: uuid.UUID,
        target_object_id: uuid.UUID | None,
        source_plane: ControlPlane,
        target_plane: ControlPlane | None,
        description: str,
    ) -> dict[str, Any]:
        return {
            "id": uuid.uuid4(),
            "run_id": run_id,
            "conflict_type": conflict_type,
            "severity": severity,
            "source_object_id": source_object_id,
            "target_object_id": target_object_id,
            "source_plane": source_plane,
            "target_plane": target_plane,
            "description": description,
            "resolution": ConflictResolution.UNRESOLVED,
            "resolution_detail": None,
            "metadata": {},
            "created_at": datetime.now(UTC),
        }
