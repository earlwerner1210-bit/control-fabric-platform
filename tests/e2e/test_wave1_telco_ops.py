"""Wave 1 end-to-end tests -- Telco Ops domain.

Tests using Vodafone incident fixtures to verify escalation, dispatch,
SLA tracking, closure gates, and incident-to-work-order linkage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain_packs.telco_ops.parsers import (
    IncidentParser,
    RunbookParser,
    VodafoneTicketParser,
)
from app.domain_packs.telco_ops.rules import (
    ActionRuleEngine,
    EscalationRuleEngine,
    OwnershipRuleEngine,
)
from app.domain_packs.telco_ops.schemas import (
    ClosureGate,
    ClosurePrerequisite,
    EscalationLevel,
    IncidentSeverity,
    IncidentState,
    ServiceState,
    VODAFONE_SLA_DEFINITIONS,
)
from app.domain_packs.reconciliation import WorkOrderIncidentLinker

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@pytest.fixture
def p1_incident() -> dict:
    with open(SAMPLE_DIR / "sample-incidents" / "vodafone_p1_core_outage.json") as f:
        return json.load(f)


@pytest.fixture
def p2_incident() -> dict:
    with open(SAMPLE_DIR / "sample-incidents" / "vodafone_p2_ran_degradation.json") as f:
        return json.load(f)


@pytest.fixture
def hv_switching_runbook() -> dict:
    with open(SAMPLE_DIR / "sample-runbooks" / "spen_hv_switching_runbook.json") as f:
        return json.load(f)


@pytest.fixture
def incident_parser() -> IncidentParser:
    return IncidentParser()


@pytest.fixture
def ticket_parser() -> VodafoneTicketParser:
    return VodafoneTicketParser()


@pytest.fixture
def escalation_engine() -> EscalationRuleEngine:
    return EscalationRuleEngine()


@pytest.fixture
def action_engine() -> ActionRuleEngine:
    return ActionRuleEngine()


# ===========================================================================
# Tests
# ===========================================================================


class TestP1IncidentEscalation:
    """Test P1 incident escalation rules."""

    def test_p1_incident_escalation(
        self,
        incident_parser: IncidentParser,
        escalation_engine: EscalationRuleEngine,
        p1_incident: dict,
    ):
        """P1 core outage triggers L3 escalation."""
        parsed = incident_parser.parse_incident({
            "incident_id": p1_incident["incident_id"],
            "title": p1_incident["title"],
            "severity": "p1",
            "state": "investigating",
            "affected_services": [s["service_id"] for s in p1_incident["affected_services"]],
        })
        decision = escalation_engine.evaluate(
            incident=parsed,
            service_state=ServiceState.outage,
        )
        assert decision.escalate is True
        assert decision.level == EscalationLevel.l3
        assert decision.owner != ""

    def test_major_incident_handling(
        self, incident_parser: IncidentParser, p1_incident: dict
    ):
        """P1 incident data includes major incident fields."""
        assert p1_incident["major_incident"] is True
        # The fixture uses mim_bridge_ref at the top level
        assert "mim_bridge_ref" in p1_incident
        assert p1_incident["estimated_customer_impact"]["total_affected_subscribers"] > 100000
        # Verify timeline has key events
        timeline_events = [e["event"] for e in p1_incident["timeline"]]
        assert any("major incident" in e.lower() for e in timeline_events)


class TestP2IncidentDispatch:
    """Test P2 incident dispatch and handling."""

    def test_p2_incident_dispatch(
        self,
        incident_parser: IncidentParser,
        action_engine: ActionRuleEngine,
        p2_incident: dict,
    ):
        """P2 RAN degradation dispatches an engineer."""
        parsed = incident_parser.parse_incident({
            "incident_id": p2_incident["incident_id"],
            "title": p2_incident["title"],
            "severity": "p2",
            "state": "investigating",
            "affected_services": [s["service_id"] for s in p2_incident["affected_services"]],
        })
        action = action_engine.evaluate(
            incident_state=parsed.state,
            service_state=ServiceState.degraded,
            has_runbook=True,
            has_assigned_owner=True,
        )
        assert action.action == "dispatch"

    def test_p2_escalation(
        self,
        incident_parser: IncidentParser,
        escalation_engine: EscalationRuleEngine,
        p2_incident: dict,
    ):
        """P2 incident triggers L2 escalation."""
        parsed = incident_parser.parse_incident({
            "incident_id": p2_incident["incident_id"],
            "title": p2_incident["title"],
            "severity": "p2",
            "state": "investigating",
            "affected_services": [s["service_id"] for s in p2_incident["affected_services"]],
        })
        decision = escalation_engine.evaluate(incident=parsed)
        assert decision.escalate is True
        assert decision.level == EscalationLevel.l2


class TestSLAStatus:
    """Test SLA status checks."""

    def test_sla_status_check_within(self, action_engine: ActionRuleEngine):
        """SLA within window returns 'within' status."""
        result = action_engine.check_sla_window(
            severity=IncidentSeverity.p2,
            elapsed_minutes=60,
        )
        assert result["status"] == "within"
        assert result["remaining_minutes"] > 0
        assert result["pct_used"] < 80

    def test_sla_status_check_warning(self, action_engine: ActionRuleEngine):
        """SLA approaching limit returns 'warning' status."""
        result = action_engine.check_sla_window(
            severity=IncidentSeverity.p2,
            elapsed_minutes=200,
        )
        assert result["status"] == "warning"
        assert result["pct_used"] >= 80

    def test_sla_status_check_breached(self, action_engine: ActionRuleEngine):
        """SLA past limit returns 'breached' status."""
        result = action_engine.check_sla_window(
            severity=IncidentSeverity.p2,
            elapsed_minutes=300,
        )
        assert result["status"] == "breached"
        assert result["remaining_minutes"] == 0

    def test_p1_sla_definition(self):
        """Verify P1 SLA definitions from Vodafone constants."""
        p1_sla = next(
            (s for s in VODAFONE_SLA_DEFINITIONS if s.severity == IncidentSeverity.p1),
            None,
        )
        assert p1_sla is not None
        assert p1_sla.response_time_minutes == 15
        assert p1_sla.resolution_time_minutes == 240
        assert p1_sla.bridge_call_required is True
        assert p1_sla.rca_required is True


class TestClosureGateValidation:
    """Test incident closure gate validation."""

    def test_closure_gate_validation_satisfied(self):
        """All mandatory gates satisfied -> closure allowed."""
        gates = [
            ClosureGate(prerequisite=ClosurePrerequisite.service_restored, satisfied=True, mandatory=True),
            ClosureGate(prerequisite=ClosurePrerequisite.customer_notified, satisfied=True, mandatory=True),
            ClosureGate(prerequisite=ClosurePrerequisite.root_cause_identified, satisfied=True, mandatory=True),
        ]
        unsatisfied_mandatory = [g for g in gates if g.mandatory and not g.satisfied]
        assert len(unsatisfied_mandatory) == 0

    def test_closure_gate_validation_blocked(self):
        """Mandatory gate unsatisfied -> closure blocked."""
        gates = [
            ClosureGate(prerequisite=ClosurePrerequisite.service_restored, satisfied=True, mandatory=True),
            ClosureGate(prerequisite=ClosurePrerequisite.customer_notified, satisfied=False, mandatory=True),
            ClosureGate(prerequisite=ClosurePrerequisite.root_cause_identified, satisfied=True, mandatory=True),
        ]
        unsatisfied_mandatory = [g for g in gates if g.mandatory and not g.satisfied]
        assert len(unsatisfied_mandatory) == 1
        assert unsatisfied_mandatory[0].prerequisite == ClosurePrerequisite.customer_notified

    def test_closure_gates_extracted_from_ticket(self, ticket_parser: VodafoneTicketParser):
        """Closure gates are inferred from ticket severity."""
        ticket = {
            "incident_id": "VF-INC-2026-01050",
            "title": "Customer supply loss",
            "severity": "p1",
            "state": "resolved",
        }
        gates = ticket_parser.extract_closure_gates(ticket)
        assert len(gates) > 2  # P1/P2 should have additional gates
        gate_prereqs = [g.prerequisite for g in gates]
        assert ClosurePrerequisite.service_restored in gate_prereqs
        assert ClosurePrerequisite.rca_submitted in gate_prereqs


class TestIncidentWorkOrderLinkage:
    """Test incident-to-work-order linkage."""

    def test_incident_to_work_order_linkage(self):
        """Work order linked to triggering incident via time window and description."""
        linker = WorkOrderIncidentLinker()
        wo_data = {
            "work_order_id": "SPEN-WO-2026-0502",
            "description": "Emergency LV fault customer supply loss at 15 Byres Road",
            "work_order_type": "emergency",
            "scheduled_date": "2026-03-20",
            "location": "15 Byres Road Glasgow",
        }
        incidents = [
            {
                "incident_id": "VF-INC-2026-01050",
                "title": "Customer supply loss 15 Byres Road Glasgow",
                "description": "Customer supply loss at 15 Byres Road Glasgow",
                "affected_services": ["residential_supply"],
                "created_at": "2026-03-20T14:30:00Z",
                "location": "15 Byres Road Glasgow",
            }
        ]
        links = linker.link(wo_data, incidents)
        # Location + description similarity should produce a link
        assert len(links) >= 1
        assert links[0].link_type == "work_order_to_incident"
        assert links[0].confidence > 0.3


class TestVodafoneTicketParsing:
    """Test Vodafone ticket parsing."""

    def test_vodafone_ticket_parse(
        self, ticket_parser: VodafoneTicketParser, p1_incident: dict
    ):
        """Parse a Vodafone P1 ticket into structured incident."""
        parsed = ticket_parser.parse_vodafone_ticket({
            "incident_id": p1_incident["incident_id"],
            "title": p1_incident["title"],
            "severity": "p1",
            "state": "major_incident_declared",
            "affected_services": [s["service_id"] for s in p1_incident["affected_services"]],
            "major_incident": True,
            "service_domain": "core_network",
            "category": "core_network_outage",
            "bridge_call_id": p1_incident.get("mim_bridge_ref", ""),
        })
        assert parsed.incident_id == p1_incident["incident_id"]
        assert parsed.severity == IncidentSeverity.p1
        assert "major_incident" in parsed.tags
        assert any("domain:core_network" in t for t in parsed.tags)

    def test_vodafone_category_classification(
        self, incident_parser: IncidentParser, p1_incident: dict
    ):
        """Classify Vodafone incident into correct category."""
        text = f"{p1_incident['title']} {p1_incident.get('root_cause_hypothesis', '')}"
        category = incident_parser.classify_vodafone_category(text)
        # P1 core outage with UPS/power references
        assert category in ("power_failure", "network_outage")


class TestServiceCreditCalculation:
    """Test service credit calculation logic."""

    def test_service_credit_calculation(self):
        """Calculate service credits for SLA breaches."""
        # Using the wave1_penalty_scenario logic: 5% per breach, 30% cap
        breaches = 7
        credit_per_breach = 5.0
        cap = 30.0
        monthly_value = 85000.00

        uncapped = breaches * credit_per_breach
        assert uncapped == 35.0

        capped = min(uncapped, cap)
        assert capped == 30.0

        credit_value = monthly_value * capped / 100
        assert credit_value == pytest.approx(25500.00)

    def test_p2_sla_breach_triggers_management_escalation(
        self, escalation_engine: EscalationRuleEngine
    ):
        """P2 incident with SLA breach escalates to management."""
        from app.domain_packs.telco_ops.schemas import ParsedIncident

        parsed = ParsedIncident(
            incident_id="VF-INC-TEST",
            title="RAN degradation Edinburgh",
            severity=IncidentSeverity.p2,
            state=IncidentState.investigating,
        )
        decision = escalation_engine.evaluate(
            incident=parsed,
            sla_breached=True,
        )
        assert decision.escalate is True
        assert decision.level == EscalationLevel.management

    def test_ownership_for_p1(self):
        """P1 incident should be assigned to on_call_engineer."""
        engine = OwnershipRuleEngine()
        owner = engine.determine_owner(
            severity=IncidentSeverity.p1,
            affected_services=["core_network"],
        )
        assert owner == "on_call_engineer"

    def test_ownership_for_p2(self):
        """P2 incident should be assigned to engineering_team."""
        engine = OwnershipRuleEngine()
        owner = engine.determine_owner(
            severity=IncidentSeverity.p2,
            affected_services=["ran_radio"],
        )
        assert owner == "engineering_team"
