"""Tests for the margin diagnosis workflow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain_packs.contract_margin.rules.leakage_rules import (
    LeakageRuleEngine,
    WorkHistoryEntry,
)
from domain_packs.contract_margin.schemas.contract_schemas import (
    ParsedContract,
    RateCardEntry,
)
from domain_packs.contract_margin.taxonomy.contract_taxonomy import (
    BillableCategory,
    ContractType,
)
from workflows.margin_diagnosis.workflow import (
    MarginDiagnosisWorkflow,
    MarginDiagnosisResult,
)


@pytest.fixture
def leakage_engine() -> LeakageRuleEngine:
    return LeakageRuleEngine()


@pytest.fixture
def test_contract() -> ParsedContract:
    return ParsedContract(
        contract_type=ContractType.master_services,
        title="Test MSA",
        billing_category=BillableCategory.time_and_materials,
        rate_card=[
            RateCardEntry(role_or_item="standard_maintenance", rate=125.0),
        ],
        clauses=[],
    )


class TestMarginDiagnosisWorkflow:
    """Tests for MarginDiagnosisWorkflow."""

    @pytest.mark.asyncio
    async def test_healthy_margin(self, leakage_engine: LeakageRuleEngine, test_contract: ParsedContract):
        """No leakage should produce 'healthy' verdict."""
        workflow = MarginDiagnosisWorkflow(leakage_engine=leakage_engine)

        history = [
            WorkHistoryEntry(
                entry_id="WH-001",
                description="Standard maintenance",
                role="standard_maintenance",
                hours=8.0,
                actual_rate=125.0,
                date="2024-03-01",
                billed=True,
                in_original_scope=True,
            ),
        ]

        result = await workflow.run(
            case_id="case-001",
            billing_record_id="BR-001",
            contract=test_contract,
            work_history=history,
        )

        assert isinstance(result, MarginDiagnosisResult)
        assert result.verdict == "healthy"
        assert result.leakage_amount is None or result.leakage_amount == 0

    @pytest.mark.asyncio
    async def test_leakage_detected(self, leakage_engine: LeakageRuleEngine, test_contract: ParsedContract):
        """Unbilled work should produce leakage verdict."""
        workflow = MarginDiagnosisWorkflow(leakage_engine=leakage_engine)

        history = [
            WorkHistoryEntry(
                entry_id="WH-002",
                description="Unbilled maintenance",
                role="standard_maintenance",
                hours=100.0,
                actual_rate=125.0,
                date="2024-03-01",
                billed=False,
                in_original_scope=True,
            ),
        ]

        result = await workflow.run(
            case_id="case-002",
            billing_record_id="BR-002",
            contract=test_contract,
            work_history=history,
        )

        assert result.verdict in ("at_risk", "leaking", "critical")
        assert result.leakage_amount is not None
        assert result.leakage_amount > 0
        assert len(result.leakage_reasons) > 0
        assert len(result.recommendations) > 0

    @pytest.mark.asyncio
    async def test_workflow_without_engines(self):
        """Workflow without engines should complete with healthy verdict."""
        workflow = MarginDiagnosisWorkflow()
        result = await workflow.run(
            case_id="case-003",
            billing_record_id="BR-003",
        )
        assert result.verdict == "healthy"

    @pytest.mark.asyncio
    async def test_workflow_audit(self, leakage_engine: LeakageRuleEngine, test_contract: ParsedContract):
        """Workflow should log audit events."""
        mock_audit = AsyncMock()
        mock_audit.log = AsyncMock()

        workflow = MarginDiagnosisWorkflow(
            leakage_engine=leakage_engine,
            audit_logger=mock_audit,
        )

        history = [
            WorkHistoryEntry(
                entry_id="WH-003",
                description="Work",
                role="standard_maintenance",
                hours=4.0,
                actual_rate=125.0,
                date="2024-03-01",
                billed=True,
                in_original_scope=True,
            ),
        ]

        await workflow.run(
            case_id="case-004",
            billing_record_id="BR-004",
            contract=test_contract,
            work_history=history,
        )
        mock_audit.log.assert_called_once()
