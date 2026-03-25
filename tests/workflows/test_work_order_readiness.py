"""Tests for the work order readiness workflow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain_packs.utilities_field.rules.readiness_rules import ReadinessRuleEngine
from workflows.work_order_readiness.workflow import (
    WorkOrderReadinessWorkflow,
    WorkOrderReadinessResult,
)


@pytest.fixture
def readiness_engine() -> ReadinessRuleEngine:
    return ReadinessRuleEngine()


class TestWorkOrderReadinessWorkflow:
    """Tests for WorkOrderReadinessWorkflow."""

    @pytest.mark.asyncio
    async def test_ready_work_order(self, readiness_engine: ReadinessRuleEngine):
        """Ready work order should produce 'ready' verdict."""
        workflow = WorkOrderReadinessWorkflow(readiness_engine=readiness_engine)

        work_order = {
            "work_order_id": "WO-001",
            "required_skills": ["fiber_splicing"],
            "engineer": {
                "id": "ENG-001",
                "skills": ["fiber_splicing", "otdr_testing"],
                "certifications": [],
            },
            "required_certifications": [],
            "required_permits": [],
            "materials": [],
            "schedule": {"scheduled_date": "2024-04-01"},
        }

        result = await workflow.run(
            case_id="case-001",
            work_order=work_order,
            tenant_id="tenant-001",
        )

        assert isinstance(result, WorkOrderReadinessResult)
        assert result.verdict == "ready"
        assert "fiber_splicing" in result.matched_skills

    @pytest.mark.asyncio
    async def test_blocked_work_order(self, readiness_engine: ReadinessRuleEngine):
        """Blocked work order should produce 'blocked' verdict."""
        workflow = WorkOrderReadinessWorkflow(readiness_engine=readiness_engine)

        work_order = {
            "work_order_id": "WO-002",
            "required_skills": ["welding"],
            "engineer": {
                "id": "ENG-001",
                "skills": ["fiber_splicing"],
                "certifications": [],
            },
            "required_certifications": [],
            "required_permits": [
                {"type": "hot_work", "status": "pending"},
            ],
            "materials": [],
            "schedule": {"scheduled_date": "2024-04-01"},
        }

        result = await workflow.run(
            case_id="case-002",
            work_order=work_order,
            tenant_id="tenant-001",
        )

        assert result.verdict == "blocked"
        assert len(result.blockers) > 0

    @pytest.mark.asyncio
    async def test_workflow_with_audit(self, readiness_engine: ReadinessRuleEngine):
        """Workflow should log audit events."""
        mock_audit = AsyncMock()
        mock_audit.log = AsyncMock()

        workflow = WorkOrderReadinessWorkflow(
            readiness_engine=readiness_engine,
            audit_logger=mock_audit,
        )

        work_order = {
            "work_order_id": "WO-003",
            "required_skills": [],
            "engineer": {"id": "ENG-001", "skills": [], "certifications": []},
            "required_certifications": [],
            "required_permits": [],
            "materials": [],
            "schedule": {"scheduled_date": "2024-04-01"},
        }

        await workflow.run(case_id="case-003", work_order=work_order, tenant_id="tenant-001")
        mock_audit.log.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_uses_sample_data(self, readiness_engine: ReadinessRuleEngine, sample_work_order: dict[str, Any]):
        """Workflow should work with sample fixture data."""
        workflow = WorkOrderReadinessWorkflow(readiness_engine=readiness_engine)
        result = await workflow.run(
            case_id="case-004",
            work_order=sample_work_order,
            tenant_id="tenant-001",
        )
        assert result.work_order_id == "WO-2024-001"
        # Sample has a pending permit, so should be blocked
        assert result.verdict == "blocked"
