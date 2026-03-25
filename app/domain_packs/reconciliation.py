"""Cross-pack reconciliation module.

Links control objects across the commercial (contract_margin), field
(utilities_field), and operations (telco_ops) domains. Provides linkers for
detecting relationships and conflicts between domain objects and assemblers
for building evidence bundles used in downstream diagnosis and decision-making.
"""

from __future__ import annotations

import dataclasses
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


# ---------------------------------------------------------------------------
# SPEN / Vodafone domain-hardened linkers
# ---------------------------------------------------------------------------


class FieldCompletionBillabilityLinker:
    """Links field completion state to billability determination."""

    def evaluate(
        self,
        work_order: dict,
        completion_evidence: list[dict],
        billing_gates: list[dict],
        reattendance_info: dict | None = None,
    ) -> dict:
        """
        Check if completed field work is actually billable.

        Returns dict with: billable (bool), blockers (list), leakage_triggers (list)

        Rules:
        1. If completion evidence is missing required items -> non-billable
        2. If billing gates not all satisfied -> non-billable
        3. If reattendance due to provider fault -> non-billable
        4. If abortive visit (customer no-access) -> billable as abortive_visit category
        5. If daywork sheet not signed -> non-billable
        6. If variation work without change order -> non-billable, leakage trigger
        """
        blockers: list[dict] = []
        leakage_triggers: list[dict] = []
        billable = True
        category = work_order.get("category", "standard")

        # Rule 1: completion evidence check
        required_evidence_types = set(work_order.get("required_evidence_types", []))
        provided_evidence_types = {
            e.get("evidence_type", e.get("type", ""))
            for e in completion_evidence
            if e.get("provided", False)
        }
        missing_evidence = required_evidence_types - provided_evidence_types
        if missing_evidence:
            billable = False
            blockers.append({
                "rule": "missing_completion_evidence",
                "description": f"Missing required evidence: {', '.join(sorted(missing_evidence))}",
                "severity": "error",
            })
            leakage_triggers.append({
                "trigger_type": "incomplete_evidence_prevents_billing",
                "description": f"Cannot invoice — missing evidence: {', '.join(sorted(missing_evidence))}",
                "severity": "error",
            })

        # Rule 2: billing gates
        unsatisfied_gates = [
            g for g in billing_gates
            if not g.get("satisfied", False)
        ]
        if unsatisfied_gates:
            billable = False
            for gate in unsatisfied_gates:
                blockers.append({
                    "rule": "billing_gate_unsatisfied",
                    "gate_type": gate.get("gate_type", "unknown"),
                    "description": gate.get("description", "Billing gate not satisfied"),
                    "severity": "error",
                })

        # Rule 3: reattendance — provider fault
        if reattendance_info:
            trigger = reattendance_info.get("trigger", "")
            if trigger == "provider_fault":
                billable = False
                blockers.append({
                    "rule": "reattendance_provider_fault",
                    "description": "Re-attendance caused by provider fault — non-billable",
                    "severity": "error",
                })
                if reattendance_info.get("billed", False):
                    leakage_triggers.append({
                        "trigger_type": "reattendance_incorrectly_billed",
                        "description": "Provider-fault re-visit was billed to customer",
                        "severity": "critical",
                    })

            # Rule 4: abortive visit
            elif trigger == "customer_no_access":
                billable = True
                category = "abortive_visit"

        # Rule 5: daywork sheet
        if work_order.get("category") == "daywork" and not work_order.get("daywork_sheet_signed", False):
            billable = False
            blockers.append({
                "rule": "daywork_sheet_not_signed",
                "description": "Daywork sheet not signed — cannot invoice",
                "severity": "error",
            })

        # Rule 6: variation without change order
        if work_order.get("is_variation", False) and not work_order.get("variation_order_ref"):
            billable = False
            blockers.append({
                "rule": "variation_no_change_order",
                "description": "Variation work without formal change order — non-billable",
                "severity": "error",
            })
            leakage_triggers.append({
                "trigger_type": "variation_work_unbilled",
                "description": "Out-of-scope variation work done without variation order — cannot bill",
                "severity": "error",
            })

        return {
            "billable": billable,
            "category": category,
            "blockers": blockers,
            "leakage_triggers": leakage_triggers,
        }


class TicketClosureHandoverLinker:
    """Links incident ticket closure to field handover state."""

    def evaluate(
        self,
        incident: dict,
        work_order: dict,
        completion_evidence: list[dict],
        closure_gates: list[dict],
    ) -> dict:
        """
        Check if ticket can be closed based on field handover state.

        Returns dict with: can_close (bool), blockers (list), mismatches (list)

        Rules:
        1. If incident resolved but field completion evidence missing -> cannot close
        2. If work order status != "completed" but ticket state = "resolved" -> mismatch
        3. If P1/P2 ticket: RCA must be submitted before closure
        4. If work order has open permits -> cannot close (permit not closed out)
        5. If customer sign-off required but not obtained -> cannot close
        """
        blockers: list[dict] = []
        mismatches: list[dict] = []
        can_close = True

        inc_state = _safe_str(incident.get("state", ""))
        inc_severity = _safe_str(incident.get("severity", ""))
        wo_status = _safe_str(work_order.get("status", ""))

        # Rule 1: incident resolved but no completion evidence
        if inc_state in ("resolved", "closed"):
            has_evidence = any(e.get("provided", False) for e in completion_evidence)
            if not has_evidence:
                can_close = False
                blockers.append({
                    "rule": "missing_completion_evidence",
                    "description": "Incident resolved but field completion evidence not provided",
                    "severity": "error",
                })

        # Rule 2: state mismatch
        if inc_state == "resolved" and wo_status and wo_status != "completed":
            can_close = False
            mismatches.append({
                "field": "state_alignment",
                "incident_value": inc_state,
                "work_order_value": wo_status,
                "severity": "error",
                "description": f"Ticket is '{inc_state}' but work order is '{wo_status}'",
            })

        # Rule 3: P1/P2 require RCA
        if inc_severity in ("p1", "p2"):
            rca_submitted = any(
                g.get("prerequisite") == "rca_submitted" and g.get("satisfied", False)
                for g in closure_gates
            )
            if not rca_submitted:
                can_close = False
                blockers.append({
                    "rule": "rca_not_submitted",
                    "description": f"{inc_severity.upper()} ticket requires RCA before closure",
                    "severity": "error",
                })

        # Rule 4: open permits
        open_permits = [
            g for g in closure_gates
            if g.get("prerequisite") == "permit_closed_out"
            and not g.get("satisfied", False)
        ]
        if open_permits:
            can_close = False
            blockers.append({
                "rule": "open_permits",
                "description": "Work order has permits not closed out",
                "severity": "error",
            })

        # Rule 5: customer sign-off
        needs_sign_off = any(
            g.get("prerequisite") == "customer_sign_off" for g in closure_gates
        )
        has_sign_off = any(
            g.get("prerequisite") == "customer_sign_off" and g.get("satisfied", False)
            for g in closure_gates
        )
        if needs_sign_off and not has_sign_off:
            can_close = False
            blockers.append({
                "rule": "customer_sign_off_missing",
                "description": "Customer sign-off required but not obtained",
                "severity": "error",
            })

        return {
            "can_close": can_close,
            "blockers": blockers,
            "mismatches": mismatches,
        }


class SLAAccountabilityLinker:
    """Determines SLA accountability when field blockers exist."""

    def evaluate(
        self,
        sla_status: dict,
        field_blockers: list[dict],
        contract_assumptions: list[dict],
    ) -> dict:
        """
        Determine if SLA breach is provider-accountable or has mitigating factors.

        Returns dict with: accountable (bool), mitigation_factors (list), adjusted_sla_status (str)

        Rules:
        1. Access blocker caused by customer -> SLA clock paused (not accountable)
        2. Permit delay caused by local authority -> SLA clock paused
        3. Weather event (force majeure) -> SLA exclusion applies
        4. Material supply failure by customer-nominated supplier -> not accountable
        5. Third-party dependency (DNO, council) -> partial mitigation
        6. Provider's own resource shortage -> fully accountable
        """
        mitigation_factors: list[dict] = []
        accountable = True
        adjusted_status = sla_status.get("status", "within")

        blocker_type_map = {
            "customer_access": {
                "accountable": False,
                "mitigation": "SLA clock paused — customer access blocker",
                "adjusted_status": "paused",
            },
            "local_authority_permit": {
                "accountable": False,
                "mitigation": "SLA clock paused — local authority permit delay",
                "adjusted_status": "paused",
            },
            "weather_force_majeure": {
                "accountable": False,
                "mitigation": "SLA exclusion — force majeure weather event",
                "adjusted_status": "excluded",
            },
            "customer_nominated_supplier": {
                "accountable": False,
                "mitigation": "Material supply failure by customer-nominated supplier",
                "adjusted_status": "paused",
            },
            "third_party_dependency": {
                "accountable": True,
                "mitigation": "Third-party dependency (DNO/council) — partial mitigation",
                "adjusted_status": "mitigated",
            },
            "provider_resource_shortage": {
                "accountable": True,
                "mitigation": None,
                "adjusted_status": None,
            },
        }

        has_non_accountable = False
        fully_accountable_only = True

        for blocker in field_blockers:
            blocker_type = blocker.get("blocker_type", "")
            mapping = blocker_type_map.get(blocker_type)
            if mapping:
                if not mapping["accountable"]:
                    has_non_accountable = True
                    fully_accountable_only = False
                    mitigation_factors.append({
                        "blocker_type": blocker_type,
                        "mitigation": mapping["mitigation"],
                        "description": blocker.get("description", ""),
                    })
                    if mapping["adjusted_status"]:
                        adjusted_status = mapping["adjusted_status"]
                elif mapping["mitigation"]:
                    # Partial mitigation (e.g. third_party_dependency)
                    fully_accountable_only = False
                    mitigation_factors.append({
                        "blocker_type": blocker_type,
                        "mitigation": mapping["mitigation"],
                        "description": blocker.get("description", ""),
                    })
                    if mapping["adjusted_status"]:
                        adjusted_status = mapping["adjusted_status"]

        if has_non_accountable:
            accountable = False
        elif not fully_accountable_only and mitigation_factors:
            # Partial mitigation — still accountable but with factors
            accountable = True

        return {
            "accountable": accountable,
            "mitigation_factors": mitigation_factors,
            "adjusted_sla_status": adjusted_status,
        }


class MarginLeakageReconciler:
    """Comprehensive margin leakage detection across all three planes."""

    def reconcile(
        self,
        contract_data: dict,
        field_data: dict,
        ops_data: dict,
    ) -> dict:
        """
        Full cross-plane margin leakage analysis.

        Returns dict with: leakage_triggers (list), total_at_risk_value (float),
        recommendations (list)

        Specific leakage patterns to detect:
        1.  field_completion_not_billed
        2.  abortive_visit_not_claimed
        3.  emergency_billed_at_base_rate
        4.  reattendance_incorrectly_billed
        5.  permit_cost_not_recovered
        6.  rate_escalation_not_applied
        7.  variation_work_unbilled
        8.  sla_credit_not_deducted
        9.  incomplete_evidence_prevents_billing
        10. duplicate_claim_risk
        """
        triggers: list[dict] = []
        total_at_risk = 0.0
        recommendations: list[str] = []

        work_orders = field_data.get("work_orders", [])
        invoices = contract_data.get("invoices", [])
        rate_card = contract_data.get("rate_card", [])
        sla_breaches = ops_data.get("sla_breaches", [])

        # Build lookup sets
        invoiced_wo_ids = {inv.get("work_order_id") for inv in invoices}
        rate_map: dict[str, dict] = {}
        for rc in rate_card:
            activity = _safe_str(rc.get("activity", ""))
            if activity:
                rate_map[activity.lower()] = rc

        for wo in work_orders:
            wo_id = wo.get("work_order_id", "")
            wo_status = wo.get("status", "")
            wo_activity = _safe_str(wo.get("activity", ""))
            wo_value = _safe_float(wo.get("value", wo.get("estimated_value", 0)))

            # 1. field_completion_not_billed
            if wo_status == "completed" and wo_id not in invoiced_wo_ids:
                triggers.append({
                    "trigger_type": "field_completion_not_billed",
                    "work_order_id": wo_id,
                    "description": f"Work order {wo_id} completed but no invoice raised",
                    "severity": "error",
                    "at_risk_value": wo_value,
                })
                total_at_risk += wo_value
                recommendations.append(f"Raise invoice for completed work order {wo_id}")

            # 2. abortive_visit_not_claimed
            if wo.get("abortive", False) and not wo.get("abortive_claimed", False):
                abortive_value = _safe_float(wo.get("abortive_value", 0))
                triggers.append({
                    "trigger_type": "abortive_visit_not_claimed",
                    "work_order_id": wo_id,
                    "description": f"Abortive visit for {wo_id} not claimed",
                    "severity": "warning",
                    "at_risk_value": abortive_value,
                })
                total_at_risk += abortive_value
                recommendations.append(f"Claim abortive visit charge for {wo_id}")

            # 3. emergency_billed_at_base_rate
            if wo.get("is_emergency", False):
                billed_rate = _safe_float(wo.get("billed_rate", 0))
                rc = rate_map.get(wo_activity.lower(), {})
                base_rate = _safe_float(rc.get("rate", rc.get("base_rate", 0)))
                emergency_multiplier = _safe_float(rc.get("emergency_multiplier", 1.5))
                expected_rate = base_rate * emergency_multiplier
                if billed_rate > 0 and base_rate > 0 and billed_rate < expected_rate * 0.99:
                    diff = expected_rate - billed_rate
                    triggers.append({
                        "trigger_type": "emergency_billed_at_base_rate",
                        "work_order_id": wo_id,
                        "description": (
                            f"Emergency callout billed at {billed_rate} "
                            f"instead of expected {expected_rate}"
                        ),
                        "severity": "error",
                        "at_risk_value": diff,
                    })
                    total_at_risk += diff
                    recommendations.append(
                        f"Rebill {wo_id} at emergency rate ({expected_rate})"
                    )

            # 4. reattendance_incorrectly_billed
            reattendance = wo.get("reattendance_info", {})
            if reattendance.get("trigger") == "provider_fault" and reattendance.get("billed", False):
                triggers.append({
                    "trigger_type": "reattendance_incorrectly_billed",
                    "work_order_id": wo_id,
                    "description": f"Provider-fault re-visit {wo_id} billed to customer",
                    "severity": "critical",
                    "at_risk_value": wo_value,
                })
                total_at_risk += wo_value
                recommendations.append(f"Issue credit note for incorrectly billed rework {wo_id}")

            # 5. permit_cost_not_recovered
            permit_cost = _safe_float(wo.get("permit_cost", 0))
            if permit_cost > 0 and not wo.get("permit_cost_recovered", False):
                triggers.append({
                    "trigger_type": "permit_cost_not_recovered",
                    "work_order_id": wo_id,
                    "description": f"NRSWA permit cost {permit_cost:.2f} not passed through",
                    "severity": "warning",
                    "at_risk_value": permit_cost,
                })
                total_at_risk += permit_cost
                recommendations.append(f"Recover permit cost {permit_cost:.2f} for {wo_id}")

            # 6. rate_escalation_not_applied
            if wo.get("escalation_due", False) and not wo.get("escalation_applied", False):
                contract_rate = _safe_float(wo.get("contract_rate", 0))
                esc_pct = _safe_float(wo.get("escalation_percentage", 0))
                volume = _safe_float(wo.get("volume", 1))
                delta = contract_rate * esc_pct / 100.0 * volume
                if delta > 0:
                    triggers.append({
                        "trigger_type": "rate_escalation_not_applied",
                        "work_order_id": wo_id,
                        "description": f"Annual rate escalation not applied — under-recovery {delta:.2f}",
                        "severity": "warning",
                        "at_risk_value": delta,
                    })
                    total_at_risk += delta
                    recommendations.append(f"Apply rate escalation for {wo_id}")

            # 7. variation_work_unbilled
            if wo.get("is_variation", False) and not wo.get("variation_order_ref"):
                triggers.append({
                    "trigger_type": "variation_work_unbilled",
                    "work_order_id": wo_id,
                    "description": f"Variation work on {wo_id} without variation order — cannot bill",
                    "severity": "error",
                    "at_risk_value": wo_value,
                })
                total_at_risk += wo_value
                recommendations.append(f"Raise variation order for {wo_id} before invoicing")

            # 9. incomplete_evidence_prevents_billing
            required_evidence = set(wo.get("required_evidence_types", []))
            provided_evidence = {
                e.get("evidence_type", "")
                for e in wo.get("completion_evidence", [])
                if e.get("provided", False)
            }
            missing = required_evidence - provided_evidence
            if missing and wo_status == "completed":
                triggers.append({
                    "trigger_type": "incomplete_evidence_prevents_billing",
                    "work_order_id": wo_id,
                    "description": f"Missing evidence ({', '.join(sorted(missing))}) prevents invoicing",
                    "severity": "error",
                    "at_risk_value": wo_value,
                })
                total_at_risk += wo_value
                recommendations.append(f"Collect missing evidence for {wo_id}")

        # 8. sla_credit_not_deducted
        for breach in sla_breaches:
            if not breach.get("credit_applied", False):
                credit_value = _safe_float(breach.get("credit_value", 0))
                triggers.append({
                    "trigger_type": "sla_credit_not_deducted",
                    "incident_id": breach.get("incident_id", ""),
                    "description": f"SLA breach but service credit not applied",
                    "severity": "warning",
                    "at_risk_value": credit_value,
                })
                total_at_risk += credit_value
                recommendations.append("Apply SLA service credit for breach")

        # 10. duplicate_claim_risk
        activity_wo_map: dict[str, list[str]] = {}
        for wo in work_orders:
            key = (
                _safe_str(wo.get("activity", "")).lower()
                + "|"
                + _safe_str(wo.get("location", "")).lower()
                + "|"
                + _safe_str(wo.get("scheduled_date", ""))
            )
            if key and key != "||":
                activity_wo_map.setdefault(key, []).append(wo.get("work_order_id", ""))
        for key, wo_ids in activity_wo_map.items():
            if len(wo_ids) > 1:
                triggers.append({
                    "trigger_type": "duplicate_claim_risk",
                    "work_order_ids": wo_ids,
                    "description": f"Possible duplicate claim across work orders: {', '.join(wo_ids)}",
                    "severity": "warning",
                    "at_risk_value": 0.0,
                })
                recommendations.append(f"Review potential duplicate: {', '.join(wo_ids)}")

        return {
            "leakage_triggers": triggers,
            "total_at_risk_value": round(total_at_risk, 2),
            "recommendations": recommendations,
        }


# ---------------------------------------------------------------------------
# MarginDiagnosisBundle dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class MarginDiagnosisBundle:
    """Complete output from MarginDiagnosisReconciler."""

    contract_wo_links: list[CrossPlaneLink]
    wo_incident_links: list[CrossPlaneLink]
    field_billing_conflicts: list[CrossPlaneConflict]
    sla_conflicts: list[CrossPlaneConflict]
    leakage_patterns: list[dict]
    evidence_bundle: EvidenceBundle
    all_conflicts: list[CrossPlaneConflict]
    verdict: str  # "healthy", "leakage_detected", "penalty_risk", "under_recovery"
    confidence: float
    summary: str


# ---------------------------------------------------------------------------
# ContradictionDetector
# ---------------------------------------------------------------------------


class ContradictionDetector:
    """Detect contradictions between domain planes.

    Examples:
    - Contract says in-scope but field completion says out-of-scope
    - Work order says completed but incident says service still degraded
    - Rate card says X but billing says Y
    - Contract says approval required but work executed without approval
    - SLA says within threshold but penalty triggered
    """

    def detect(
        self,
        contract_data: dict,
        field_data: dict,
        incident_data: dict | None = None,
    ) -> list[CrossPlaneConflict]:
        conflicts: list[CrossPlaneConflict] = []

        # --- Scope contradiction ---
        # Contract says in-scope but field data says out-of-scope or vice versa
        scope_boundaries = contract_data.get("scope_boundaries", [])
        wo_description = _safe_str(field_data.get("description", ""))
        wo_activities = _extract_activities(wo_description)
        field_scope = _safe_str(field_data.get("scope_status", ""))

        for boundary in scope_boundaries:
            scope_type = _safe_str(boundary.get("scope_type", ""))
            scope_activities = set(
                a.lower().strip() for a in boundary.get("activities", [])
            )
            overlap = scope_activities & wo_activities

            if scope_type == "in_scope" and field_scope == "out_of_scope" and overlap:
                conflicts.append(
                    CrossPlaneConflict(
                        field="scope",
                        domain_a=DOMAIN_CONTRACT_MARGIN,
                        value_a=f"in_scope: {', '.join(sorted(overlap))}",
                        domain_b=DOMAIN_UTILITIES_FIELD,
                        value_b=f"field reports out_of_scope",
                        severity="error",
                        resolution="Contract defines activities as in-scope but field execution flagged them as out-of-scope. Clarify scope with contract team.",
                    )
                )
            elif scope_type == "out_of_scope" and field_scope == "in_scope" and overlap:
                conflicts.append(
                    CrossPlaneConflict(
                        field="scope",
                        domain_a=DOMAIN_CONTRACT_MARGIN,
                        value_a=f"out_of_scope: {', '.join(sorted(overlap))}",
                        domain_b=DOMAIN_UTILITIES_FIELD,
                        value_b=f"field reports in_scope",
                        severity="error",
                        resolution="Contract defines activities as out-of-scope but field executed them as in-scope. May indicate unauthorised work.",
                    )
                )

        # --- Completion vs incident contradiction ---
        if incident_data:
            wo_status = _safe_str(field_data.get("status", ""))
            inc_state = _safe_str(incident_data.get("state", ""))
            inc_severity = _safe_str(incident_data.get("severity", ""))

            # Work order completed but incident still active/degraded
            if wo_status == "completed" and inc_state in ("new", "investigating", "in_progress"):
                conflicts.append(
                    CrossPlaneConflict(
                        field="completion_vs_incident",
                        domain_a=DOMAIN_UTILITIES_FIELD,
                        value_a=f"status={wo_status}",
                        domain_b=DOMAIN_TELCO_OPS,
                        value_b=f"state={inc_state}",
                        severity="error",
                        resolution="Work order marked completed but related incident still active. Verify field resolution was effective.",
                    )
                )

            # Incident resolved but work order still open
            if inc_state in ("resolved", "closed") and wo_status in ("pending", "in_progress", "assigned"):
                conflicts.append(
                    CrossPlaneConflict(
                        field="completion_vs_incident",
                        domain_a=DOMAIN_TELCO_OPS,
                        value_a=f"state={inc_state}",
                        domain_b=DOMAIN_UTILITIES_FIELD,
                        value_b=f"status={wo_status}",
                        severity="warning",
                        resolution="Incident resolved/closed but work order still open. Update work order status.",
                    )
                )

        # --- Rate contradiction ---
        rate_card = contract_data.get("rate_card", [])
        field_rate = _safe_float(field_data.get("rate", field_data.get("billed_rate", 0)))
        field_activity = _safe_str(field_data.get("activity", field_data.get("work_order_type", "")))

        if field_rate > 0 and field_activity:
            for rc in rate_card:
                rc_activity = _safe_str(rc.get("activity", ""))
                rc_rate = _safe_float(rc.get("rate", 0))
                if rc_rate > 0 and rc_activity:
                    sim = _text_similarity(rc_activity, field_activity)
                    if sim >= _TEXT_SIMILARITY_THRESHOLD:
                        diff = abs(rc_rate - field_rate)
                        tolerance = rc_rate * _RATE_TOLERANCE_FRACTION
                        if diff > tolerance:
                            conflicts.append(
                                CrossPlaneConflict(
                                    field="rate",
                                    domain_a=DOMAIN_CONTRACT_MARGIN,
                                    value_a=str(rc_rate),
                                    domain_b=DOMAIN_UTILITIES_FIELD,
                                    value_b=str(field_rate),
                                    severity="critical" if diff / rc_rate > 0.10 else "warning",
                                    resolution=f"Rate mismatch: contract specifies {rc_rate} but field/billing shows {field_rate}. Difference of {diff:.2f}.",
                                )
                            )

        # --- Approval contradiction ---
        requires_approval = contract_data.get("requires_approval", False)
        approval_obtained = field_data.get("approval_obtained", True)
        if requires_approval and not approval_obtained:
            conflicts.append(
                CrossPlaneConflict(
                    field="approval",
                    domain_a=DOMAIN_CONTRACT_MARGIN,
                    value_a="approval_required=True",
                    domain_b=DOMAIN_UTILITIES_FIELD,
                    value_b="approval_obtained=False",
                    severity="error",
                    resolution="Contract requires approval before work execution but approval was not obtained.",
                )
            )

        # --- SLA contradiction ---
        sla_status = contract_data.get("sla_status", "")
        penalty_triggered = contract_data.get("penalty_triggered", False)
        if sla_status == "within" and penalty_triggered:
            conflicts.append(
                CrossPlaneConflict(
                    field="sla_penalty",
                    domain_a=DOMAIN_CONTRACT_MARGIN,
                    value_a="sla_status=within",
                    domain_b=DOMAIN_CONTRACT_MARGIN,
                    value_b="penalty_triggered=True",
                    severity="error",
                    resolution="SLA reported as within threshold but penalty was triggered. Reconcile SLA measurement.",
                )
            )

        return conflicts


# ---------------------------------------------------------------------------
# EvidenceChainValidator
# ---------------------------------------------------------------------------


class EvidenceChainValidator:
    """Validate that evidence chains are complete for a margin diagnosis.

    A complete chain requires:
    1. Contract basis (rate card entry or obligation)
    2. Work authorization (work order or purchase order)
    3. Execution evidence (completion certificate, daywork sheet, field log)
    4. Billing evidence (invoice, billing gate satisfaction)

    Missing links in the chain produce warnings or blockers.
    """

    # The four required stages in an evidence chain
    CHAIN_STAGES = [
        {
            "stage": "contract_basis",
            "label": "Contract Basis",
            "required_types": {"rate_card", "obligation", "contract_object"},
        },
        {
            "stage": "work_authorization",
            "label": "Work Authorization",
            "required_types": {"work_order", "purchase_order", "dispatch_precondition"},
        },
        {
            "stage": "execution_evidence",
            "label": "Execution Evidence",
            "required_types": {"completion_certificate", "daywork_sheet", "field_log", "completion_evidence"},
        },
        {
            "stage": "billing_evidence",
            "label": "Billing Evidence",
            "required_types": {"invoice", "billing_gate", "billing_confirmation"},
        },
    ]

    def validate_chain(self, evidence_bundle: EvidenceBundle) -> list[dict]:
        """Return list of chain validation results.

        Each result is a dict with:
        - stage: str
        - label: str
        - present: bool
        - severity: str ("ok", "warning", "blocker")
        - message: str
        """
        results: list[dict] = []
        item_types = {
            _safe_str(item.get("type", "")).lower()
            for item in evidence_bundle.evidence_items
        }

        for stage_def in self.CHAIN_STAGES:
            stage = stage_def["stage"]
            label = stage_def["label"]
            required_types = stage_def["required_types"]

            # Check if any required type is present
            present = bool(item_types & required_types)

            if present:
                results.append({
                    "stage": stage,
                    "label": label,
                    "present": True,
                    "severity": "ok",
                    "message": f"{label} evidence found.",
                })
            else:
                # Contract basis and work authorization are blockers; the rest are warnings
                if stage in ("contract_basis", "work_authorization"):
                    severity = "blocker"
                    message = f"Missing {label} -- cannot produce reliable margin diagnosis."
                else:
                    severity = "warning"
                    message = f"Missing {label} -- margin diagnosis may be incomplete."
                results.append({
                    "stage": stage,
                    "label": label,
                    "present": False,
                    "severity": severity,
                    "message": message,
                })

        return results


# ---------------------------------------------------------------------------
# MarginDiagnosisReconciler
# ---------------------------------------------------------------------------


class MarginDiagnosisReconciler:
    """Full margin diagnosis reconciler combining all three domain planes.

    Orchestrates: ContractWorkOrderLinker, WorkOrderIncidentLinker,
    MarginEvidenceAssembler, FieldCompletionBillabilityLinker,
    SLAAccountabilityLinker, MarginLeakageReconciler to produce
    a comprehensive margin diagnosis.
    """

    def __init__(self) -> None:
        self.contract_wo_linker = ContractWorkOrderLinker()
        self.wo_incident_linker = WorkOrderIncidentLinker()
        self.margin_evidence = MarginEvidenceAssembler()
        self.field_billing_linker = FieldCompletionBillabilityLinker()
        self.sla_linker = SLAAccountabilityLinker()
        self.leakage_reconciler = MarginLeakageReconciler()
        self.contradiction_detector = ContradictionDetector()
        self.chain_validator = EvidenceChainValidator()

    def reconcile(
        self,
        contract_objects: list[dict],
        work_orders: list[dict],
        incidents: list[dict] | None = None,
        work_history: list[dict] | None = None,
        sla_performance: dict | None = None,
    ) -> MarginDiagnosisBundle:
        """Run full cross-plane reconciliation for margin diagnosis.

        Steps:
        1. Link contracts to work orders
        2. Link work orders to incidents (if incidents provided)
        3. Run field-completion-to-billability checks
        4. Run SLA accountability checks
        5. Run margin leakage detection
        6. Assemble evidence bundle
        7. Detect cross-plane conflicts
        8. Produce final diagnosis bundle
        """
        incidents = incidents or []
        work_history = work_history or []
        sla_performance = sla_performance or {}

        # Build contract data dict for sub-reconcilers
        contract_data = self._build_contract_data(contract_objects)

        # 1. Link contracts to work orders
        all_contract_wo_links: list[CrossPlaneLink] = []
        for wo in work_orders:
            links = self.contract_wo_linker.link(contract_objects, wo)
            all_contract_wo_links.extend(links)

        # 2. Link work orders to incidents
        all_wo_incident_links: list[CrossPlaneLink] = []
        for wo in work_orders:
            links = self.wo_incident_linker.link(wo, incidents)
            all_wo_incident_links.extend(links)

        # 3. Field-completion-to-billability checks
        field_billing_conflicts: list[CrossPlaneConflict] = []
        for wo in work_orders:
            completion_evidence = wo.get("completion_evidence", [])
            billing_gates = wo.get("billing_gates", [])
            reattendance_info = wo.get("reattendance_info")
            fb_result = self.field_billing_linker.evaluate(
                wo, completion_evidence, billing_gates, reattendance_info
            )
            for blocker in fb_result.get("blockers", []):
                field_billing_conflicts.append(
                    CrossPlaneConflict(
                        field=blocker.get("rule", "billing_gate"),
                        domain_a=DOMAIN_UTILITIES_FIELD,
                        value_a=_safe_str(wo.get("work_order_id", "")),
                        domain_b=DOMAIN_CONTRACT_MARGIN,
                        value_b=blocker.get("description", ""),
                        severity=blocker.get("severity", "error"),
                        resolution=f"Resolve billing blocker: {blocker.get('description', '')}",
                    )
                )

        # 4. SLA accountability checks
        sla_conflicts: list[CrossPlaneConflict] = []
        sla_status = sla_performance.get("sla_status", {})
        field_blockers = sla_performance.get("field_blockers", [])
        contract_assumptions = sla_performance.get("contract_assumptions", [])
        if sla_status or field_blockers:
            sla_result = self.sla_linker.evaluate(
                sla_status, field_blockers, contract_assumptions
            )
            if sla_result.get("accountable", False) and sla_status.get("status") == "breached":
                sla_conflicts.append(
                    CrossPlaneConflict(
                        field="sla_accountability",
                        domain_a=DOMAIN_TELCO_OPS,
                        value_a=f"sla_breached",
                        domain_b=DOMAIN_CONTRACT_MARGIN,
                        value_b=f"provider_accountable",
                        severity="critical",
                        resolution="SLA breached and provider is accountable. Penalty exposure applies.",
                    )
                )
            for factor in sla_result.get("mitigation_factors", []):
                sla_conflicts.append(
                    CrossPlaneConflict(
                        field="sla_mitigation",
                        domain_a=DOMAIN_UTILITIES_FIELD,
                        value_a=factor.get("blocker_type", ""),
                        domain_b=DOMAIN_TELCO_OPS,
                        value_b=factor.get("mitigation", ""),
                        severity="warning",
                        resolution=factor.get("mitigation", "Review SLA mitigation factor."),
                    )
                )

        # 5. Margin leakage detection
        field_data = {"work_orders": work_orders + work_history}
        ops_data = {"sla_breaches": sla_performance.get("sla_breaches", [])}
        leakage_result = self.leakage_reconciler.reconcile(
            contract_data, field_data, ops_data
        )
        leakage_patterns = leakage_result.get("leakage_triggers", [])

        # 6. Assemble evidence bundle
        leakage_trigger_dicts = [
            {
                "trigger_type": t.get("trigger_type", ""),
                "description": t.get("description", ""),
                "severity": t.get("severity", "warning"),
            }
            for t in leakage_patterns
        ]
        evidence_bundle = self.margin_evidence.assemble(
            contract_objects, work_orders + work_history, leakage_trigger_dicts
        )

        # 7. Detect cross-plane contradictions
        contradiction_conflicts: list[CrossPlaneConflict] = []
        for wo in work_orders:
            primary_incident = incidents[0] if incidents else None
            detected = self.contradiction_detector.detect(
                contract_data, wo, primary_incident
            )
            contradiction_conflicts.extend(detected)

        # Aggregate all conflicts
        all_conflicts = (
            field_billing_conflicts
            + sla_conflicts
            + contradiction_conflicts
        )

        # 8. Determine verdict
        verdict = self._determine_verdict(
            leakage_patterns, all_conflicts, sla_conflicts
        )
        confidence = self._compute_confidence(
            contract_objects, work_orders, incidents, evidence_bundle, all_conflicts
        )
        summary = self._build_summary(
            verdict, leakage_patterns, all_conflicts, evidence_bundle
        )

        return MarginDiagnosisBundle(
            contract_wo_links=all_contract_wo_links,
            wo_incident_links=all_wo_incident_links,
            field_billing_conflicts=field_billing_conflicts,
            sla_conflicts=sla_conflicts,
            leakage_patterns=leakage_patterns,
            evidence_bundle=evidence_bundle,
            all_conflicts=all_conflicts,
            verdict=verdict,
            confidence=round(confidence, 3),
            summary=summary,
        )

    # ---- Internal helpers ----

    @staticmethod
    def _build_contract_data(contract_objects: list[dict]) -> dict:
        """Reshape flat contract objects into the dict format expected by sub-reconcilers."""
        rate_card: list[dict] = []
        obligations: list[dict] = []
        scope_boundaries: list[dict] = []
        invoices: list[dict] = []

        for obj in contract_objects:
            obj_type = _safe_str(
                obj.get("type", obj.get("control_type", obj.get("object_type", "")))
            )
            if obj_type in ("rate_card", "rate", "billable_event"):
                rate_card.append(obj)
            elif obj_type in ("obligation", "sla"):
                obligations.append(obj)
            elif obj_type in ("scope", "scope_boundary"):
                scope_boundaries.append(obj)
            elif obj_type == "invoice":
                invoices.append(obj)

        return {
            "rate_card": rate_card,
            "obligations": obligations,
            "scope_boundaries": scope_boundaries,
            "invoices": invoices,
        }

    @staticmethod
    def _determine_verdict(
        leakage_patterns: list[dict],
        all_conflicts: list[CrossPlaneConflict],
        sla_conflicts: list[CrossPlaneConflict],
    ) -> str:
        # Penalty risk takes precedence
        has_penalty_risk = any(
            c.field == "sla_accountability" and c.severity == "critical"
            for c in sla_conflicts
        )
        if has_penalty_risk:
            return "penalty_risk"

        # Leakage detected
        if leakage_patterns:
            critical_leakage = any(
                t.get("severity") in ("error", "critical") for t in leakage_patterns
            )
            if critical_leakage:
                return "under_recovery"
            return "leakage_detected"

        # Conflicts present but no leakage
        if all_conflicts:
            critical_conflicts = any(
                c.severity in ("error", "critical") for c in all_conflicts
            )
            if critical_conflicts:
                return "under_recovery"
            return "leakage_detected"

        return "healthy"

    @staticmethod
    def _compute_confidence(
        contract_objects: list[dict],
        work_orders: list[dict],
        incidents: list[dict],
        evidence_bundle: EvidenceBundle,
        all_conflicts: list[CrossPlaneConflict],
    ) -> float:
        score = 0.0
        # Evidence breadth
        if contract_objects:
            score += 0.25
        if work_orders:
            score += 0.25
        if incidents:
            score += 0.15
        # Evidence bundle confidence contribution
        score += 0.15 * evidence_bundle.confidence
        # Conflicts reduce confidence
        if all_conflicts:
            score -= 0.05 * min(len(all_conflicts), 4)
        # Baseline
        score += 0.10
        return max(min(score, 1.0), 0.1)

    @staticmethod
    def _build_summary(
        verdict: str,
        leakage_patterns: list[dict],
        all_conflicts: list[CrossPlaneConflict],
        evidence_bundle: EvidenceBundle,
    ) -> str:
        parts: list[str] = [f"Margin diagnosis verdict: {verdict}."]
        if leakage_patterns:
            parts.append(f"{len(leakage_patterns)} leakage pattern(s) detected.")
        if all_conflicts:
            parts.append(f"{len(all_conflicts)} cross-plane conflict(s) found.")
        parts.append(
            f"Evidence bundle contains {evidence_bundle.total_items} item(s) "
            f"across {len(evidence_bundle.domains)} domain(s) "
            f"(confidence: {evidence_bundle.confidence:.2f})."
        )
        return " ".join(parts)
