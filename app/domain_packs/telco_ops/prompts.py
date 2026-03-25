"""Telco Ops prompt builder classes.

Each builder produces a dict with ``system``, ``user``, and optionally
``examples`` keys, ready to be fed into an LLM completion call.
"""

from __future__ import annotations

import json
from typing import Any

from app.domain_packs.telco_ops.schemas import (
    EscalationDecision,
    IncidentTimeline,
    NextAction,
    OpsRecommendation,
    ParsedIncident,
    ReconciliationResult,
    ServiceStateObject,
)


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_BASE_SYSTEM = (
    "You are an expert telecommunications operations analyst. "
    "Always base your analysis on factual evidence. "
    "Return structured JSON unless otherwise specified."
)


def _incident_block(incident: ParsedIncident) -> str:
    """Render an incident as a readable markdown block."""
    lines = [
        f"- **ID:** {incident.incident_id}",
        f"- **Title:** {incident.title}",
        f"- **Severity:** {incident.severity.value}",
        f"- **State:** {incident.state.value}",
        f"- **Affected services:** {', '.join(incident.affected_services) or 'none'}",
        f"- **Assigned to:** {incident.assigned_to or 'unassigned'}",
        f"- **Created:** {incident.created_at}",
    ]
    if incident.description:
        lines.append(f"- **Description:** {incident.description[:500]}")
    if incident.tags:
        lines.append(f"- **Tags:** {', '.join(incident.tags)}")
    return "\n".join(lines)


def _service_state_block(svc: ServiceStateObject) -> str:
    lines = [
        f"- **Service:** {svc.service_name} ({svc.service_id})",
        f"- **State:** {svc.state.value}",
        f"- **Impact:** {svc.impact_level.value}",
        f"- **Affected customers:** {svc.affected_customers}",
        f"- **Dependencies:** {', '.join(svc.dependencies) or 'none'}",
    ]
    if svc.recovery_eta_minutes is not None:
        lines.append(f"- **Recovery ETA:** {svc.recovery_eta_minutes} minutes")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# IncidentExplanationPromptBuilder
# ---------------------------------------------------------------------------


class IncidentExplanationPromptBuilder:
    """Build a prompt that asks an LLM to explain an incident."""

    def build(
        self,
        incident: ParsedIncident,
        service_state: ServiceStateObject | None = None,
        timeline: IncidentTimeline | None = None,
    ) -> dict:
        system = (
            f"{_BASE_SYSTEM}\n\n"
            "Your task is to produce a clear, concise explanation of the incident "
            "suitable for both technical and managerial audiences. Include:\n"
            "1. What happened\n"
            "2. Impact assessment\n"
            "3. Current status\n"
            "4. Key timeline milestones\n"
            "5. Recommended immediate actions"
        )

        user_parts = ["## Incident Details", _incident_block(incident)]

        if service_state:
            user_parts += ["", "## Service State", _service_state_block(service_state)]

        if timeline and timeline.events:
            user_parts += ["", "## Timeline"]
            for evt in timeline.events:
                user_parts.append(
                    f"- [{evt.timestamp}] **{evt.event_type}** by {evt.actor}: {evt.description}"
                )
            user_parts.append(f"\nTotal duration: {timeline.total_duration_minutes} min | SLA: {timeline.sla_status}")

        user_parts += [
            "",
            "## Instructions",
            "Provide a JSON object with keys: `explanation`, `impact_summary`, "
            "`current_status`, `timeline_highlights` (list), `recommended_actions` (list).",
        ]

        return {"system": system, "user": "\n".join(user_parts)}


# ---------------------------------------------------------------------------
# NextActionPromptBuilder
# ---------------------------------------------------------------------------


class NextActionPromptBuilder:
    """Build a prompt that asks an LLM for the next best action."""

    def build(
        self,
        incident: ParsedIncident,
        current_state: str,
        available_actions: list[str],
        sla_status: str,
    ) -> dict:
        system = (
            f"{_BASE_SYSTEM}\n\n"
            "Determine the single best next action for the incident. "
            "Consider severity, current state, SLA, and available actions."
        )

        user = (
            f"## Incident\n{_incident_block(incident)}\n\n"
            f"## Current state\n{current_state}\n\n"
            f"## Available actions\n{', '.join(available_actions)}\n\n"
            f"## SLA status\n{sla_status}\n\n"
            "## Instructions\n"
            "Return a JSON object with keys: `next_action`, `owner`, `rationale`, "
            "`priority` (critical/high/normal/low), `estimated_resolution_minutes`."
        )

        return {"system": system, "user": user}


# ---------------------------------------------------------------------------
# RunbookRecommendationPromptBuilder
# ---------------------------------------------------------------------------


class RunbookRecommendationPromptBuilder:
    """Build a prompt for runbook recommendation."""

    def build(
        self,
        incident: ParsedIncident,
        candidate_runbooks: list[dict],
        symptoms: list[str],
    ) -> dict:
        system = (
            f"{_BASE_SYSTEM}\n\n"
            "You will be given an incident and a list of candidate runbooks. "
            "Select the most appropriate runbook and explain your reasoning. "
            "If none are applicable, say so."
        )

        rb_block = ""
        for i, rb in enumerate(candidate_runbooks, 1):
            rb_block += (
                f"\n### Runbook {i}\n"
                f"- ID: {rb.get('runbook_id', 'unknown')}\n"
                f"- Title: {rb.get('title', '')}\n"
                f"- Services: {', '.join(rb.get('applicable_services', []))}\n"
                f"- Severity: {', '.join(rb.get('applicable_severity', []))}\n"
                f"- Success rate: {rb.get('success_rate', 'N/A')}\n"
                f"- Est. time: {rb.get('estimated_time_minutes', 'N/A')} min\n"
            )

        user = (
            f"## Incident\n{_incident_block(incident)}\n\n"
            f"## Observed Symptoms\n{chr(10).join('- ' + s for s in symptoms) if symptoms else 'None identified'}\n\n"
            f"## Candidate Runbooks{rb_block}\n\n"
            "## Instructions\n"
            "Return JSON: `selected_runbook_id` (or null), `confidence` (0-1), "
            "`rationale`, `modifications_needed` (list of strings)."
        )

        return {"system": system, "user": user}


# ---------------------------------------------------------------------------
# EscalationRecommendationPromptBuilder
# ---------------------------------------------------------------------------


class EscalationRecommendationPromptBuilder:
    """Build a prompt for escalation reasoning."""

    def build(
        self,
        incident: ParsedIncident,
        escalation_decision: EscalationDecision,
        ownership_chain: list[str],
    ) -> dict:
        system = (
            f"{_BASE_SYSTEM}\n\n"
            "Evaluate the proposed escalation decision and provide a "
            "human-readable justification or counter-recommendation."
        )

        user = (
            f"## Incident\n{_incident_block(incident)}\n\n"
            f"## Proposed Escalation\n"
            f"- Escalate: {escalation_decision.escalate}\n"
            f"- Level: {escalation_decision.level.value if escalation_decision.level else 'none'}\n"
            f"- Owner: {escalation_decision.owner}\n"
            f"- Reason: {escalation_decision.reason}\n\n"
            f"## Ownership Chain\n{' → '.join(ownership_chain) if ownership_chain else 'Not defined'}\n\n"
            "## Instructions\n"
            "Return JSON: `agree` (bool), `justification`, `alternative_level` (or null), "
            "`alternative_owner` (or null), `urgency` (immediate/soon/can_wait)."
        )

        return {"system": system, "user": user}


# ---------------------------------------------------------------------------
# ReconciliationPromptBuilder
# ---------------------------------------------------------------------------


class ReconciliationPromptBuilder:
    """Build a prompt for reconciliation analysis."""

    def build(
        self,
        incident_state: dict,
        work_order_state: dict,
        mismatches: list[dict],
    ) -> dict:
        system = (
            f"{_BASE_SYSTEM}\n\n"
            "You will be given the state of an incident and its corresponding "
            "work order, along with detected mismatches. Analyse the mismatches "
            "and provide actionable recommendations to resolve them."
        )

        user = (
            f"## Incident State\n```json\n{json.dumps(incident_state, indent=2)}\n```\n\n"
            f"## Work Order State\n```json\n{json.dumps(work_order_state, indent=2)}\n```\n\n"
            f"## Detected Mismatches\n```json\n{json.dumps(mismatches, indent=2)}\n```\n\n"
            "## Instructions\n"
            "Return JSON: `overall_assessment`, `recommendations` (list of "
            "{`action`, `priority`, `owner`}), `risk_level` (high/medium/low), "
            "`requires_manual_review` (bool)."
        )

        return {"system": system, "user": user}


# ---------------------------------------------------------------------------
# OpsNotePromptBuilder
# ---------------------------------------------------------------------------


class OpsNotePromptBuilder:
    """Build a prompt for generating an operational note."""

    def build(
        self,
        incident: ParsedIncident,
        analysis: dict,
        recommendations: list[dict],
    ) -> dict:
        system = (
            f"{_BASE_SYSTEM}\n\n"
            "Generate a concise operational note for shift handover or "
            "stakeholder communication. The note should cover: summary, "
            "current status, actions taken, pending items, and recommendations."
        )

        rec_lines = ""
        for r in recommendations:
            rec_lines += f"- {r.get('action', 'N/A')} (owner: {r.get('owner', 'TBD')}, priority: {r.get('priority', 'normal')})\n"

        user = (
            f"## Incident\n{_incident_block(incident)}\n\n"
            f"## Analysis\n```json\n{json.dumps(analysis, indent=2)}\n```\n\n"
            f"## Recommendations\n{rec_lines}\n"
            "## Instructions\n"
            "Return JSON: `summary` (2-3 sentences), `next_action`, "
            "`runbook_ref` (or null), `escalation_status`, `risk_assessment`."
        )

        return {"system": system, "user": user}
