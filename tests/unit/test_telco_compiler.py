"""Tests for the TelcoCompiler from app.domain_packs.telco_ops.compiler."""

from __future__ import annotations

import pytest

from app.domain_packs.telco_ops.compiler import TelcoCompiler, TelcoCompileResult
from app.domain_packs.telco_ops.schemas import (
    ImpactLevel,
    IncidentSeverity,
    IncidentState,
    ParsedIncident,
    ParsedRunbook,
    ServiceState,
    ServiceStateObject,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def compiler() -> TelcoCompiler:
    return TelcoCompiler()


@pytest.fixture
def p1_incident() -> ParsedIncident:
    return ParsedIncident(
        incident_id="INC-001",
        title="Core network outage affecting voice services",
        description="Complete outage of the core_network service cluster.",
        severity=IncidentSeverity.p1,
        state=IncidentState.new,
        affected_services=["core_network", "voice_platform"],
        assigned_to="on_call_engineer",
        created_at="2024-04-15T08:00:00Z",
        updated_at="2024-04-15T08:05:00Z",
        tags=["outage", "critical"],
    )


@pytest.fixture
def p3_incident_unassigned() -> ParsedIncident:
    return ParsedIncident(
        incident_id="INC-003",
        title="Minor DNS configuration issue",
        description="DNS lookup intermittently slow.",
        severity=IncidentSeverity.p3,
        state=IncidentState.new,
        affected_services=["dns_service"],
        assigned_to="",
        created_at="2024-04-15T10:00:00Z",
    )


@pytest.fixture
def service_state_outage() -> ServiceStateObject:
    return ServiceStateObject(
        service_id="svc-core-001",
        service_name="core_network",
        state=ServiceState.outage,
        affected_customers=15000,
        impact_level=ImpactLevel.critical,
        dependencies=["power_grid", "data_center"],
        recovery_eta_minutes=120,
    )


@pytest.fixture
def sample_runbook() -> ParsedRunbook:
    return ParsedRunbook(
        runbook_id="RB-NET-001",
        title="Core Network Recovery Procedure",
        description="Steps to recover core network from outage.",
        applicable_services=["core_network"],
        steps=[
            {"step_number": 1, "action": "Verify power supply"},
            {"step_number": 2, "action": "Restart network controllers"},
            {"step_number": 3, "action": "Run connectivity checks"},
        ],
        estimated_resolution_minutes=90,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCompileP1Incident:
    """test_compile_p1_incident: P1 incident gets L3 escalation rules."""

    def test_compile_returns_result(self, compiler: TelcoCompiler, p1_incident: ParsedIncident):
        result = compiler.compile(p1_incident)
        assert isinstance(result, TelcoCompileResult)

    def test_incident_state_generated(self, compiler: TelcoCompiler, p1_incident: ParsedIncident):
        result = compiler.compile(p1_incident)

        assert result.incident_state["incident_id"] == "INC-001"
        assert result.incident_state["severity"] == "p1"
        assert result.incident_state["state"] == "new"
        assert result.incident_state["is_active"] is True
        assert result.incident_state["requires_immediate_attention"] is True

    def test_p1_gets_l3_escalation(self, compiler: TelcoCompiler, p1_incident: ParsedIncident):
        result = compiler.compile(p1_incident)

        severity_rules = [
            r for r in result.escalation_rules if r["rule"] == "severity_based_escalation"
        ]
        assert len(severity_rules) == 1
        assert severity_rules[0]["escalation_level"] == "l3"
        assert severity_rules[0]["auto"] is True

    def test_p1_critical_service_escalation(
        self, compiler: TelcoCompiler, p1_incident: ParsedIncident
    ):
        """P1 affecting core_network should also trigger critical_service_escalation."""
        result = compiler.compile(p1_incident)

        critical_rules = [
            r for r in result.escalation_rules if r["rule"] == "critical_service_escalation"
        ]
        assert len(critical_rules) == 1
        assert critical_rules[0]["escalation_level"] == "l3"
        assert critical_rules[0]["auto"] is True
        assert "core_network" in critical_rules[0]["affected_services"]

    def test_p1_ownership_is_on_call(self, compiler: TelcoCompiler, p1_incident: ParsedIncident):
        result = compiler.compile(p1_incident)

        default_ownership = [r for r in result.ownership_rules if r["rule"] == "default_ownership"]
        assert len(default_ownership) == 1
        assert default_ownership[0]["primary_owner"] == "on_call_engineer"
        assert default_ownership[0]["time_to_own_minutes"] == 5

    def test_control_object_payloads_aggregated(
        self, compiler: TelcoCompiler, p1_incident: ParsedIncident
    ):
        result = compiler.compile(p1_incident)

        types = {o["type"] for o in result.control_object_payloads}
        assert "incident_state" in types
        assert "escalation_rule" in types
        assert "ownership_rule" in types
        assert "next_action_context" in types


class TestCompileWithServiceState:
    """test_compile_with_service_state: Service state objects generated."""

    def test_explicit_service_state_included(
        self,
        compiler: TelcoCompiler,
        p1_incident: ParsedIncident,
        service_state_outage: ServiceStateObject,
    ):
        result = compiler.compile(p1_incident, service_state=service_state_outage)

        assert len(result.service_states) >= 1

        core_svc = [s for s in result.service_states if s["service_name"] == "core_network"]
        assert len(core_svc) == 1
        assert core_svc[0]["state"] == "outage"
        assert core_svc[0]["affected_customers"] == 15000
        assert core_svc[0]["impact_level"] == "critical"
        assert core_svc[0]["recovery_eta_minutes"] == 120
        assert core_svc[0]["linked_incident"] == "INC-001"

    def test_unrepresented_services_get_placeholder(
        self,
        compiler: TelcoCompiler,
        p1_incident: ParsedIncident,
        service_state_outage: ServiceStateObject,
    ):
        result = compiler.compile(p1_incident, service_state=service_state_outage)

        voice = [s for s in result.service_states if s["service_name"] == "voice_platform"]
        assert len(voice) == 1
        assert voice[0]["state"] == "unknown"
        assert voice[0]["linked_incident"] == "INC-001"

    def test_no_service_state_generates_placeholders(
        self, compiler: TelcoCompiler, p1_incident: ParsedIncident
    ):
        result = compiler.compile(p1_incident)

        assert len(result.service_states) == 2
        for ss in result.service_states:
            assert ss["state"] == "unknown"

    def test_service_states_in_control_objects(
        self,
        compiler: TelcoCompiler,
        p1_incident: ParsedIncident,
        service_state_outage: ServiceStateObject,
    ):
        result = compiler.compile(p1_incident, service_state=service_state_outage)

        svc_payloads = [o for o in result.control_object_payloads if o["type"] == "service_state"]
        assert len(svc_payloads) >= 1


class TestCompileWithRunbook:
    """test_compile_with_runbook: Next action context includes runbook."""

    def test_runbook_included_in_context(
        self, compiler: TelcoCompiler, p1_incident: ParsedIncident, sample_runbook: ParsedRunbook
    ):
        result = compiler.compile(p1_incident, runbook=sample_runbook)

        assert result.next_action_context["has_runbook"] is True
        assert result.next_action_context["runbook_id"] == "RB-NET-001"
        assert result.next_action_context["runbook_title"] == "Core Network Recovery Procedure"

    def test_no_runbook_in_context(self, compiler: TelcoCompiler, p1_incident: ParsedIncident):
        result = compiler.compile(p1_incident)

        assert result.next_action_context["has_runbook"] is False
        assert result.next_action_context["runbook_id"] is None
        assert result.next_action_context["runbook_title"] is None

    def test_next_action_context_fields(
        self, compiler: TelcoCompiler, p1_incident: ParsedIncident, sample_runbook: ParsedRunbook
    ):
        result = compiler.compile(p1_incident, runbook=sample_runbook)

        ctx = result.next_action_context
        assert ctx["incident_id"] == "INC-001"
        assert ctx["current_state"] == "new"
        assert ctx["severity"] == "p1"
        assert isinstance(ctx["valid_actions"], list)
        assert len(ctx["valid_actions"]) > 0
        assert ctx["has_assigned_owner"] is True
        assert ctx["affected_services"] == ["core_network", "voice_platform"]

    def test_service_outage_detected_in_context(
        self,
        compiler: TelcoCompiler,
        p1_incident: ParsedIncident,
        service_state_outage: ServiceStateObject,
        sample_runbook: ParsedRunbook,
    ):
        result = compiler.compile(
            p1_incident,
            service_state=service_state_outage,
            runbook=sample_runbook,
        )

        assert result.next_action_context["service_outage"] is True
        assert result.next_action_context["service_state"] == "outage"
        assert result.next_action_context["recovery_eta_minutes"] == 120


class TestCompileOwnershipUnassigned:
    """test_compile_ownership_unassigned: Unassigned gets alert rule."""

    def test_unassigned_alert_generated(
        self, compiler: TelcoCompiler, p3_incident_unassigned: ParsedIncident
    ):
        result = compiler.compile(p3_incident_unassigned)

        alert_rules = [r for r in result.ownership_rules if r["rule"] == "unassigned_alert"]
        assert len(alert_rules) == 1
        assert alert_rules[0]["alert"] is True
        assert "INC-003" in alert_rules[0]["message"]

    def test_assigned_incident_no_alert(self, compiler: TelcoCompiler, p1_incident: ParsedIncident):
        result = compiler.compile(p1_incident)

        alert_rules = [r for r in result.ownership_rules if r["rule"] == "unassigned_alert"]
        assert len(alert_rules) == 0

    def test_unassigned_next_action_context(
        self, compiler: TelcoCompiler, p3_incident_unassigned: ParsedIncident
    ):
        result = compiler.compile(p3_incident_unassigned)

        assert result.next_action_context["has_assigned_owner"] is False

    def test_p3_ownership_is_service_desk(
        self, compiler: TelcoCompiler, p3_incident_unassigned: ParsedIncident
    ):
        result = compiler.compile(p3_incident_unassigned)

        default_ownership = [r for r in result.ownership_rules if r["rule"] == "default_ownership"]
        assert len(default_ownership) == 1
        assert default_ownership[0]["primary_owner"] == "service_desk"
        assert default_ownership[0]["time_to_own_minutes"] == 15


class TestCompileCriticalService:
    """test_compile_critical_service: Critical service escalation rule generated."""

    def test_core_network_triggers_critical_escalation(
        self, compiler: TelcoCompiler, p1_incident: ParsedIncident
    ):
        result = compiler.compile(p1_incident)

        critical_rules = [
            r for r in result.escalation_rules if r["rule"] == "critical_service_escalation"
        ]
        assert len(critical_rules) == 1
        assert critical_rules[0]["escalation_level"] == "l3"

    def test_billing_service_triggers_critical_escalation(self, compiler: TelcoCompiler):
        incident = ParsedIncident(
            incident_id="INC-BILL",
            title="Billing system failure",
            severity=IncidentSeverity.p2,
            state=IncidentState.investigating,
            affected_services=["billing"],
        )
        result = compiler.compile(incident)

        critical_rules = [
            r for r in result.escalation_rules if r["rule"] == "critical_service_escalation"
        ]
        assert len(critical_rules) == 1

    def test_non_critical_service_no_critical_escalation(self, compiler: TelcoCompiler):
        incident = ParsedIncident(
            incident_id="INC-NON-CRIT",
            title="Email system slow",
            severity=IncidentSeverity.p3,
            state=IncidentState.new,
            affected_services=["email_gateway"],
        )
        result = compiler.compile(incident)

        critical_rules = [
            r for r in result.escalation_rules if r["rule"] == "critical_service_escalation"
        ]
        assert len(critical_rules) == 0

    def test_investigating_state_gets_stale_investigation_rule(self, compiler: TelcoCompiler):
        incident = ParsedIncident(
            incident_id="INC-INV",
            title="Network degradation under investigation",
            severity=IncidentSeverity.p1,
            state=IncidentState.investigating,
            affected_services=["core_network"],
            assigned_to="senior_eng",
        )
        result = compiler.compile(incident)

        stale_rules = [
            r for r in result.escalation_rules if r["rule"] == "stale_investigation_escalation"
        ]
        assert len(stale_rules) == 1
        assert stale_rules[0]["threshold_minutes"] == 60  # P1 threshold

    def test_resolved_incident_not_active(self, compiler: TelcoCompiler):
        incident = ParsedIncident(
            incident_id="INC-RESOLVED",
            title="Issue resolved",
            severity=IncidentSeverity.p1,
            state=IncidentState.resolved,
            affected_services=["core_network"],
        )
        result = compiler.compile(incident)

        assert result.incident_state["is_active"] is False
        assert result.incident_state["requires_immediate_attention"] is False
