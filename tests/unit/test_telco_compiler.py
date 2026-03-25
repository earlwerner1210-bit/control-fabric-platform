"""Tests for the telco-ops compiler (parsers)."""

from __future__ import annotations

import pytest

from app.domain_packs.telco_ops.parsers import IncidentParser, RunbookParser
from app.domain_packs.telco_ops.schemas import (
    IncidentSeverity,
    IncidentState,
    ParsedIncident,
    ParsedRunbook,
)


@pytest.fixture
def inc_parser() -> IncidentParser:
    return IncidentParser()


@pytest.fixture
def rb_parser() -> RunbookParser:
    return RunbookParser()


@pytest.fixture
def sample_incident_data() -> dict:
    return {
        "incident_id": "INC-001",
        "title": "Network degradation on core router",
        "description": "Intermittent packet loss on core_network affecting multiple services",
        "severity": "p2",
        "state": "investigating",
        "affected_services": ["core_network", "voip", "internet"],
        "reported_by": "noc_team",
        "assigned_to": "senior_engineer_01",
        "created_at": "2024-03-14T14:00:00Z",
        "timeline": [
            {"timestamp": "2024-03-14T14:00:00Z", "action": "reported"},
            {"timestamp": "2024-03-14T14:05:00Z", "action": "acknowledged"},
        ],
        "tags": ["network", "core", "degradation"],
    }


@pytest.fixture
def sample_runbook_data() -> dict:
    return {
        "runbook_id": "RB-001",
        "title": "Network Degradation Response",
        "description": "Standard response procedure for network degradation events",
        "applicable_services": ["core_network", "voip"],
        "steps": [
            {"step": 1, "action": "Check interface counters", "expected_duration_minutes": 5},
            {"step": 2, "action": "Verify routing tables", "expected_duration_minutes": 10},
            {"step": 3, "action": "Check for hardware errors", "expected_duration_minutes": 15},
        ],
        "decision_points": [
            {"condition": "hardware_error_found", "action": "escalate_to_vendor"},
            {"condition": "routing_issue_found", "action": "apply_routing_fix"},
        ],
        "escalation_criteria": [
            {"condition": "unresolved_after_30_min", "escalate_to": "l3"},
        ],
        "estimated_resolution_minutes": 45,
    }


class TestTelcoCompiler:
    """Tests for the telco ops parsers."""

    def test_compile_incident_state(self, inc_parser: IncidentParser, sample_incident_data: dict):
        """Incident should compile with correct state and severity."""
        parsed = inc_parser.parse_incident(sample_incident_data)

        assert isinstance(parsed, ParsedIncident)
        assert parsed.incident_id == "INC-001"
        assert parsed.severity == IncidentSeverity.p2
        assert parsed.state == IncidentState.investigating
        assert parsed.assigned_to == "senior_engineer_01"
        assert len(parsed.timeline) == 2

    def test_compile_service_states(self, inc_parser: IncidentParser, sample_incident_data: dict):
        """Incident should have affected services."""
        parsed = inc_parser.parse_incident(sample_incident_data)

        assert len(parsed.affected_services) == 3
        assert "core_network" in parsed.affected_services
        assert "voip" in parsed.affected_services

    def test_compile_escalation_rules(self, rb_parser: RunbookParser, sample_runbook_data: dict):
        """Runbook should compile with escalation criteria."""
        parsed = rb_parser.parse_runbook(sample_runbook_data)

        assert isinstance(parsed, ParsedRunbook)
        assert parsed.runbook_id == "RB-001"
        assert len(parsed.steps) == 3
        assert len(parsed.decision_points) == 2
        assert len(parsed.escalation_criteria) == 1
        assert parsed.estimated_resolution_minutes == 45
        assert "core_network" in parsed.applicable_services

    def test_parse_incident_from_text(self, inc_parser: IncidentParser):
        """Parser should handle raw text incidents."""
        text = "INC-042 P1 Critical: Core network outage affecting all services"
        parsed = inc_parser.parse_incident(text)

        assert parsed.incident_id == "INC-042"
        assert parsed.severity == IncidentSeverity.p1
        assert "Core network outage" in parsed.description

    def test_parse_all_severities(self, inc_parser: IncidentParser):
        """All severity levels should parse correctly."""
        for sev in ["p1", "p2", "p3", "p4"]:
            parsed = inc_parser.parse_incident({
                "incident_id": f"INC-{sev}",
                "severity": sev,
            })
            assert parsed.severity == IncidentSeverity(sev)

    def test_parse_all_states(self, inc_parser: IncidentParser):
        """All incident states should parse correctly."""
        for state in ["new", "acknowledged", "investigating", "resolved", "closed"]:
            parsed = inc_parser.parse_incident({
                "incident_id": f"INC-{state}",
                "state": state,
            })
            assert parsed.state == IncidentState(state)

    def test_runbook_from_text(self, rb_parser: RunbookParser):
        """Runbook parser should handle text input."""
        parsed = rb_parser.parse_runbook("Network degradation runbook with step-by-step instructions")
        assert isinstance(parsed, ParsedRunbook)
        assert "Network degradation" in parsed.description

    def test_incident_default_values(self, inc_parser: IncidentParser):
        """Minimal incident should have sensible defaults."""
        parsed = inc_parser.parse_incident({"incident_id": "INC-MINIMAL"})
        assert parsed.severity == IncidentSeverity.p3  # default
        assert parsed.state == IncidentState.new  # default
        assert parsed.affected_services == []
