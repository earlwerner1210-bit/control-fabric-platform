"""Unit tests for IncidentRuleEngine.

Tests cover state transition validation, owner assignment, evidence requirements,
SLA compliance, and escalation triggers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

# ── Incident rule engine ─────────────────────────────────────────────────────

VALID_TRANSITIONS = {
    None: ["reported"],
    "reported": ["acknowledged", "cancelled"],
    "acknowledged": ["en_route", "cancelled"],
    "en_route": ["on_site"],
    "on_site": ["work_in_progress"],
    "work_in_progress": ["resolved", "escalated"],
    "resolved": ["closed"],
    "escalated": ["work_in_progress", "resolved"],
}


class IncidentRuleEngine:
    """Evaluate incident lifecycle rules."""

    def validate_transition(self, from_state: str | None, to_state: str) -> dict[str, Any]:
        allowed = VALID_TRANSITIONS.get(from_state, [])
        valid = to_state in allowed
        return {
            "valid": valid,
            "from_state": from_state,
            "to_state": to_state,
            "allowed_transitions": allowed,
        }

    def check_owner(self, incident: dict[str, Any]) -> dict[str, Any]:
        owner = incident.get("owner", "")
        has_owner = bool(owner and owner.strip())
        return {
            "rule": "owner_assigned",
            "passed": has_owner,
            "owner": owner,
        }

    def check_evidence(self, incident: dict[str, Any], required_types: list[str]) -> dict[str, Any]:
        evidence = incident.get("evidence", [])
        evidence_types = {e.get("type", "") for e in evidence}
        missing = [r for r in required_types if r not in evidence_types]
        return {
            "rule": "evidence_complete",
            "passed": len(missing) == 0,
            "missing": missing,
            "provided": list(evidence_types),
        }

    def check_sla(self, incident: dict[str, Any]) -> dict[str, Any]:
        sla = incident.get("sla_compliance", {})
        response_met = sla.get("response_met", False)
        resolution_met = sla.get("resolution_met", False)
        return {
            "rule": "sla_compliance",
            "passed": response_met and resolution_met,
            "response_met": response_met,
            "resolution_met": resolution_met,
        }

    def check_escalation(self, incident: dict[str, Any]) -> dict[str, Any]:
        priority = incident.get("priority", "medium")
        resolved_at = incident.get("resolved_at")
        reported_at = incident.get("reported_at")

        needs_escalation = False
        reason = ""

        if priority in ("critical", "high") and resolved_at is None:
            needs_escalation = True
            reason = f"{priority} incident still unresolved"
        elif priority == "critical" and reported_at and resolved_at:
            reported = datetime.fromisoformat(reported_at)
            resolved = datetime.fromisoformat(resolved_at)
            hours = (resolved - reported).total_seconds() / 3600
            if hours > 4.0:
                needs_escalation = True
                reason = f"Critical incident took {hours:.1f}h to resolve (target: 4h)"

        return {
            "rule": "escalation_check",
            "needs_escalation": needs_escalation,
            "reason": reason,
        }


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def engine() -> IncidentRuleEngine:
    return IncidentRuleEngine()


@pytest.fixture
def resolved_incident(sample_incident: dict[str, Any]) -> dict[str, Any]:
    return sample_incident


@pytest.fixture
def unresolved_incident() -> dict[str, Any]:
    return {
        "incident_id": "INC-X",
        "priority": "critical",
        "owner": "Acme",
        "reported_at": "2024-07-22T03:14:00Z",
        "resolved_at": None,
        "evidence": [],
        "sla_compliance": {"response_met": True, "resolution_met": False},
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestIncidentRuleEngine:
    def test_valid_transition_reported_to_acknowledged(self, engine):
        result = engine.validate_transition("reported", "acknowledged")
        assert result["valid"] is True

    def test_invalid_transition_reported_to_resolved(self, engine):
        result = engine.validate_transition("reported", "resolved")
        assert result["valid"] is False

    def test_initial_transition(self, engine):
        result = engine.validate_transition(None, "reported")
        assert result["valid"] is True

    def test_owner_assigned(self, engine, resolved_incident):
        result = engine.check_owner(resolved_incident)
        assert result["passed"] is True

    def test_owner_missing(self, engine):
        result = engine.check_owner({"owner": ""})
        assert result["passed"] is False

    def test_evidence_complete(self, engine, resolved_incident):
        result = engine.check_evidence(resolved_incident, ["fault_report", "photo"])
        assert result["passed"] is True

    def test_evidence_incomplete(self, engine, resolved_incident):
        result = engine.check_evidence(resolved_incident, ["fault_report", "cctv_footage"])
        assert result["passed"] is False
        assert "cctv_footage" in result["missing"]

    def test_sla_compliant(self, engine, resolved_incident):
        result = engine.check_sla(resolved_incident)
        assert result["passed"] is True

    def test_sla_non_compliant(self, engine, unresolved_incident):
        result = engine.check_sla(unresolved_incident)
        assert result["passed"] is False

    def test_escalation_needed(self, engine, unresolved_incident):
        result = engine.check_escalation(unresolved_incident)
        assert result["needs_escalation"] is True

    def test_no_escalation_needed(self, engine, resolved_incident):
        result = engine.check_escalation(resolved_incident)
        assert result["needs_escalation"] is False
