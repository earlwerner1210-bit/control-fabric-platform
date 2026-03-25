"""Contract & Margin compiler — compile parsed contracts into control objects."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.domain_packs.contract_margin.schemas import (
    ParsedContract, ExtractedClause, ClauseSegment, SLAEntry, RateCardEntry,
    Obligation, PenaltyCondition, BillableEvent, ScopeBoundaryObject,
    ClauseType,
)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class ContractCompileResult:
    """Container for all compiled control objects from a parsed contract."""

    clauses: list[dict] = field(default_factory=list)
    sla_entries: list[dict] = field(default_factory=list)
    rate_card_entries: list[dict] = field(default_factory=list)
    obligations: list[dict] = field(default_factory=list)
    penalties: list[dict] = field(default_factory=list)
    scope_boundaries: list[dict] = field(default_factory=list)
    control_object_payloads: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Risk-level mapping helpers
# ---------------------------------------------------------------------------

_CLAUSE_TYPE_RISK_MAP: dict[str, str] = {
    ClauseType.penalty.value: "high",
    ClauseType.liability.value: "high",
    ClauseType.indemnity.value: "high",
    ClauseType.termination.value: "high",
    ClauseType.sla.value: "medium",
    ClauseType.obligation.value: "medium",
    ClauseType.rate.value: "medium",
    ClauseType.scope.value: "medium",
    ClauseType.warranty.value: "medium",
    ClauseType.confidentiality.value: "low",
    ClauseType.force_majeure.value: "low",
    ClauseType.governing_law.value: "low",
    ClauseType.dispute_resolution.value: "low",
}

_DUE_TYPE_RISK_BOOST: dict[str, int] = {
    "one_time": 0,
    "ongoing": 1,
    "periodic": 1,
    "upon_trigger": 2,
}

_PENALTY_TYPE_SEVERITY: dict[str, str] = {
    "percentage": "warning",
    "fixed": "warning",
    "per_breach": "error",
    "tiered": "error",
    "capped": "warning",
}

_RISK_ORDER = ["low", "medium", "high", "critical"]


def _elevate_risk(base_risk: str, boost: int) -> str:
    """Elevate a risk level by *boost* steps, capping at critical."""
    idx = _RISK_ORDER.index(base_risk) if base_risk in _RISK_ORDER else 1
    return _RISK_ORDER[min(idx + boost, len(_RISK_ORDER) - 1)]


# ---------------------------------------------------------------------------
# ContractCompiler
# ---------------------------------------------------------------------------


class ContractCompiler:
    """Compile a parsed contract into typed control objects."""

    # -- public entry point -------------------------------------------------

    def compile(self, contract: ParsedContract) -> ContractCompileResult:
        """Run the full compilation pipeline and return an aggregated result."""
        clauses = self.compile_clauses(contract.clauses, contract.clause_segments)
        sla_entries = self.compile_sla_entries(contract.sla_table)
        rate_card_entries = self.compile_rate_card(contract.rate_card)
        obligations = self.compile_obligations(contract)
        penalties = self.compile_penalties(contract)
        scope_boundaries = self.compile_scope_boundaries(contract.scope_boundaries)

        # Aggregate all payloads for downstream consumers
        control_objects: list[dict] = []
        for clause in clauses:
            control_objects.append({"type": "clause", "payload": clause})
        for sla in sla_entries:
            control_objects.append({"type": "sla_entry", "payload": sla})
        for rc in rate_card_entries:
            control_objects.append({"type": "rate_card_entry", "payload": rc})
        for ob in obligations:
            control_objects.append({"type": "obligation", "payload": ob})
        for pen in penalties:
            control_objects.append({"type": "penalty_condition", "payload": pen})
        for sb in scope_boundaries:
            control_objects.append({"type": "scope_boundary", "payload": sb})

        return ContractCompileResult(
            clauses=clauses,
            sla_entries=sla_entries,
            rate_card_entries=rate_card_entries,
            obligations=obligations,
            penalties=penalties,
            scope_boundaries=scope_boundaries,
            control_object_payloads=control_objects,
        )

    # -- clause compilation -------------------------------------------------

    def compile_clauses(
        self,
        clauses: list[ExtractedClause],
        clause_segments: list[ClauseSegment],
    ) -> list[dict]:
        """Generate clause control objects from parsed clauses and clause segments."""
        results: list[dict] = []

        # Index segments by parent clause id for enrichment
        segments_by_clause: dict[str, list[ClauseSegment]] = {}
        for seg in clause_segments:
            parent_key = seg.parent_clause_id or seg.id
            segments_by_clause.setdefault(parent_key, []).append(seg)

        for clause in clauses:
            related_segments = segments_by_clause.get(clause.id, [])
            risk_level = _CLAUSE_TYPE_RISK_MAP.get(clause.type.value, "medium")

            compiled: dict = {
                "control_id": str(uuid.uuid4()),
                "control_type": "clause",
                "clause_id": clause.id,
                "clause_type": clause.type.value,
                "text": clause.text,
                "section": clause.section,
                "confidence": clause.confidence,
                "risk_level": risk_level,
                "segment_count": len(related_segments),
                "segments": [
                    {
                        "segment_id": seg.id,
                        "clause_number": seg.clause_number,
                        "heading": seg.heading,
                        "text": seg.text,
                        "clause_type": seg.clause_type.value,
                        "section_ref": seg.section_ref,
                        "source_offset_start": seg.source_offset_start,
                        "source_offset_end": seg.source_offset_end,
                        "confidence": seg.confidence,
                        "metadata": seg.metadata,
                    }
                    for seg in related_segments
                ],
            }
            results.append(compiled)

        # Handle orphan segments — segments not linked to any extracted clause
        linked_clause_ids = {c.id for c in clauses}
        for seg in clause_segments:
            parent = seg.parent_clause_id or seg.id
            if parent not in linked_clause_ids and seg.id not in linked_clause_ids:
                risk_level = _CLAUSE_TYPE_RISK_MAP.get(seg.clause_type.value, "medium")
                results.append({
                    "control_id": str(uuid.uuid4()),
                    "control_type": "clause",
                    "clause_id": seg.id,
                    "clause_type": seg.clause_type.value,
                    "text": seg.text,
                    "section": seg.section_ref,
                    "confidence": seg.confidence,
                    "risk_level": risk_level,
                    "segment_count": 1,
                    "segments": [
                        {
                            "segment_id": seg.id,
                            "clause_number": seg.clause_number,
                            "heading": seg.heading,
                            "text": seg.text,
                            "clause_type": seg.clause_type.value,
                            "section_ref": seg.section_ref,
                            "source_offset_start": seg.source_offset_start,
                            "source_offset_end": seg.source_offset_end,
                            "confidence": seg.confidence,
                            "metadata": seg.metadata,
                        }
                    ],
                    "orphan_segment": True,
                })
                # Prevent duplicates
                linked_clause_ids.add(seg.id)

        return results

    # -- SLA compilation ----------------------------------------------------

    def compile_sla_entries(self, sla_table: list[SLAEntry]) -> list[dict]:
        """Generate SLA control objects from the parsed SLA table."""
        results: list[dict] = []

        for entry in sla_table:
            has_penalty = entry.penalty_percentage is not None and entry.penalty_percentage > 0
            severity = "info"
            if entry.response_time_hours <= 1:
                severity = "critical"
            elif entry.response_time_hours <= 4:
                severity = "error"
            elif entry.response_time_hours <= 8:
                severity = "warning"

            results.append({
                "control_id": str(uuid.uuid4()),
                "control_type": "sla_entry",
                "priority": entry.priority,
                "response_time_hours": entry.response_time_hours,
                "resolution_time_hours": entry.resolution_time_hours,
                "availability": entry.availability,
                "penalty_percentage": entry.penalty_percentage,
                "measurement_window": entry.measurement_window,
                "has_penalty_clause": has_penalty,
                "severity": severity,
                "response_to_resolution_ratio": round(
                    entry.response_time_hours / entry.resolution_time_hours, 3
                ) if entry.resolution_time_hours > 0 else 0.0,
            })

        return results

    # -- rate card compilation ----------------------------------------------

    def compile_rate_card(self, rate_card: list[RateCardEntry]) -> list[dict]:
        """Generate rate card control objects."""
        results: list[dict] = []

        for entry in rate_card:
            has_escalation = entry.escalation_rate is not None and entry.escalation_rate > 0
            has_overtime = entry.overtime_multiplier is not None and entry.overtime_multiplier > 1.0
            has_minimum = entry.minimum_charge is not None and entry.minimum_charge > 0

            results.append({
                "control_id": str(uuid.uuid4()),
                "control_type": "rate_card_entry",
                "activity": entry.activity,
                "unit": entry.unit,
                "rate": entry.rate,
                "currency": entry.currency,
                "effective_from": entry.effective_from.isoformat() if entry.effective_from else None,
                "effective_to": entry.effective_to.isoformat() if entry.effective_to else None,
                "escalation_rate": entry.escalation_rate,
                "minimum_charge": entry.minimum_charge,
                "overtime_multiplier": entry.overtime_multiplier,
                "has_escalation_clause": has_escalation,
                "has_overtime_clause": has_overtime,
                "has_minimum_charge": has_minimum,
            })

        return results

    # -- obligation compilation ---------------------------------------------

    def compile_obligations(self, contract: ParsedContract) -> list[dict]:
        """Extract and compile obligation control objects with risk levels and due tracking."""
        results: list[dict] = []

        # Gather obligations from dedicated fields
        obligations = self._extract_obligations_from_clauses(contract)

        for ob in obligations:
            base_risk = ob.risk_level if ob.risk_level in _RISK_ORDER else "medium"
            due_boost = _DUE_TYPE_RISK_BOOST.get(ob.due_type, 0)
            computed_risk = _elevate_risk(base_risk, due_boost)

            has_due_date = ob.due_date is not None
            has_dependencies = len(ob.dependencies) > 0

            results.append({
                "control_id": str(uuid.uuid4()),
                "control_type": "obligation",
                "clause_id": ob.clause_id,
                "description": ob.description,
                "owner": ob.owner,
                "due_type": ob.due_type,
                "risk_level": computed_risk,
                "status": ob.status,
                "due_date": ob.due_date.isoformat() if ob.due_date else None,
                "has_due_date": has_due_date,
                "dependencies": ob.dependencies,
                "has_dependencies": has_dependencies,
                "tracking": {
                    "requires_periodic_review": ob.due_type in ("ongoing", "periodic"),
                    "has_trigger_condition": ob.due_type == "upon_trigger",
                    "overdue": False,  # To be resolved at runtime by due-date checks
                },
            })

        return results

    def _extract_obligations_from_clauses(self, contract: ParsedContract) -> list[Obligation]:
        """Extract obligation objects from clause segments and explicit clause data."""
        obligations: list[Obligation] = []

        # Collect obligation-typed clauses from segments
        for seg in contract.clause_segments:
            if seg.clause_type == ClauseType.obligation:
                obligations.append(Obligation(
                    clause_id=seg.parent_clause_id or seg.id,
                    description=seg.text,
                    owner=seg.metadata.get("owner", ""),
                    due_type=seg.metadata.get("due_type", "ongoing"),
                    risk_level=seg.metadata.get("risk_level", "medium"),
                    status=seg.metadata.get("status", "active"),
                    due_date=seg.metadata.get("due_date"),
                    dependencies=seg.metadata.get("dependencies", []),
                ))

        # Collect obligation-typed extracted clauses not already captured
        captured_clause_ids = {ob.clause_id for ob in obligations}
        for clause in contract.clauses:
            if clause.type == ClauseType.obligation and clause.id not in captured_clause_ids:
                obligations.append(Obligation(
                    clause_id=clause.id,
                    description=clause.text,
                    owner="",
                    due_type="ongoing",
                    risk_level="medium",
                    status="active",
                ))

        return obligations

    # -- penalty compilation ------------------------------------------------

    def compile_penalties(self, contract: ParsedContract) -> list[dict]:
        """Extract and compile penalty condition control objects with triggers and caps."""
        results: list[dict] = []

        penalties = self._extract_penalties_from_clauses(contract)

        for pen in penalties:
            severity = _PENALTY_TYPE_SEVERITY.get(pen.penalty_type, "warning")
            has_cap = pen.cap is not None and pen.cap > 0
            has_grace_period = pen.grace_period_days is not None and pen.grace_period_days > 0
            has_cure_period = pen.cure_period_days is not None and pen.cure_period_days > 0
            has_escalation = len(pen.escalation_schedule) > 0

            results.append({
                "control_id": str(uuid.uuid4()),
                "control_type": "penalty_condition",
                "clause_id": pen.clause_id,
                "description": pen.description,
                "trigger": pen.trigger,
                "penalty_amount": pen.penalty_amount,
                "penalty_type": pen.penalty_type,
                "cap": pen.cap,
                "grace_period_days": pen.grace_period_days,
                "cure_period_days": pen.cure_period_days,
                "escalation_schedule": pen.escalation_schedule,
                "severity": severity,
                "has_cap": has_cap,
                "has_grace_period": has_grace_period,
                "has_cure_period": has_cure_period,
                "has_escalation_schedule": has_escalation,
                "mitigation": {
                    "grace_available": has_grace_period,
                    "cure_available": has_cure_period,
                    "capped": has_cap,
                    "max_exposure": pen.cap if has_cap else None,
                },
            })

        return results

    def _extract_penalties_from_clauses(self, contract: ParsedContract) -> list[PenaltyCondition]:
        """Extract penalty condition objects from clause segments and clause data."""
        penalties: list[PenaltyCondition] = []

        # Collect penalty-typed clauses from segments
        for seg in contract.clause_segments:
            if seg.clause_type == ClauseType.penalty:
                penalties.append(PenaltyCondition(
                    clause_id=seg.parent_clause_id or seg.id,
                    description=seg.text,
                    trigger=seg.metadata.get("trigger", ""),
                    penalty_amount=seg.metadata.get("penalty_amount", ""),
                    penalty_type=seg.metadata.get("penalty_type", ""),
                    cap=seg.metadata.get("cap"),
                    grace_period_days=seg.metadata.get("grace_period_days"),
                    cure_period_days=seg.metadata.get("cure_period_days"),
                    escalation_schedule=seg.metadata.get("escalation_schedule", []),
                ))

        # Collect from extracted clauses not already captured
        captured_clause_ids = {p.clause_id for p in penalties}
        for clause in contract.clauses:
            if clause.type == ClauseType.penalty and clause.id not in captured_clause_ids:
                penalties.append(PenaltyCondition(
                    clause_id=clause.id,
                    description=clause.text,
                ))

        # Also derive penalty data from SLA entries that have penalty percentages
        for sla in contract.sla_table:
            if sla.penalty_percentage is not None and sla.penalty_percentage > 0:
                penalties.append(PenaltyCondition(
                    clause_id=f"sla-{sla.priority}",
                    description=(
                        f"SLA penalty for {sla.priority}: "
                        f"{sla.penalty_percentage}% if response exceeds "
                        f"{sla.response_time_hours}h or resolution exceeds "
                        f"{sla.resolution_time_hours}h"
                    ),
                    trigger=f"sla_breach_{sla.priority}",
                    penalty_amount=f"{sla.penalty_percentage}%",
                    penalty_type="percentage",
                ))

        return penalties

    # -- scope boundary compilation -----------------------------------------

    def compile_scope_boundaries(
        self,
        scope_boundaries: list[ScopeBoundaryObject],
    ) -> list[dict]:
        """Generate scope boundary control objects from parsed scope boundaries."""
        results: list[dict] = []

        for boundary in scope_boundaries:
            is_restrictive = boundary.scope_type.value in ("out_of_scope", "conditional")
            has_conditions = len(boundary.conditions) > 0

            results.append({
                "control_id": str(uuid.uuid4()),
                "control_type": "scope_boundary",
                "scope_type": boundary.scope_type.value,
                "description": boundary.description,
                "conditions": boundary.conditions,
                "clause_refs": boundary.clause_refs,
                "activities": boundary.activities,
                "is_restrictive": is_restrictive,
                "has_conditions": has_conditions,
                "activity_count": len(boundary.activities),
            })

        return results
