"""
Reconciliation Module - Top-level margin diagnosis reconciler that
orchestrates linking, conflict detection, evidence assembly, and
chain validation into a single coherent diagnosis bundle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain_packs.reconciliation.conflict_detector import (
    ConflictDetector,
    CrossPlaneConflict,
    LeakageTrigger,
)
from app.domain_packs.reconciliation.evidence import (
    EvidenceAssembler,
    EvidenceBundle,
    EvidenceChainValidator,
)
from app.domain_packs.reconciliation.linkers import (
    ContractWorkOrderLinker,
    CrossPlaneLink,
    WorkOrderIncidentLinker,
)

# ---------------------------------------------------------------------------
# Diagnosis bundle (output dataclass)
# ---------------------------------------------------------------------------


@dataclass
class MarginDiagnosisBundle:
    """Complete margin diagnosis result from the reconciliation process."""

    verdict: str = ""
    contract_wo_links: list[CrossPlaneLink] = field(default_factory=list)
    wo_incident_links: list[CrossPlaneLink] = field(default_factory=list)
    conflicts: list[CrossPlaneConflict] = field(default_factory=list)
    leakage_triggers: list[LeakageTrigger] = field(default_factory=list)
    evidence_bundle: EvidenceBundle | None = None
    chain_results: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reconciler
# ---------------------------------------------------------------------------


class MarginDiagnosisReconciler:
    """Orchestrates the full margin-assurance reconciliation pipeline.

    Steps:
    1. Link contracts to work orders
    2. Link work orders to incidents
    3. Detect cross-domain conflicts
    4. Detect margin leakage triggers
    5. Assemble evidence bundle
    6. Validate evidence chain completeness
    7. Build verdict
    8. Return MarginDiagnosisBundle
    """

    def __init__(self) -> None:
        self.contract_wo_linker = ContractWorkOrderLinker()
        self.wo_incident_linker = WorkOrderIncidentLinker()
        self.evidence_assembler = EvidenceAssembler()
        self.conflict_detector = ConflictDetector()
        self.chain_validator = EvidenceChainValidator()

    def reconcile(
        self,
        contract_objects: list[dict[str, Any]],
        work_orders: list[dict[str, Any]],
        incidents: list[dict[str, Any]] | None = None,
        sla_performance: dict[str, Any] | None = None,
    ) -> MarginDiagnosisBundle:
        """Run the full reconciliation pipeline and return a diagnosis bundle.

        Args:
            contract_objects: List of contract dicts (from contract-margin domain).
            work_orders: List of work order dicts (from utilities-field domain).
            incidents: Optional list of incident dicts (from telco-ops domain).
            sla_performance: Optional SLA performance data (reserved for future use).

        Returns:
            MarginDiagnosisBundle with all links, conflicts, leakage triggers,
            evidence, chain validation results, and an overall verdict.
        """
        incidents = incidents or []

        # -- Step 1: Link contracts to work orders ---------------------------
        all_contract_wo_links: list[CrossPlaneLink] = []
        for wo in work_orders:
            links = self.contract_wo_linker.link(contract_objects, wo)
            all_contract_wo_links.extend(links)

        # -- Step 2: Link work orders to incidents ---------------------------
        all_wo_incident_links: list[CrossPlaneLink] = []
        for wo in work_orders:
            links = self.wo_incident_linker.link(wo, incidents)
            all_wo_incident_links.extend(links)

        # -- Step 3: Detect cross-domain conflicts ---------------------------
        all_conflicts: list[CrossPlaneConflict] = []

        # Contract vs field conflicts
        for wo in work_orders:
            # Find contracts linked to this WO
            wo_id = str(wo.get("work_order_id", wo.get("id", "")))
            linked_contract_ids = {
                link.source_id
                for link in all_contract_wo_links
                if link.target_id == wo_id and link.source_domain == "contract"
            }
            for co in contract_objects:
                co_id = str(co.get("contract_id", co.get("id", "")))
                if co_id in linked_contract_ids:
                    conflicts = self.conflict_detector.detect_contract_field_conflict(co, wo)
                    all_conflicts.extend(conflicts)

        # Field vs telco conflicts
        for wo in work_orders:
            wo_id = str(wo.get("work_order_id", wo.get("id", "")))
            linked_incident_ids = {
                link.target_id
                for link in all_wo_incident_links
                if link.source_id == wo_id and link.target_domain == "telco"
            }
            for inc in incidents:
                inc_id = str(inc.get("incident_id", inc.get("id", "")))
                if inc_id in linked_incident_ids:
                    conflicts = self.conflict_detector.detect_field_service_conflict(wo, inc)
                    all_conflicts.extend(conflicts)

        # -- Step 4: Detect leakage triggers ---------------------------------
        leakage_triggers = self.conflict_detector.detect_margin_leakage(
            contract_objects,
            work_orders,
            incidents,
        )

        # -- Step 5: Assemble evidence bundle --------------------------------
        evidence_bundle = self.evidence_assembler.assemble_margin_evidence(
            contract_objects,
            work_orders,
            incidents,
        )

        # -- Step 6: Validate evidence chain ---------------------------------
        chain_results = self.chain_validator.validate_chain(evidence_bundle)

        # -- Step 7: Build verdict -------------------------------------------
        verdict = self._build_verdict(
            all_contract_wo_links,
            all_wo_incident_links,
            all_conflicts,
            leakage_triggers,
            chain_results,
        )

        # -- Step 8: Return bundle -------------------------------------------
        return MarginDiagnosisBundle(
            verdict=verdict,
            contract_wo_links=all_contract_wo_links,
            wo_incident_links=all_wo_incident_links,
            conflicts=all_conflicts,
            leakage_triggers=leakage_triggers,
            evidence_bundle=evidence_bundle,
            chain_results=chain_results,
        )

    # ------------------------------------------------------------------
    # Verdict builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_verdict(
        contract_wo_links: list[CrossPlaneLink],
        wo_incident_links: list[CrossPlaneLink],
        conflicts: list[CrossPlaneConflict],
        leakage_triggers: list[LeakageTrigger],
        chain_results: list[dict[str, Any]],
    ) -> str:
        """Determine an overall verdict based on reconciliation results.

        Verdict levels:
        - ``clean``: no issues found
        - ``minor_issues``: warnings or low-severity items only
        - ``attention_required``: medium severity conflicts or gaps
        - ``critical``: critical conflicts, leakage, or chain gaps
        """
        critical_count = 0
        high_count = 0
        medium_count = 0

        # Count conflict severities
        for c in conflicts:
            sev = c.severity.lower()
            if sev == "critical":
                critical_count += 1
            elif sev == "high":
                high_count += 1
            elif sev == "medium":
                medium_count += 1

        # Count leakage severities
        for lt in leakage_triggers:
            sev = lt.severity.lower()
            if sev == "critical":
                critical_count += 1
            elif sev == "high":
                high_count += 1
            elif sev == "medium":
                medium_count += 1

        # Count critical chain gaps
        for cr in chain_results:
            if not cr.get("present") and cr.get("severity") == "critical":
                critical_count += 1
            elif not cr.get("present") and cr.get("severity") == "high":
                high_count += 1

        # Check for unlinked work orders (no contract link found)
        if not contract_wo_links:
            high_count += 1

        # Determine verdict
        if critical_count > 0:
            return "critical"
        if high_count > 0:
            return "attention_required"
        if medium_count > 0:
            return "minor_issues"
        return "clean"
