"""Tests for telco-ops validation rules."""

from __future__ import annotations

import pytest

from app.domain_packs.telco_ops.rules import (
    ActionRuleEngine,
    EscalationRuleEngine,
    OwnershipRuleEngine,
)
from app.domain_packs.telco_ops.schemas import (
    EscalationLevel,
    IncidentSeverity,
    IncidentState,
    ParsedIncident,
    ServiceState,
)


@pytest.fixture
def escalation_engine() -> EscalationRuleEngine:
    return EscalationRuleEngine()


@pytest.fixture
def action_engine() -> ActionRuleEngine:
    return ActionRuleEngine()


@pytest.fixture
def ownership_engine() -> OwnershipRuleEngine:
    return OwnershipRuleEngine()


class TestTelcoValidators:
    """Tests for telco ops validation rules."""

    def test_invalid_action_for_state(self, action_engine: ActionRuleEngine):
        """Action engine should only return valid actions for the current state."""
        # Closed incident: only valid action is reopen
        result = action_engine.evaluate(
            incident_state=IncidentState.closed,
        )
        valid_actions = ActionRuleEngine.VALID_TRANSITIONS["closed"]
        assert result.action in valid_actions

        # New incident: should not get resolve or close
        result_new = action_engine.evaluate(
            incident_state=IncidentState.new,
            has_assigned_owner=True,
        )
        assert result_new.action in ActionRuleEngine.VALID_TRANSITIONS["new"]
        assert result_new.action not in ("resolve", "close")

    def test_escalation_without_reason(self, escalation_engine: EscalationRuleEngine):
        """Low-severity incident without escalation conditions should not escalate."""
        incident = ParsedIncident(
            incident_id="INC-LOW",
            severity=IncidentSeverity.p4,
            state=IncidentState.new,
            affected_services=["email"],
        )

        result = escalation_engine.evaluate(incident)

        assert result.escalate is False
        assert result.level is None
        assert result.reason == ""

    def test_reconciliation_mismatches(self, action_engine: ActionRuleEngine):
        """Resolved incident should recommend closure, not investigation."""
        result = action_engine.evaluate(
            incident_state=IncidentState.resolved,
        )

        assert result.action == "close"
        assert "resolved" in result.reason.lower() or "closure" in result.reason.lower()

    def test_outdated_runbook_warning(self, action_engine: ActionRuleEngine):
        """Investigating incident with runbook should recommend dispatch."""
        result = action_engine.evaluate(
            incident_state=IncidentState.investigating,
            has_runbook=True,
        )

        assert result.action == "dispatch"
        assert "runbook" in result.reason.lower()

    def test_dispatch_on_resolved_fails(self, action_engine: ActionRuleEngine):
        """Resolved incident should not result in dispatch action."""
        result = action_engine.evaluate(
            incident_state=IncidentState.resolved,
        )

        assert result.action != "dispatch"
        assert result.action == "close"


class TestEscalationRules:
    """Tests for the escalation rule engine."""

    def test_p1_escalates_to_l3(self, escalation_engine: EscalationRuleEngine):
        """P1 incidents should escalate to L3."""
        incident = ParsedIncident(
            incident_id="INC-P1",
            severity=IncidentSeverity.p1,
            state=IncidentState.new,
        )

        result = escalation_engine.evaluate(incident)

        assert result.escalate is True
        assert result.level == EscalationLevel.l3
        assert result.owner == "senior_engineering"

    def test_p2_escalates_to_l2(self, escalation_engine: EscalationRuleEngine):
        """P2 incidents should escalate to L2."""
        incident = ParsedIncident(
            incident_id="INC-P2",
            severity=IncidentSeverity.p2,
            state=IncidentState.investigating,
        )

        result = escalation_engine.evaluate(incident)

        assert result.escalate is True
        assert result.level == EscalationLevel.l2
        assert result.owner == "engineering_team"

    def test_sla_breach_escalates_further(self, escalation_engine: EscalationRuleEngine):
        """SLA breach should increase escalation level."""
        incident = ParsedIncident(
            incident_id="INC-SLA",
            severity=IncidentSeverity.p2,
            state=IncidentState.investigating,
        )

        result = escalation_engine.evaluate(incident, sla_breached=True)

        assert result.escalate is True
        assert result.level == EscalationLevel.l3
        assert "SLA breach" in result.reason

    def test_outage_escalates(self, escalation_engine: EscalationRuleEngine):
        """Service outage should trigger escalation."""
        incident = ParsedIncident(
            incident_id="INC-OUTAGE",
            severity=IncidentSeverity.p3,
            state=IncidentState.investigating,
        )

        result = escalation_engine.evaluate(
            incident,
            service_state=ServiceState.outage,
        )

        assert result.escalate is True
        assert result.level == EscalationLevel.l3

    def test_repeated_incident_escalates(self, escalation_engine: EscalationRuleEngine):
        """Repeated incidents should trigger escalation."""
        incident = ParsedIncident(
            incident_id="INC-REPEAT",
            severity=IncidentSeverity.p4,
            state=IncidentState.investigating,
        )

        result = escalation_engine.evaluate(incident, repeat_count=5)

        assert result.escalate is True
        assert "Repeated incident" in result.reason


class TestOwnershipRules:
    """Tests for the ownership rule engine."""

    def test_p1_owner(self, ownership_engine: OwnershipRuleEngine):
        """P1 should be assigned to on-call engineer."""
        owner = ownership_engine.determine_owner(IncidentSeverity.p1, ["core_network"])
        assert owner == "on_call_engineer"

    def test_management_escalation_owner(self, ownership_engine: OwnershipRuleEngine):
        """Management escalation should go to service delivery manager."""
        owner = ownership_engine.determine_owner(
            IncidentSeverity.p2,
            ["voip"],
            escalation_level=EscalationLevel.management,
        )
        assert owner == "service_delivery_manager"

    def test_p4_default_owner(self, ownership_engine: OwnershipRuleEngine):
        """P4 incidents should go to service desk."""
        owner = ownership_engine.determine_owner(IncidentSeverity.p4, [])
        assert owner == "service_desk"
