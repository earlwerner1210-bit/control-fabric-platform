"""Tests for the incident dispatch workflow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from services.escalation_engine import EscalationRuleEngine
from workflows.incident_dispatch_reconcile.workflow import (
    IncidentDispatchResult,
    IncidentDispatchWorkflow,
)


@pytest.fixture
def escalation_engine() -> EscalationRuleEngine:
    return EscalationRuleEngine()


class TestIncidentDispatchWorkflow:
    """Tests for IncidentDispatchWorkflow."""

    @pytest.mark.asyncio
    async def test_dispatch_p2_network(self, escalation_engine: EscalationRuleEngine):
        """P2 network incident should be assigned to network_operations."""
        workflow = IncidentDispatchWorkflow(escalation_engine=escalation_engine)

        incident = {
            "incident_id": "INC-001",
            "priority": "P2",
            "severity": 2,
            "category": "network_degradation",
            "status": "investigating",
            "escalation_level": 0,
            "reported_at": "2024-03-14T14:00:00Z",
            "acknowledged_at": "2024-03-14T14:05:00Z",
            "affected_services": [],
        }

        result = await workflow.run(
            case_id="case-001",
            incident=incident,
            tenant_id="tenant-001",
        )

        assert isinstance(result, IncidentDispatchResult)
        assert result.assigned_team == "network_operations"
        assert result.sla_target_minutes == 480

    @pytest.mark.asyncio
    async def test_dispatch_p1_auto_escalates(self, escalation_engine: EscalationRuleEngine):
        """P1 incident should auto-escalate."""
        workflow = IncidentDispatchWorkflow(escalation_engine=escalation_engine)

        incident = {
            "incident_id": "INC-002",
            "priority": "P1",
            "severity": 1,
            "category": "network_outage",
            "status": "open",
            "escalation_level": 0,
            "reported_at": "2024-03-14T14:00:00Z",
            "acknowledged_at": "2024-03-14T14:02:00Z",
            "affected_services": [],
        }

        result = await workflow.run(
            case_id="case-002",
            incident=incident,
            tenant_id="tenant-001",
        )

        assert result.escalation_level >= 2
        assert result.sla_target_minutes == 240

    @pytest.mark.asyncio
    async def test_dispatch_with_sample_incident(
        self, escalation_engine: EscalationRuleEngine, sample_incident: dict[str, Any]
    ):
        """Workflow should work with sample incident fixture."""
        workflow = IncidentDispatchWorkflow(escalation_engine=escalation_engine)
        result = await workflow.run(
            case_id="case-003",
            incident=sample_incident,
            tenant_id="tenant-001",
        )
        assert result.incident_id == "INC-2024-0042"
        assert result.assigned_team is not None
        assert len(result.recommended_actions) > 0

    @pytest.mark.asyncio
    async def test_dispatch_audit_logged(self, escalation_engine: EscalationRuleEngine):
        """Workflow should log audit events."""
        mock_audit = AsyncMock()
        mock_audit.log = AsyncMock()

        workflow = IncidentDispatchWorkflow(
            escalation_engine=escalation_engine,
            audit_logger=mock_audit,
        )

        incident = {
            "incident_id": "INC-004",
            "priority": "P3",
            "severity": 3,
            "category": "general",
            "status": "open",
            "escalation_level": 0,
            "reported_at": "2024-03-14T14:00:00Z",
            "acknowledged_at": "2024-03-14T14:10:00Z",
            "affected_services": [],
        }

        await workflow.run(case_id="case-004", incident=incident, tenant_id="tenant-001")
        mock_audit.log.assert_called_once()
