"""Tests for the telco-ops escalation rule engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from services.escalation_engine import (
    EscalationRuleEngine,
    EscalationResult,
)


@pytest.fixture
def engine() -> EscalationRuleEngine:
    return EscalationRuleEngine()


class TestEscalationRuleEngine:
    """Tests for the EscalationRuleEngine."""

    def test_p1_auto_escalate(self, engine: EscalationRuleEngine):
        """P1 incidents should automatically escalate to level 2."""
        incident = {
            "incident_id": "INC-001",
            "priority": "P1",
            "severity": 1,
            "status": "investigating",
            "escalation_level": 0,
            "reported_at": "2024-03-14T14:00:00Z",
            "acknowledged_at": "2024-03-14T14:05:00Z",
            "affected_services": [],
        }
        # Use a time shortly after reporting
        now = datetime(2024, 3, 14, 14, 10, tzinfo=timezone.utc)
        result = engine.evaluate(incident, current_time=now)
        assert result.should_escalate is True
        assert result.recommended_level >= 2

    def test_p1_already_escalated(self, engine: EscalationRuleEngine):
        """P1 incident already at level 2 should not re-escalate from P1 rule."""
        incident = {
            "incident_id": "INC-002",
            "priority": "P1",
            "severity": 1,
            "status": "investigating",
            "escalation_level": 2,
            "reported_at": "2024-03-14T14:00:00Z",
            "acknowledged_at": "2024-03-14T14:05:00Z",
            "affected_services": [],
        }
        now = datetime(2024, 3, 14, 14, 10, tzinfo=timezone.utc)
        result = engine.evaluate(incident, current_time=now)
        # P1 auto-escalate rule should not fire since already at level 2
        p1_actions = [a for a in result.actions if "auto_escalate" in a.action]
        assert len(p1_actions) == 0

    def test_sla_breach_escalation(self, engine: EscalationRuleEngine):
        """Incident past SLA resolution target should escalate."""
        incident = {
            "incident_id": "INC-003",
            "priority": "P2",
            "severity": 2,
            "status": "investigating",
            "escalation_level": 0,
            "reported_at": "2024-03-14T06:00:00Z",
            "acknowledged_at": "2024-03-14T06:05:00Z",
            "affected_services": [],
        }
        # P2 resolution SLA is 480 min (8 hours), set time 9 hours after
        now = datetime(2024, 3, 14, 15, 0, tzinfo=timezone.utc)
        result = engine.evaluate(incident, current_time=now)
        assert result.should_escalate is True
        assert result.sla_status == "breached"

    def test_sla_at_risk(self, engine: EscalationRuleEngine):
        """Incident approaching SLA should be flagged as at_risk."""
        incident = {
            "incident_id": "INC-004",
            "priority": "P2",
            "severity": 2,
            "status": "investigating",
            "escalation_level": 0,
            "reported_at": "2024-03-14T06:00:00Z",
            "acknowledged_at": "2024-03-14T06:05:00Z",
            "affected_services": [],
        }
        # At 50% of P2 resolution (240 min = 4 hours after)
        now = datetime(2024, 3, 14, 10, 0, tzinfo=timezone.utc)
        result = engine.evaluate(incident, current_time=now)
        assert result.sla_status == "at_risk"

    def test_p3_no_escalation_early(self, engine: EscalationRuleEngine):
        """P3 incident early in its SLA window should not escalate."""
        incident = {
            "incident_id": "INC-005",
            "priority": "P3",
            "severity": 3,
            "status": "investigating",
            "escalation_level": 0,
            "reported_at": "2024-03-14T14:00:00Z",
            "acknowledged_at": "2024-03-14T14:10:00Z",
            "affected_services": [],
        }
        # Only 30 minutes in, P3 has 1440 min resolution
        now = datetime(2024, 3, 14, 14, 30, tzinfo=timezone.utc)
        result = engine.evaluate(incident, current_time=now)
        assert result.should_escalate is False
        assert result.sla_status == "within_sla"

    def test_vip_high_impact_escalation(self, engine: EscalationRuleEngine):
        """VIP customer with high impact should trigger management escalation."""
        incident = {
            "incident_id": "INC-006",
            "priority": "P2",
            "severity": 2,
            "status": "investigating",
            "escalation_level": 0,
            "vip": True,
            "reported_at": "2024-03-14T14:00:00Z",
            "acknowledged_at": "2024-03-14T14:05:00Z",
            "affected_services": [
                {"service_id": "SVC-001", "customer_count": 150},
            ],
        }
        now = datetime(2024, 3, 14, 14, 10, tzinfo=timezone.utc)
        result = engine.evaluate(incident, current_time=now)
        assert result.should_escalate is True
        assert result.recommended_level >= 3
        management_actions = [a for a in result.actions if "management" in a.action]
        assert len(management_actions) >= 1

    def test_unacknowledged_near_deadline(self, engine: EscalationRuleEngine):
        """Unacknowledged incident near response deadline should escalate."""
        incident = {
            "incident_id": "INC-007",
            "priority": "P2",
            "severity": 2,
            "status": "open",
            "escalation_level": 0,
            "reported_at": "2024-03-14T14:00:00Z",
            "acknowledged_at": None,
            "affected_services": [],
        }
        # P2 response SLA is 120 min, test at 100 min (20 min remaining < 30)
        now = datetime(2024, 3, 14, 15, 40, tzinfo=timezone.utc)
        result = engine.evaluate(incident, current_time=now)
        assert result.should_escalate is True
        team_lead = [a for a in result.actions if "team_lead" in a.action]
        assert len(team_lead) >= 1
