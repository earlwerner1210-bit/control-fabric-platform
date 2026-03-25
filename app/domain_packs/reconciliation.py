"""Cross-pack reconciliation -- links and validates across commercial, field, and ops domains."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CrossPlaneLink:
    """A link between control objects in different domain planes."""

    source_domain: str
    target_domain: str
    source_object_id: uuid.UUID
    target_object_id: uuid.UUID
    link_type: str  # maps_to, requires, conflicts_with, triggers
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class CrossPlaneConflict:
    """A conflict detected between two domain planes."""

    conflict_type: str
    severity: str  # info, warning, error, critical
    description: str
    domain_a: str
    domain_b: str
    object_a_id: uuid.UUID | None = None
    object_b_id: uuid.UUID | None = None
    resolution_suggestion: str = ""


@dataclass
class EvidenceBundle:
    """A bundle of evidence gathered across domain planes."""

    bundle_type: str  # margin_evidence, readiness_evidence, ops_evidence
    contract_objects: list[dict] = field(default_factory=list)
    field_objects: list[dict] = field(default_factory=list)
    ops_objects: list[dict] = field(default_factory=list)
    cross_links: list[CrossPlaneLink] = field(default_factory=list)
    conflicts: list[CrossPlaneConflict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_uuid(value: Any) -> uuid.UUID:
    """Convert a value to UUID, generating one if the value is missing."""
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return uuid.uuid5(uuid.NAMESPACE_DNS, value)
    return uuid.uuid4()


def _normalize(text: str) -> str:
    """Lowercase and strip a string for fuzzy matching."""
    return text.lower().strip().replace("-", "_").replace(" ", "_")


def _text_overlap(a: str, b: str) -> float:
    """Return a 0..1 token-overlap score between two strings."""
    tokens_a = set(_normalize(a).split("_"))
    tokens_b = set(_normalize(b).split("_"))
    tokens_a.discard("")
    tokens_b.discard("")
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# ContractWorkOrderLinker
# ---------------------------------------------------------------------------


class ContractWorkOrderLinker:
    """Link contract control objects to work order control objects."""

    def link_contract_to_work_order(
        self,
        contract_objects: list[dict],
        work_order_objects: list[dict],
    ) -> list[CrossPlaneLink]:
        """Match contract objects to work order objects by activity, scope, and billing references.

        Matching strategies:
        - billable_events <-> work activities by activity name
        - obligations <-> dispatch_preconditions by scope
        - penalty_conditions <-> readiness_checks
        - rate_card entries <-> work order billing references
        """
        links: list[CrossPlaneLink] = []

        billable_events = [
            o for o in contract_objects
            if o.get("control_type") in ("billable_event", "rate_card")
        ]
        obligations = [
            o for o in contract_objects
            if o.get("control_type") == "obligation"
        ]
        penalties = [
            o for o in contract_objects
            if o.get("control_type") == "penalty_condition"
        ]
        rate_cards = [
            o for o in contract_objects
            if o.get("control_type") == "rate_card"
        ]

        for wo in work_order_objects:
            wo_id = _safe_uuid(wo.get("id", wo.get("work_order_id", "")))
            wo_activity = wo.get("activity", wo.get("description", ""))
            wo_scope = wo.get("scope", wo.get("description", ""))

            # 1) Match billable_events to work activities by activity name
            for be in billable_events:
                be_id = _safe_uuid(be.get("id", be.get("clause_id", "")))
                be_activity = be.get("activity", be.get("label", ""))
                overlap = _text_overlap(be_activity, wo_activity)
                if overlap > 0.2:
                    links.append(CrossPlaneLink(
                        source_domain="contract_margin",
                        target_domain="utilities_field",
                        source_object_id=be_id,
                        target_object_id=wo_id,
                        link_type="maps_to",
                        confidence=min(overlap * 1.5, 1.0),
                        metadata={
                            "contract_activity": be_activity,
                            "work_order_activity": wo_activity,
                        },
                    ))

            # 2) Match obligations to work order scope
            for ob in obligations:
                ob_id = _safe_uuid(ob.get("id", ob.get("clause_id", "")))
                ob_desc = ob.get("description", ob.get("text", ""))
                overlap = _text_overlap(ob_desc, wo_scope)
                if overlap > 0.15:
                    links.append(CrossPlaneLink(
                        source_domain="contract_margin",
                        target_domain="utilities_field",
                        source_object_id=ob_id,
                        target_object_id=wo_id,
                        link_type="requires",
                        confidence=min(overlap * 1.3, 1.0),
                        metadata={
                            "obligation": ob_desc[:100],
                            "work_order_scope": wo_scope[:100],
                        },
                    ))

            # 3) Match penalty_conditions to readiness_checks
            for pc in penalties:
                pc_id = _safe_uuid(pc.get("id", pc.get("clause_id", "")))
                pc_trigger = pc.get("trigger", pc.get("description", ""))
                # Penalty conditions link to work orders that touch the same scope
                overlap = _text_overlap(pc_trigger, wo_scope)
                if overlap > 0.1:
                    links.append(CrossPlaneLink(
                        source_domain="contract_margin",
                        target_domain="utilities_field",
                        source_object_id=pc_id,
                        target_object_id=wo_id,
                        link_type="conflicts_with",
                        confidence=min(overlap * 1.2, 1.0),
                        metadata={
                            "penalty_trigger": pc_trigger[:100],
                        },
                    ))

            # 4) Match rate_card entries to work order billing references
            wo_billing_ref = wo.get("billing_reference", wo.get("rate", ""))
            for rc in rate_cards:
                rc_id = _safe_uuid(rc.get("id", rc.get("clause_id", "")))
                rc_activity = rc.get("activity", rc.get("label", ""))
                if _normalize(rc_activity) == _normalize(wo_activity) or _text_overlap(rc_activity, wo_activity) > 0.3:
                    links.append(CrossPlaneLink(
                        source_domain="contract_margin",
                        target_domain="utilities_field",
                        source_object_id=rc_id,
                        target_object_id=wo_id,
                        link_type="maps_to",
                        confidence=0.9,
                        metadata={
                            "rate_card_activity": rc_activity,
                            "work_order_activity": wo_activity,
                            "billing_reference": str(wo_billing_ref),
                        },
                    ))

        return links

    def detect_commercial_field_conflicts(
        self,
        contract_objects: list[dict],
        work_order_objects: list[dict],
    ) -> list[CrossPlaneConflict]:
        """Detect conflicts between contract and field planes.

        Checks for:
        - Work performed but no matching billable event
        - Rate mismatch between contract and work order
        - Scope conflict: work order activity not in contract scope
        - Timeline conflict: work performed outside contract period
        """
        conflicts: list[CrossPlaneConflict] = []

        billable_activities = set()
        for co in contract_objects:
            if co.get("control_type") in ("billable_event", "rate_card"):
                activity = co.get("activity", co.get("label", ""))
                billable_activities.add(_normalize(activity))

        scope_descriptions = []
        for co in contract_objects:
            if co.get("control_type") in ("scope_boundary", "obligation"):
                scope_descriptions.append(
                    co.get("description", co.get("text", "")).lower()
                )

        contract_rates: dict[str, float] = {}
        for co in contract_objects:
            if co.get("control_type") == "rate_card":
                activity = _normalize(co.get("activity", co.get("label", "")))
                rate = co.get("rate", co.get("payload", {}).get("rate", 0))
                if isinstance(rate, (int, float)):
                    contract_rates[activity] = float(rate)

        contract_start = None
        contract_end = None
        for co in contract_objects:
            if co.get("control_type") == "contract_metadata":
                contract_start = co.get("effective_date", co.get("start_date"))
                contract_end = co.get("expiry_date", co.get("end_date"))

        for wo in work_order_objects:
            wo_id = _safe_uuid(wo.get("id", wo.get("work_order_id", "")))
            wo_activity = _normalize(wo.get("activity", wo.get("description", "")))
            wo_status = wo.get("status", "")

            # 1) Work performed but no matching billable event
            if wo_status in ("completed", "done", "finished"):
                matched = any(
                    act == wo_activity or _text_overlap(act, wo_activity) > 0.3
                    for act in billable_activities
                )
                if not matched and wo_activity:
                    conflicts.append(CrossPlaneConflict(
                        conflict_type="unbilled_work",
                        severity="error",
                        description=(
                            f"Work order activity '{wo_activity}' completed "
                            f"but no matching billable event in contract"
                        ),
                        domain_a="contract_margin",
                        domain_b="utilities_field",
                        object_b_id=wo_id,
                        resolution_suggestion="Review contract scope and add change order if needed",
                    ))

            # 2) Rate mismatch
            wo_rate = wo.get("rate", wo.get("billed_rate"))
            if isinstance(wo_rate, (int, float)) and wo_rate > 0:
                for act, contract_rate in contract_rates.items():
                    if act == wo_activity or _text_overlap(act, wo_activity) > 0.3:
                        if abs(wo_rate - contract_rate) > 0.01:
                            conflicts.append(CrossPlaneConflict(
                                conflict_type="rate_mismatch",
                                severity="warning",
                                description=(
                                    f"Work order rate ${wo_rate} differs from "
                                    f"contract rate ${contract_rate} for '{wo_activity}'"
                                ),
                                domain_a="contract_margin",
                                domain_b="utilities_field",
                                object_b_id=wo_id,
                                resolution_suggestion="Verify correct rate is applied",
                            ))
                        break

            # 3) Scope conflict
            if wo_activity and scope_descriptions:
                in_scope = any(
                    wo_activity in desc or _text_overlap(wo_activity, desc) > 0.15
                    for desc in scope_descriptions
                )
                if not in_scope:
                    conflicts.append(CrossPlaneConflict(
                        conflict_type="scope_conflict",
                        severity="warning",
                        description=(
                            f"Work order activity '{wo_activity}' not found "
                            f"in contract scope"
                        ),
                        domain_a="contract_margin",
                        domain_b="utilities_field",
                        object_b_id=wo_id,
                        resolution_suggestion="Raise change order for out-of-scope work",
                    ))

            # 4) Timeline conflict
            wo_date = wo.get("completed_date", wo.get("scheduled_date"))
            if wo_date and contract_end:
                if str(wo_date) > str(contract_end):
                    conflicts.append(CrossPlaneConflict(
                        conflict_type="timeline_conflict",
                        severity="error",
                        description=(
                            f"Work order completed on {wo_date} after contract "
                            f"expiry {contract_end}"
                        ),
                        domain_a="contract_margin",
                        domain_b="utilities_field",
                        object_b_id=wo_id,
                        resolution_suggestion="Verify contract renewal or extension",
                    ))

        return conflicts


# ---------------------------------------------------------------------------
# WorkOrderIncidentLinker
# ---------------------------------------------------------------------------


class WorkOrderIncidentLinker:
    """Link work order objects to incident objects."""

    def link_work_order_to_incident(
        self,
        work_order_objects: list[dict],
        incident_objects: list[dict],
    ) -> list[CrossPlaneLink]:
        """Match work orders to incidents by service, location, and ownership.

        Matching strategies:
        - Match dispatch to incident by service/location
        - Match work order status to incident state
        - Link engineer assignment to incident ownership
        """
        links: list[CrossPlaneLink] = []

        for wo in work_order_objects:
            wo_id = _safe_uuid(wo.get("id", wo.get("work_order_id", "")))
            wo_location = _normalize(wo.get("location", wo.get("site_id", "")))
            wo_services = [_normalize(s) for s in wo.get("affected_services", wo.get("services", []))]
            wo_description = wo.get("description", "")
            wo_incident_ref = wo.get("incident_id", wo.get("linked_incident_id", ""))

            for inc in incident_objects:
                inc_id = _safe_uuid(inc.get("id", inc.get("incident_id", "")))
                inc_services = [_normalize(s) for s in inc.get("affected_services", [])]
                inc_location = _normalize(inc.get("location", ""))
                inc_description = inc.get("description", inc.get("title", ""))

                # Direct incident reference match
                inc_ref = inc.get("incident_id", inc.get("id", ""))
                if wo_incident_ref and str(wo_incident_ref) == str(inc_ref):
                    links.append(CrossPlaneLink(
                        source_domain="utilities_field",
                        target_domain="telco_ops",
                        source_object_id=wo_id,
                        target_object_id=inc_id,
                        link_type="maps_to",
                        confidence=1.0,
                        metadata={"match_type": "direct_reference"},
                    ))
                    continue

                # 1) Match by service overlap
                service_overlap = set(wo_services) & set(inc_services) if wo_services and inc_services else set()
                if service_overlap:
                    links.append(CrossPlaneLink(
                        source_domain="utilities_field",
                        target_domain="telco_ops",
                        source_object_id=wo_id,
                        target_object_id=inc_id,
                        link_type="maps_to",
                        confidence=0.8,
                        metadata={
                            "match_type": "service_overlap",
                            "overlapping_services": list(service_overlap),
                        },
                    ))
                    continue

                # 2) Match by location
                if wo_location and inc_location and wo_location == inc_location:
                    links.append(CrossPlaneLink(
                        source_domain="utilities_field",
                        target_domain="telco_ops",
                        source_object_id=wo_id,
                        target_object_id=inc_id,
                        link_type="maps_to",
                        confidence=0.7,
                        metadata={"match_type": "location_match", "location": wo_location},
                    ))
                    continue

                # 3) Match by description overlap
                overlap = _text_overlap(wo_description, inc_description)
                if overlap > 0.25:
                    links.append(CrossPlaneLink(
                        source_domain="utilities_field",
                        target_domain="telco_ops",
                        source_object_id=wo_id,
                        target_object_id=inc_id,
                        link_type="maps_to",
                        confidence=min(overlap * 1.2, 0.9),
                        metadata={"match_type": "description_overlap"},
                    ))

        # Link engineer assignment to incident ownership
        for wo in work_order_objects:
            wo_id = _safe_uuid(wo.get("id", wo.get("work_order_id", "")))
            engineer = wo.get("assigned_engineer", wo.get("engineer_id", ""))
            if not engineer:
                continue
            for inc in incident_objects:
                inc_id = _safe_uuid(inc.get("id", inc.get("incident_id", "")))
                assigned_to = inc.get("assigned_to", "")
                if assigned_to and _normalize(str(engineer)) == _normalize(str(assigned_to)):
                    links.append(CrossPlaneLink(
                        source_domain="utilities_field",
                        target_domain="telco_ops",
                        source_object_id=wo_id,
                        target_object_id=inc_id,
                        link_type="triggers",
                        confidence=0.85,
                        metadata={
                            "match_type": "ownership_match",
                            "engineer": str(engineer),
                        },
                    ))

        return links

    def detect_field_ops_conflicts(
        self,
        work_order_objects: list[dict],
        incident_objects: list[dict],
    ) -> list[CrossPlaneConflict]:
        """Detect conflicts between field and ops planes.

        Checks for:
        - Incident resolved but work order still open
        - Work order completed but incident still active
        - Multiple work orders for same incident
        - Ownership mismatch
        """
        conflicts: list[CrossPlaneConflict] = []
        resolved_states = {"resolved", "closed"}
        active_states = {"new", "acknowledged", "investigating"}
        completed_wo_states = {"completed", "done", "finished", "closed"}
        open_wo_states = {"pending", "open", "in_progress", "assigned", "dispatched"}

        # Build incident lookup by id
        incident_by_id: dict[str, dict] = {}
        for inc in incident_objects:
            iid = str(inc.get("incident_id", inc.get("id", "")))
            incident_by_id[iid] = inc

        # Track work orders per incident for duplicate detection
        wo_per_incident: dict[str, list[dict]] = {}

        for wo in work_order_objects:
            wo_id = _safe_uuid(wo.get("id", wo.get("work_order_id", "")))
            wo_status = _normalize(wo.get("status", ""))
            wo_incident_ref = str(wo.get("incident_id", wo.get("linked_incident_id", "")))
            wo_engineer = wo.get("assigned_engineer", wo.get("engineer_id", ""))

            if wo_incident_ref and wo_incident_ref in incident_by_id:
                # Track for duplicate detection
                wo_per_incident.setdefault(wo_incident_ref, []).append(wo)
                inc = incident_by_id[wo_incident_ref]
                inc_id = _safe_uuid(inc.get("id", inc.get("incident_id", "")))
                inc_state = _normalize(inc.get("state", inc.get("status", "")))
                inc_owner = inc.get("assigned_to", "")

                # 1) Incident resolved but work order still open
                if inc_state in resolved_states and wo_status in open_wo_states:
                    conflicts.append(CrossPlaneConflict(
                        conflict_type="incident_resolved_wo_open",
                        severity="warning",
                        description=(
                            f"Incident '{wo_incident_ref}' is resolved but "
                            f"work order is still '{wo_status}'"
                        ),
                        domain_a="utilities_field",
                        domain_b="telco_ops",
                        object_a_id=wo_id,
                        object_b_id=inc_id,
                        resolution_suggestion="Close or cancel the work order",
                    ))

                # 2) Work order completed but incident still active
                if wo_status in completed_wo_states and inc_state in active_states:
                    conflicts.append(CrossPlaneConflict(
                        conflict_type="wo_completed_incident_active",
                        severity="warning",
                        description=(
                            f"Work order completed but incident "
                            f"'{wo_incident_ref}' is still '{inc_state}'"
                        ),
                        domain_a="utilities_field",
                        domain_b="telco_ops",
                        object_a_id=wo_id,
                        object_b_id=inc_id,
                        resolution_suggestion="Update incident state to resolved",
                    ))

                # 4) Ownership mismatch
                if wo_engineer and inc_owner:
                    if _normalize(str(wo_engineer)) != _normalize(str(inc_owner)):
                        conflicts.append(CrossPlaneConflict(
                            conflict_type="ownership_mismatch",
                            severity="info",
                            description=(
                                f"Work order assigned to '{wo_engineer}' but "
                                f"incident assigned to '{inc_owner}'"
                            ),
                            domain_a="utilities_field",
                            domain_b="telco_ops",
                            object_a_id=wo_id,
                            object_b_id=inc_id,
                            resolution_suggestion="Align work order and incident ownership",
                        ))

        # 3) Multiple work orders for same incident
        for inc_ref, wos in wo_per_incident.items():
            if len(wos) > 1:
                conflicts.append(CrossPlaneConflict(
                    conflict_type="multiple_work_orders",
                    severity="warning",
                    description=(
                        f"Incident '{inc_ref}' has {len(wos)} work orders linked"
                    ),
                    domain_a="utilities_field",
                    domain_b="telco_ops",
                    resolution_suggestion="Review and consolidate duplicate work orders",
                ))

        return conflicts


# ---------------------------------------------------------------------------
# MarginEvidenceAssembler
# ---------------------------------------------------------------------------


class MarginEvidenceAssembler:
    """Assemble evidence bundles for margin diagnosis."""

    def assemble_margin_evidence(
        self,
        contract_objects: list[dict],
        work_objects: list[dict],
        incident_objects: list[dict],
    ) -> EvidenceBundle:
        """Build complete evidence bundle for margin analysis.

        Steps:
        1. Collect all billable events from contract
        2. Match to work history
        3. Identify unbilled work
        4. Calculate rate variances
        5. Detect penalty exposure
        6. Build cross-links
        7. Detect conflicts
        """
        linker = ContractWorkOrderLinker()
        cross_links = linker.link_contract_to_work_order(contract_objects, work_objects)
        conflicts = linker.detect_commercial_field_conflicts(contract_objects, work_objects)

        # Also link work orders to incidents for full picture
        wo_inc_linker = WorkOrderIncidentLinker()
        wi_links = wo_inc_linker.link_work_order_to_incident(work_objects, incident_objects)
        wi_conflicts = wo_inc_linker.detect_field_ops_conflicts(work_objects, incident_objects)

        return EvidenceBundle(
            bundle_type="margin_evidence",
            contract_objects=contract_objects,
            field_objects=work_objects,
            ops_objects=incident_objects,
            cross_links=cross_links + wi_links,
            conflicts=conflicts + wi_conflicts,
        )

    def calculate_margin_impact(self, bundle: EvidenceBundle) -> dict:
        """Calculate financial impact from evidence bundle.

        Returns:
            dict with total_billed, total_billable, leakage_amount,
            penalty_exposure, and recovery_potential.
        """
        total_billed = 0.0
        total_billable = 0.0
        penalty_exposure = 0.0

        # Collect billing data from work objects
        for wo in bundle.field_objects:
            rate = wo.get("rate", wo.get("billed_rate", 0))
            hours = wo.get("hours", wo.get("actual_duration_hours", 0))
            if not isinstance(rate, (int, float)):
                rate = 0
            if not isinstance(hours, (int, float)):
                hours = 0
            amount = rate * hours

            if wo.get("billed", False):
                total_billed += amount
            status = wo.get("status", "")
            if status in ("completed", "done", "finished") or wo.get("billed", False):
                total_billable += amount

        # Collect penalty exposure from contract objects
        for co in bundle.contract_objects:
            if co.get("control_type") == "penalty_condition":
                payload = co.get("payload", {})
                if payload.get("breach_detected", False):
                    cap = payload.get("cap")
                    if isinstance(cap, (int, float)):
                        penalty_exposure += cap
                    else:
                        # Estimate from penalty amount string
                        amt_str = payload.get("penalty_amount", co.get("penalty_amount", ""))
                        try:
                            penalty_exposure += float(str(amt_str).replace("$", "").replace(",", "").replace("%", ""))
                        except (ValueError, TypeError):
                            penalty_exposure += 1000.0  # default estimate

        leakage_amount = max(total_billable - total_billed, 0.0)

        # Recovery potential: leakage + unbilled conflicts
        unbilled_conflicts = [
            c for c in bundle.conflicts if c.conflict_type == "unbilled_work"
        ]
        recovery_potential = leakage_amount + len(unbilled_conflicts) * 500.0

        return {
            "total_billed": total_billed,
            "total_billable": total_billable,
            "leakage_amount": leakage_amount,
            "penalty_exposure": penalty_exposure,
            "recovery_potential": recovery_potential,
        }


# ---------------------------------------------------------------------------
# ReadinessEvidenceAssembler
# ---------------------------------------------------------------------------


class ReadinessEvidenceAssembler:
    """Assemble evidence for readiness assessment."""

    def assemble_readiness_evidence(
        self,
        work_order_objects: list[dict],
        engineer_objects: list[dict],
        contract_objects: list[dict],
    ) -> EvidenceBundle:
        """Build evidence bundle for field readiness assessment.

        Collects work order details, engineer profiles, and relevant contract
        obligations to determine dispatch readiness.
        """
        linker = ContractWorkOrderLinker()
        cross_links = linker.link_contract_to_work_order(contract_objects, work_order_objects)
        conflicts = linker.detect_commercial_field_conflicts(contract_objects, work_order_objects)

        return EvidenceBundle(
            bundle_type="readiness_evidence",
            contract_objects=contract_objects,
            field_objects=work_order_objects + engineer_objects,
            ops_objects=[],
            cross_links=cross_links,
            conflicts=conflicts,
        )


# ---------------------------------------------------------------------------
# OpsEvidenceAssembler
# ---------------------------------------------------------------------------


class OpsEvidenceAssembler:
    """Assemble evidence for ops decisions."""

    def assemble_ops_evidence(
        self,
        incident_objects: list[dict],
        work_order_objects: list[dict],
        service_state_objects: list[dict],
    ) -> EvidenceBundle:
        """Build evidence bundle for operational decisions.

        Links incidents to work orders and enriches with service state context.
        """
        linker = WorkOrderIncidentLinker()
        cross_links = linker.link_work_order_to_incident(work_order_objects, incident_objects)
        conflicts = linker.detect_field_ops_conflicts(work_order_objects, incident_objects)

        return EvidenceBundle(
            bundle_type="ops_evidence",
            contract_objects=[],
            field_objects=work_order_objects,
            ops_objects=incident_objects + service_state_objects,
            cross_links=cross_links,
            conflicts=conflicts,
        )


# ---------------------------------------------------------------------------
# CrossPlaneReconciler
# ---------------------------------------------------------------------------


class CrossPlaneReconciler:
    """Main reconciliation entry point."""

    def reconcile_all(
        self,
        contract_objects: list[dict],
        work_order_objects: list[dict],
        incident_objects: list[dict],
    ) -> dict:
        """Run all cross-plane reconciliation checks.

        Performs:
        1. Contract <-> Work Order linking and conflict detection
        2. Work Order <-> Incident linking and conflict detection
        3. Aggregated summary
        """
        linker_cw = ContractWorkOrderLinker()
        linker_wi = WorkOrderIncidentLinker()

        cw_links = linker_cw.link_contract_to_work_order(contract_objects, work_order_objects)
        wi_links = linker_wi.link_work_order_to_incident(work_order_objects, incident_objects)

        cw_conflicts = linker_cw.detect_commercial_field_conflicts(
            contract_objects, work_order_objects
        )
        wi_conflicts = linker_wi.detect_field_ops_conflicts(
            work_order_objects, incident_objects
        )

        return {
            "links": cw_links + wi_links,
            "conflicts": cw_conflicts + wi_conflicts,
            "has_conflicts": len(cw_conflicts) + len(wi_conflicts) > 0,
            "summary": self._build_summary(cw_links, wi_links, cw_conflicts, wi_conflicts),
        }

    def _build_summary(
        self,
        cw_links: list[CrossPlaneLink],
        wi_links: list[CrossPlaneLink],
        cw_conflicts: list[CrossPlaneConflict],
        wi_conflicts: list[CrossPlaneConflict],
    ) -> dict:
        """Build a summary of reconciliation results."""
        all_conflicts = cw_conflicts + wi_conflicts

        conflict_types: dict[str, int] = {}
        for c in all_conflicts:
            conflict_types[c.conflict_type] = conflict_types.get(c.conflict_type, 0) + 1

        severity_counts: dict[str, int] = {}
        for c in all_conflicts:
            severity_counts[c.severity] = severity_counts.get(c.severity, 0) + 1

        return {
            "total_links": len(cw_links) + len(wi_links),
            "contract_work_order_links": len(cw_links),
            "work_order_incident_links": len(wi_links),
            "total_conflicts": len(all_conflicts),
            "contract_field_conflicts": len(cw_conflicts),
            "field_ops_conflicts": len(wi_conflicts),
            "conflict_types": conflict_types,
            "severity_counts": severity_counts,
        }
