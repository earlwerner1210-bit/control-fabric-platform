"""Reconciliation engine — cross-plane mismatch detection and scoring."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.control_link import ControlLink
from app.core.control_object import ControlObject
from app.core.graph.service import GraphService
from app.core.reconciliation.rules import DEFAULT_RULES, ReconciliationRule
from app.core.reconciliation.scoring import score_mismatches
from app.core.reconciliation.types import (
    EvidenceBundle,
    Mismatch,
    ReconciliationMode,
    ReconciliationResult,
    ReconciliationStatus,
)
from app.core.registry import FabricRegistry
from app.core.types import (
    AuditContext,
    ControlLinkType,
    ControlObjectId,
    ControlState,
    PlaneType,
)


class ReconciliationEngine:
    """Cross-plane reconciliation: deterministic mismatch detection, scoring, evidence bundles."""

    def __init__(
        self,
        graph_service: GraphService,
        registry: FabricRegistry | None = None,
        rules: list[ReconciliationRule] | None = None,
    ) -> None:
        self._graph = graph_service
        self._registry = registry or FabricRegistry()
        self._rules: list[ReconciliationRule] = rules if rules is not None else list(DEFAULT_RULES)

    def add_rule(self, rule: ReconciliationRule) -> None:
        self._rules.append(rule)

    def reconcile_pair(
        self,
        source: ControlObject,
        target: ControlObject,
        rules: list[ReconciliationRule] | None = None,
    ) -> list[Mismatch]:
        """Run reconciliation rules against a source/target pair."""
        active_rules = rules if rules is not None else self._rules
        mismatches: list[Mismatch] = []
        for rule in active_rules:
            mismatches.extend(rule.evaluate(source, target))
        return mismatches

    def reconcile_cross_plane(
        self,
        tenant_id: uuid.UUID,
        source_plane: PlaneType,
        target_plane: PlaneType,
        domain: str,
    ) -> ReconciliationResult:
        """Run full cross-plane reconciliation between two planes for a domain."""
        source_objects = self._graph.list_objects(tenant_id, plane=source_plane, domain=domain)
        target_objects = self._graph.list_objects(tenant_id, plane=target_plane, domain=domain)

        all_mismatches: list[Mismatch] = []
        source_ids: list[ControlObjectId] = []
        target_ids: list[ControlObjectId] = []

        # Find cross-plane linked pairs
        pairs = self._find_cross_plane_pairs(source_objects, target_objects, tenant_id)

        for src, tgt in pairs:
            mismatches = self.reconcile_pair(src, tgt)
            all_mismatches.extend(mismatches)
            if src.id not in source_ids:
                source_ids.append(src.id)
            if tgt.id not in target_ids:
                target_ids.append(tgt.id)

        score = score_mismatches(all_mismatches)

        evidence_bundle = EvidenceBundle(
            mismatches=all_mismatches,
            source_objects=source_ids,
            target_objects=target_ids,
            summary=(
                f"Reconciliation of {source_plane.value}↔{target_plane.value} "
                f"in domain '{domain}': {len(all_mismatches)} mismatches found"
            ),
        )

        result = ReconciliationResult(
            tenant_id=tenant_id,
            run_at=datetime.now(UTC),
            status=ReconciliationStatus.COMPLETED,
            mode=ReconciliationMode.DETERMINISTIC,
            source_plane=source_plane,
            target_plane=target_plane,
            domain=domain,
            evidence_bundle=evidence_bundle,
            score=score,
        )
        result.compute_hash()

        # Mark reconciled objects
        now = datetime.now(UTC)
        for src_obj in source_objects:
            if src_obj.state == ControlState.FROZEN:
                src_obj.mark_reconciled(
                    AuditContext(
                        actor="reconciliation_engine",
                        action="reconciled",
                        timestamp=now,
                    )
                )
                self._graph.repository.store_object(src_obj)

        return result

    def _find_cross_plane_pairs(
        self,
        source_objects: list[ControlObject],
        target_objects: list[ControlObject],
        tenant_id: uuid.UUID,
    ) -> list[tuple[ControlObject, ControlObject]]:
        """Find object pairs linked across planes."""
        pairs: list[tuple[ControlObject, ControlObject]] = []
        source_map = {obj.id: obj for obj in source_objects}
        target_map = {obj.id: obj for obj in target_objects}

        all_links = self._graph.repository.get_all_links(tenant_id)
        for link in all_links:
            if not link.is_cross_plane:
                continue
            src = source_map.get(link.source_id)
            tgt = target_map.get(link.target_id)
            if src and tgt:
                pairs.append((src, tgt))
            # Also check reverse
            src_r = source_map.get(link.target_id)
            tgt_r = target_map.get(link.source_id)
            if src_r and tgt_r:
                pairs.append((src_r, tgt_r))

        # Also pair by correlation keys
        if not pairs:
            for src in source_objects:
                for key, val in src.correlation_keys.items():
                    for tgt in target_objects:
                        if tgt.correlation_keys.get(key) == val:
                            pairs.append((src, tgt))

        return pairs
