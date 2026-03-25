"""Cross-pack reconciliation module.

Links control objects across the commercial (contract_margin), field
(utilities_field), and operations (telco_ops) domains. Provides linkers for
detecting relationships and conflicts between domain objects and assemblers
for building evidence bundles used in downstream diagnosis and decision-making.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

DOMAIN_CONTRACT_MARGIN = "contract_margin"
DOMAIN_UTILITIES_FIELD = "utilities_field"
DOMAIN_TELCO_OPS = "telco_ops"

# Matching thresholds
_TEXT_SIMILARITY_THRESHOLD = 0.55
_HIGH_CONFIDENCE = 0.90
_MEDIUM_CONFIDENCE = 0.70
_LOW_CONFIDENCE = 0.50
_RATE_TOLERANCE_FRACTION = 0.01  # 1 % tolerance for rate comparison
_TIME_WINDOW_HOURS = 48  # default window for temporal matching


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CrossPlaneLink(BaseModel):
    """A directed link between two control objects in different domains."""

    source_domain: str
    source_id: str
    target_domain: str
    target_id: str
    link_type: str
    confidence: float
    metadata: dict = Field(default_factory=dict)


class CrossPlaneConflict(BaseModel):
    """A detected conflict between two domain planes."""

    field: str
    domain_a: str
    value_a: str
    domain_b: str
    value_b: str
    severity: str  # info, warning, error, critical
    resolution: str


class EvidenceBundle(BaseModel):
    """An assembled bundle of cross-domain evidence items."""

    bundle_id: str
    domains: list[str]
    evidence_items: list[dict]
    total_items: int
    confidence: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text_similarity(a: str, b: str) -> float:
    """Return a 0-1 similarity ratio between two strings (case-insensitive)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _safe_str(value: Any) -> str:
    """Coerce *value* to a stripped string."""
    if value is None:
        return ""
    return str(value).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce *value* to float, returning *default* on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Any) -> datetime | None:
    """Best-effort ISO datetime parse."""
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    raw = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _extract_activities(description: str) -> set[str]:
    """Extract a rough set of normalised 'activity tokens' from free text."""
    tokens: set[str] = set()
    for word in description.lower().replace(",", " ").replace(".", " ").split():
        cleaned = word.strip()
        if len(cleaned) > 2:
            tokens.add(cleaned)
    return tokens


# ---------------------------------------------------------------------------
# ContractWorkOrderLinker
# ---------------------------------------------------------------------------


class ContractWorkOrderLinker:
    """Links contract control objects to work orders.

    Matching strategies:
    1. Rate card entries  -> WO activities  (text similarity on activity name)
    2. Obligations        -> WO type        (obligation description vs WO type/desc)
    3. Scope boundaries   -> WO description (activity overlap)
    """

    def link(
        self,
        contract_objects: list[dict],
        work_order: dict,
    ) -> list[CrossPlaneLink]:
        links: list[CrossPlaneLink] = []

        wo_id = _safe_str(work_order.get("work_order_id", ""))
        wo_type = _safe_str(work_order.get("work_order_type", ""))
        wo_desc = _safe_str(work_order.get("description", ""))
        wo_activities = _extract_activities(wo_desc)

        for obj in contract_objects:
            obj_type = _safe_str(obj.get("type", obj.get("object_type", "")))
            obj_id = _safe_str(
                obj.get("id", obj.get("clause_id", obj.get("activity", "")))
            )

            # --- Rate card matching ---
            if obj_type in ("rate_card", "rate") or "activity" in obj:
                activity_name = _safe_str(obj.get("activity", ""))
                if activity_name:
                    sim = _text_similarity(activity_name, wo_desc)
                    # Also check token overlap
                    activity_tokens = _extract_activities(activity_name)
                    overlap = activity_tokens & wo_activities
                    token_score = (
                        len(overlap) / max(len(activity_tokens), 1)
                        if activity_tokens
                        else 0.0
                    )
                    combined = max(sim, token_score)
                    if combined >= _TEXT_SIMILARITY_THRESHOLD:
                        links.append(
                            CrossPlaneLink(
                                source_domain=DOMAIN_CONTRACT_MARGIN,
                                source_id=obj_id or activity_name,
                                target_domain=DOMAIN_UTILITIES_FIELD,
                                target_id=wo_id,
                                link_type="rate_card_to_activity",
                                confidence=round(min(combined, 1.0), 3),
                                metadata={
                                    "activity": activity_name,
                                    "rate": obj.get("rate"),
                                    "unit": obj.get("unit"),
                                    "similarity": round(combined, 3),
                                },
                            )
                        )

            # --- Obligation matching ---
            if obj_type in ("obligation",) or "description" in obj and "due_type" in obj:
                obligation_desc = _safe_str(obj.get("description", ""))
                sim_type = _text_similarity(obligation_desc, wo_type)
                sim_desc = _text_similarity(obligation_desc, wo_desc)
                best = max(sim_type, sim_desc)
                if best >= _TEXT_SIMILARITY_THRESHOLD:
                    links.append(
                        CrossPlaneLink(
                            source_domain=DOMAIN_CONTRACT_MARGIN,
                            source_id=obj_id or obligation_desc[:60],
                            target_domain=DOMAIN_UTILITIES_FIELD,
                            target_id=wo_id,
                            link_type="obligation_to_work_order",
                            confidence=round(min(best, 1.0), 3),
                            metadata={
                                "obligation_description": obligation_desc,
                                "wo_type": wo_type,
                                "similarity": round(best, 3),
                            },
                        )
                    )

            # --- Scope boundary matching ---
            if obj_type in ("scope", "scope_boundary") or "scope_type" in obj:
                scope_desc = _safe_str(obj.get("description", ""))
                scope_activities = set(
                    a.lower().strip() for a in obj.get("activities", [])
                )
                overlap = scope_activities & wo_activities
                desc_sim = _text_similarity(scope_desc, wo_desc)
                token_score = (
                    len(overlap) / max(len(scope_activities), 1)
                    if scope_activities
                    else 0.0
                )
                combined = max(desc_sim, token_score)
                if combined >= _TEXT_SIMILARITY_THRESHOLD:
                    scope_type = _safe_str(obj.get("scope_type", ""))
                    links.append(
                        CrossPlaneLink(
                            source_domain=DOMAIN_CONTRACT_MARGIN,
                            source_id=obj_id or scope_desc[:60],
                            target_domain=DOMAIN_UTILITIES_FIELD,
                            target_id=wo_id,
                            link_type="scope_boundary_to_work_order",
                            confidence=round(min(combined, 1.0), 3),
                            metadata={
                                "scope_type": scope_type,
                                "overlapping_activities": sorted(overlap),
                                "similarity": round(combined, 3),
                            },
                        )
                    )

        return links

    # ---- Conflict detection ----

    def detect_conflicts(
        self,
        links: list[CrossPlaneLink],
        contract_data: dict,
        wo_data: dict,
    ) -> list[CrossPlaneConflict]:
        conflicts: list[CrossPlaneConflict] = []

        rate_card = contract_data.get("rate_card", [])
        obligations = contract_data.get("obligations", [])
        scope_boundaries = contract_data.get("scope_boundaries", [])

        wo_desc = _safe_str(wo_data.get("description", ""))
        wo_type = _safe_str(wo_data.get("work_order_type", ""))
        wo_rate = _safe_float(wo_data.get("rate"))
        wo_activities = _extract_activities(wo_desc)

        # --- Rate mismatches ---
        for link in links:
            if link.link_type == "rate_card_to_activity":
                contract_rate = _safe_float(link.metadata.get("rate"))
                if contract_rate > 0 and wo_rate > 0:
                    diff = abs(contract_rate - wo_rate)
                    tolerance = contract_rate * _RATE_TOLERANCE_FRACTION
                    if diff > tolerance:
                        severity = "critical" if diff / contract_rate > 0.10 else "warning"
                        conflicts.append(
                            CrossPlaneConflict(
                                field="rate",
                                domain_a=DOMAIN_CONTRACT_MARGIN,
                                value_a=str(contract_rate),
                                domain_b=DOMAIN_UTILITIES_FIELD,
                                value_b=str(wo_rate),
                                severity=severity,
                                resolution=(
                                    "Review rate card against work order pricing. "
                                    f"Difference of {diff:.2f} detected."
                                ),
                            )
                        )

        # --- Scope conflicts ---
        for boundary in scope_boundaries:
            scope_type = _safe_str(boundary.get("scope_type", ""))
            if scope_type == "out_of_scope":
                out_activities = set(
                    a.lower().strip() for a in boundary.get("activities", [])
                )
                overlap = out_activities & wo_activities
                if overlap:
                    conflicts.append(
                        CrossPlaneConflict(
                            field="scope",
                            domain_a=DOMAIN_CONTRACT_MARGIN,
                            value_a=f"out_of_scope: {', '.join(sorted(overlap))}",
                            domain_b=DOMAIN_UTILITIES_FIELD,
                            value_b=wo_desc[:120],
                            severity="error",
                            resolution=(
                                "Work order references activities marked out-of-scope "
                                "in the contract. Raise a scope clarification or "
                                "change order before proceeding."
                            ),
                        )
                    )

        # --- Missing obligation coverage ---
        linked_obligation_ids = {
            link.source_id
            for link in links
            if link.link_type == "obligation_to_work_order"
        }
        for obligation in obligations:
            ob_id = _safe_str(
                obligation.get("clause_id", obligation.get("id", ""))
            )
            ob_status = _safe_str(obligation.get("status", "active"))
            if ob_status == "active" and ob_id not in linked_obligation_ids:
                ob_desc = _safe_str(obligation.get("description", ""))
                # Only flag if the obligation is plausibly relevant
                sim = _text_similarity(ob_desc, wo_desc)
                if sim >= 0.30:
                    conflicts.append(
                        CrossPlaneConflict(
                            field="obligation_coverage",
                            domain_a=DOMAIN_CONTRACT_MARGIN,
                            value_a=ob_desc[:120],
                            domain_b=DOMAIN_UTILITIES_FIELD,
                            value_b=f"work_order:{wo_data.get('work_order_id', '')}",
                            severity="warning",
                            resolution=(
                                "Active obligation may not be addressed by the "
                                "current work order. Verify compliance."
                            ),
                        )
                    )

        return conflicts


# ---------------------------------------------------------------------------
# WorkOrderIncidentLinker
# ---------------------------------------------------------------------------


class WorkOrderIncidentLinker:
    """Links work orders to incidents by service, location, and time window."""

    def link(
        self,
        work_order: dict,
        incidents: list[dict],
    ) -> list[CrossPlaneLink]:
        links: list[CrossPlaneLink] = []

        wo_id = _safe_str(work_order.get("work_order_id", ""))
        wo_location = _safe_str(work_order.get("location", ""))
        wo_site = _safe_str(work_order.get("site_id", ""))
        wo_desc = _safe_str(work_order.get("description", ""))
        wo_customer = _safe_str(work_order.get("customer", ""))
        wo_start = _parse_datetime(
            work_order.get("scheduled_date") or work_order.get("scheduled_start")
        )
        wo_end = _parse_datetime(work_order.get("scheduled_end"))

        for incident in incidents:
            inc_id = _safe_str(incident.get("incident_id", ""))
            inc_services = [
                s.lower().strip()
                for s in incident.get("affected_services", [])
            ]
            inc_desc = _safe_str(incident.get("description", ""))
            inc_title = _safe_str(incident.get("title", ""))
            inc_created = _parse_datetime(incident.get("created_at"))
            inc_location = _safe_str(incident.get("location", ""))
            inc_site = _safe_str(incident.get("site_id", ""))

            confidence_signals: list[float] = []

            # --- Service match ---
            wo_desc_lower = wo_desc.lower()
            service_matched = False
            for svc in inc_services:
                if svc and (svc in wo_desc_lower or svc in wo_location.lower()):
                    service_matched = True
                    break
            if service_matched:
                confidence_signals.append(0.35)

            # --- Location / site match ---
            location_matched = False
            if wo_site and inc_site and wo_site.lower() == inc_site.lower():
                location_matched = True
                confidence_signals.append(0.30)
            elif wo_location and inc_location:
                loc_sim = _text_similarity(wo_location, inc_location)
                if loc_sim >= _TEXT_SIMILARITY_THRESHOLD:
                    location_matched = True
                    confidence_signals.append(0.30 * loc_sim)

            # --- Time window match ---
            time_matched = False
            if wo_start and inc_created:
                window = timedelta(hours=_TIME_WINDOW_HOURS)
                if wo_end:
                    effective_end = max(wo_end, wo_start + window)
                else:
                    effective_end = wo_start + window
                effective_start = wo_start - window
                if effective_start <= inc_created <= effective_end:
                    time_matched = True
                    confidence_signals.append(0.25)

            # --- Text similarity boost ---
            desc_sim = max(
                _text_similarity(wo_desc, inc_desc),
                _text_similarity(wo_desc, inc_title),
            )
            if desc_sim >= _TEXT_SIMILARITY_THRESHOLD:
                confidence_signals.append(0.10 * desc_sim)

            # Require at least two positive signals to create a link
            if len(confidence_signals) >= 2:
                total_confidence = min(sum(confidence_signals), 1.0)
                links.append(
                    CrossPlaneLink(
                        source_domain=DOMAIN_UTILITIES_FIELD,
                        source_id=wo_id,
                        target_domain=DOMAIN_TELCO_OPS,
                        target_id=inc_id,
                        link_type="work_order_to_incident",
                        confidence=round(total_confidence, 3),
                        metadata={
                            "service_match": service_matched,
                            "location_match": location_matched,
                            "time_match": time_matched,
                            "description_similarity": round(desc_sim, 3),
                        },
                    )
                )

        return links

    def detect_conflicts(
        self,
        links: list[CrossPlaneLink],
        wo_data: dict,
        incident_data: dict,
    ) -> list[CrossPlaneConflict]:
        conflicts: list[CrossPlaneConflict] = []

        wo_start = _parse_datetime(
            wo_data.get("scheduled_date") or wo_data.get("scheduled_start")
        )
        wo_end = _parse_datetime(wo_data.get("scheduled_end"))
        wo_assigned = _safe_str(wo_data.get("assigned_to", wo_data.get("engineer", "")))

        incidents = incident_data.get("incidents", [incident_data])
        if not isinstance(incidents, list):
            incidents = [incidents]

        incident_map: dict[str, dict] = {}
        for inc in incidents:
            iid = _safe_str(inc.get("incident_id", ""))
            if iid:
                incident_map[iid] = inc

        for link in links:
            if link.link_type != "work_order_to_incident":
                continue

            inc = incident_map.get(link.target_id)
            if not inc:
                continue

            inc_created = _parse_datetime(inc.get("created_at"))
            inc_assigned = _safe_str(inc.get("assigned_to", ""))

            # --- Timing conflict ---
            if wo_start and inc_created:
                if inc_created > wo_start:
                    gap_hours = (inc_created - wo_start).total_seconds() / 3600
                    if gap_hours > _TIME_WINDOW_HOURS:
                        conflicts.append(
                            CrossPlaneConflict(
                                field="timing",
                                domain_a=DOMAIN_UTILITIES_FIELD,
                                value_a=wo_start.isoformat(),
                                domain_b=DOMAIN_TELCO_OPS,
                                value_b=inc_created.isoformat(),
                                severity="warning",
                                resolution=(
                                    f"Incident was created {gap_hours:.1f}h after work "
                                    "order start. Verify causal relationship."
                                ),
                            )
                        )
                elif wo_end and inc_created < wo_end:
                    # Incident created before WO ended -- usually fine
                    pass
                elif wo_end and inc_created > wo_end:
                    post_hours = (inc_created - wo_end).total_seconds() / 3600
                    conflicts.append(
                        CrossPlaneConflict(
                            field="timing",
                            domain_a=DOMAIN_UTILITIES_FIELD,
                            value_a=wo_end.isoformat(),
                            domain_b=DOMAIN_TELCO_OPS,
                            value_b=inc_created.isoformat(),
                            severity="error",
                            resolution=(
                                "Incident was created after the work order "
                                f"ended ({post_hours:.1f}h later). "
                                "May indicate a post-completion fault."
                            ),
                        )
                    )

            # --- Ownership mismatch ---
            if wo_assigned and inc_assigned:
                if wo_assigned.lower() != inc_assigned.lower():
                    conflicts.append(
                        CrossPlaneConflict(
                            field="ownership",
                            domain_a=DOMAIN_UTILITIES_FIELD,
                            value_a=wo_assigned,
                            domain_b=DOMAIN_TELCO_OPS,
                            value_b=inc_assigned,
                            severity="warning",
                            resolution=(
                                "Work order and incident are assigned to different "
                                "owners. Align ownership to avoid coordination gaps."
                            ),
                        )
                    )

            # --- Severity vs priority mismatch ---
            inc_severity = _safe_str(inc.get("severity", ""))
            wo_priority = _safe_str(wo_data.get("priority", ""))
            severity_priority_map = {
                "p1": {"emergency", "critical", "high"},
                "p2": {"high", "urgent"},
                "p3": {"normal", "medium"},
                "p4": {"low"},
            }
            expected_priorities = severity_priority_map.get(inc_severity, set())
            if expected_priorities and wo_priority.lower() not in expected_priorities:
                conflicts.append(
                    CrossPlaneConflict(
                        field="severity_priority_alignment",
                        domain_a=DOMAIN_TELCO_OPS,
                        value_a=f"severity={inc_severity}",
                        domain_b=DOMAIN_UTILITIES_FIELD,
                        value_b=f"priority={wo_priority}",
                        severity="warning",
                        resolution=(
                            f"Incident severity '{inc_severity}' does not align with "
                            f"work order priority '{wo_priority}'. Review escalation."
                        ),
                    )
                )

        return conflicts


# ---------------------------------------------------------------------------
# Evidence assemblers
# ---------------------------------------------------------------------------


class MarginEvidenceAssembler:
    """Assembles evidence bundles for margin leakage diagnosis."""

    def assemble(
        self,
        contract_objects: list[dict],
        work_history: list[dict],
        leakage_triggers: list[dict],
    ) -> EvidenceBundle:
        items: list[dict] = []

        for obj in contract_objects:
            items.append({
                "domain": DOMAIN_CONTRACT_MARGIN,
                "type": _safe_str(
                    obj.get("type", obj.get("object_type", "contract_object"))
                ),
                "id": _safe_str(
                    obj.get("id", obj.get("clause_id", obj.get("activity", "")))
                ),
                "summary": _safe_str(obj.get("description", obj.get("activity", "")))[:200],
                "data": obj,
            })

        for wo in work_history:
            items.append({
                "domain": DOMAIN_UTILITIES_FIELD,
                "type": "work_order",
                "id": _safe_str(wo.get("work_order_id", "")),
                "summary": _safe_str(wo.get("description", ""))[:200],
                "data": wo,
            })

        for trigger in leakage_triggers:
            items.append({
                "domain": DOMAIN_CONTRACT_MARGIN,
                "type": "leakage_trigger",
                "id": _safe_str(trigger.get("trigger_type", "")),
                "summary": _safe_str(trigger.get("description", ""))[:200],
                "severity": _safe_str(trigger.get("severity", "medium")),
                "data": trigger,
            })

        domains = sorted(
            {item["domain"] for item in items}
        )
        confidence = self._compute_confidence(items, leakage_triggers)

        return EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            domains=domains,
            evidence_items=items,
            total_items=len(items),
            confidence=round(confidence, 3),
        )

    @staticmethod
    def _compute_confidence(
        items: list[dict], leakage_triggers: list[dict]
    ) -> float:
        if not items:
            return 0.0
        domain_count = len({item["domain"] for item in items})
        has_contract = any(
            item["domain"] == DOMAIN_CONTRACT_MARGIN
            and item["type"] != "leakage_trigger"
            for item in items
        )
        has_work = any(
            item["domain"] == DOMAIN_UTILITIES_FIELD for item in items
        )
        has_triggers = len(leakage_triggers) > 0

        score = 0.3 * min(domain_count / 2, 1.0)
        if has_contract:
            score += 0.25
        if has_work:
            score += 0.25
        if has_triggers:
            score += 0.20
        return min(score, 1.0)


class ReadinessEvidenceAssembler:
    """Assembles evidence bundles for field readiness decisions."""

    def assemble(
        self,
        work_order: dict,
        engineer: dict,
        blockers: list[dict],
        skill_fit: dict,
    ) -> EvidenceBundle:
        items: list[dict] = []

        items.append({
            "domain": DOMAIN_UTILITIES_FIELD,
            "type": "work_order",
            "id": _safe_str(work_order.get("work_order_id", "")),
            "summary": _safe_str(work_order.get("description", ""))[:200],
            "data": work_order,
        })

        items.append({
            "domain": DOMAIN_UTILITIES_FIELD,
            "type": "engineer_profile",
            "id": _safe_str(engineer.get("engineer_id", "")),
            "summary": _safe_str(engineer.get("name", "")),
            "data": engineer,
        })

        for blocker in blockers:
            items.append({
                "domain": DOMAIN_UTILITIES_FIELD,
                "type": "blocker",
                "id": _safe_str(blocker.get("blocker_type", "")),
                "summary": _safe_str(blocker.get("description", ""))[:200],
                "severity": _safe_str(blocker.get("severity", "error")),
                "data": blocker,
            })

        items.append({
            "domain": DOMAIN_UTILITIES_FIELD,
            "type": "skill_fit",
            "id": "skill_fit_analysis",
            "summary": "fit" if skill_fit.get("fit") else "no_fit",
            "data": skill_fit,
        })

        confidence = self._compute_confidence(
            work_order, engineer, blockers, skill_fit
        )

        return EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            domains=[DOMAIN_UTILITIES_FIELD],
            evidence_items=items,
            total_items=len(items),
            confidence=round(confidence, 3),
        )

    @staticmethod
    def _compute_confidence(
        work_order: dict,
        engineer: dict,
        blockers: list[dict],
        skill_fit: dict,
    ) -> float:
        score = 0.5  # baseline for having WO + engineer
        if skill_fit.get("fit"):
            score += 0.25
        else:
            score -= 0.15
        if not blockers:
            score += 0.25
        else:
            critical_blockers = sum(
                1
                for b in blockers
                if _safe_str(b.get("severity", "")).lower() in ("error", "critical")
            )
            score -= 0.10 * min(critical_blockers, 3)
        return max(min(score, 1.0), 0.0)


class OpsEvidenceAssembler:
    """Assembles evidence bundles for operational decisions."""

    def assemble(
        self,
        incident: dict,
        service_states: list[dict],
        escalation: dict,
        next_action: dict,
    ) -> EvidenceBundle:
        items: list[dict] = []

        items.append({
            "domain": DOMAIN_TELCO_OPS,
            "type": "incident",
            "id": _safe_str(incident.get("incident_id", "")),
            "summary": _safe_str(
                incident.get("title", incident.get("description", ""))
            )[:200],
            "severity": _safe_str(incident.get("severity", "")),
            "data": incident,
        })

        for svc in service_states:
            items.append({
                "domain": DOMAIN_TELCO_OPS,
                "type": "service_state",
                "id": _safe_str(svc.get("service_id", "")),
                "summary": (
                    f"{_safe_str(svc.get('service_name', ''))} "
                    f"[{_safe_str(svc.get('state', ''))}]"
                ),
                "impact_level": _safe_str(svc.get("impact_level", "")),
                "data": svc,
            })

        if escalation:
            items.append({
                "domain": DOMAIN_TELCO_OPS,
                "type": "escalation_decision",
                "id": _safe_str(escalation.get("level", "none")),
                "summary": _safe_str(escalation.get("reason", "")),
                "data": escalation,
            })

        if next_action:
            items.append({
                "domain": DOMAIN_TELCO_OPS,
                "type": "next_action",
                "id": _safe_str(next_action.get("action", "")),
                "summary": _safe_str(next_action.get("reason", "")),
                "data": next_action,
            })

        confidence = self._compute_confidence(
            incident, service_states, escalation, next_action
        )

        return EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            domains=[DOMAIN_TELCO_OPS],
            evidence_items=items,
            total_items=len(items),
            confidence=round(confidence, 3),
        )

    @staticmethod
    def _compute_confidence(
        incident: dict,
        service_states: list[dict],
        escalation: dict,
        next_action: dict,
    ) -> float:
        score = 0.3  # baseline for having an incident
        if service_states:
            score += 0.25
        if escalation and escalation.get("reason"):
            score += 0.20
        if next_action and next_action.get("action"):
            score += 0.25
        return min(score, 1.0)


# ---------------------------------------------------------------------------
# CrossPlaneReconciler — main entry point
# ---------------------------------------------------------------------------


class CrossPlaneReconciler:
    """Orchestrates cross-domain reconciliation across all three planes."""

    def __init__(self) -> None:
        self._contract_wo_linker = ContractWorkOrderLinker()
        self._wo_incident_linker = WorkOrderIncidentLinker()
        self._margin_assembler = MarginEvidenceAssembler()
        self._readiness_assembler = ReadinessEvidenceAssembler()
        self._ops_assembler = OpsEvidenceAssembler()

    # -- Contract <-> Work Order --

    def reconcile_contract_to_work_order(
        self,
        contract_data: dict,
        wo_data: dict,
    ) -> dict:
        contract_objects = self._collect_contract_objects(contract_data)

        links = self._contract_wo_linker.link(contract_objects, wo_data)
        conflicts = self._contract_wo_linker.detect_conflicts(
            links, contract_data, wo_data
        )

        leakage_triggers = contract_data.get("leakage_triggers", [])
        evidence = self._margin_assembler.assemble(
            contract_objects,
            [wo_data],
            leakage_triggers,
        )

        return {
            "links": [link.model_dump() for link in links],
            "conflicts": [conflict.model_dump() for conflict in conflicts],
            "evidence": evidence.model_dump(),
        }

    # -- Work Order <-> Incident --

    def reconcile_work_order_to_incident(
        self,
        wo_data: dict,
        incident_data: dict,
    ) -> dict:
        incidents = incident_data.get("incidents", [incident_data])
        if not isinstance(incidents, list):
            incidents = [incidents]

        links = self._wo_incident_linker.link(wo_data, incidents)
        conflicts = self._wo_incident_linker.detect_conflicts(
            links, wo_data, incident_data
        )

        primary_incident = incidents[0] if incidents else {}
        service_states = incident_data.get("service_states", [])
        escalation = incident_data.get("escalation", {})
        next_action = incident_data.get("next_action", {})

        evidence = self._ops_assembler.assemble(
            primary_incident,
            service_states,
            escalation,
            next_action,
        )

        return {
            "links": [link.model_dump() for link in links],
            "conflicts": [conflict.model_dump() for conflict in conflicts],
            "evidence": evidence.model_dump(),
        }

    # -- Full three-plane reconciliation --

    def full_reconciliation(
        self,
        contract_data: dict,
        wo_data: dict,
        incident_data: dict,
    ) -> dict:
        contract_to_wo = self.reconcile_contract_to_work_order(
            contract_data, wo_data
        )
        wo_to_incident = self.reconcile_work_order_to_incident(
            wo_data, incident_data
        )

        all_links = contract_to_wo["links"] + wo_to_incident["links"]
        all_conflicts = contract_to_wo["conflicts"] + wo_to_incident["conflicts"]

        # Build aggregate evidence combining both bundles
        contract_evidence = contract_to_wo["evidence"]
        ops_evidence = wo_to_incident["evidence"]

        combined_items = (
            contract_evidence.get("evidence_items", [])
            + ops_evidence.get("evidence_items", [])
        )
        combined_domains = sorted(
            {item.get("domain", "") for item in combined_items}
        )
        avg_confidence = 0.0
        confidences = [
            contract_evidence.get("confidence", 0),
            ops_evidence.get("confidence", 0),
        ]
        valid_confidences = [c for c in confidences if c > 0]
        if valid_confidences:
            avg_confidence = sum(valid_confidences) / len(valid_confidences)

        aggregate_evidence = EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            domains=combined_domains,
            evidence_items=combined_items,
            total_items=len(combined_items),
            confidence=round(avg_confidence, 3),
        )

        return {
            "all_links": all_links,
            "all_conflicts": all_conflicts,
            "aggregate_evidence": aggregate_evidence.model_dump(),
            "contract_to_wo": contract_to_wo,
            "wo_to_incident": wo_to_incident,
        }

    # -- Helpers --

    @staticmethod
    def _collect_contract_objects(contract_data: dict) -> list[dict]:
        """Flatten the various contract sub-objects into a uniform list."""
        objects: list[dict] = []

        for entry in contract_data.get("rate_card", []):
            obj = dict(entry) if isinstance(entry, dict) else entry
            if isinstance(obj, dict):
                obj.setdefault("type", "rate_card")
                objects.append(obj)

        for obligation in contract_data.get("obligations", []):
            obj = dict(obligation) if isinstance(obligation, dict) else obligation
            if isinstance(obj, dict):
                obj.setdefault("type", "obligation")
                objects.append(obj)

        for boundary in contract_data.get("scope_boundaries", []):
            obj = dict(boundary) if isinstance(boundary, dict) else boundary
            if isinstance(obj, dict):
                obj.setdefault("type", "scope_boundary")
                objects.append(obj)

        # Include any explicitly provided control objects
        for co in contract_data.get("control_objects", []):
            if isinstance(co, dict):
                objects.append(co)

        return objects
