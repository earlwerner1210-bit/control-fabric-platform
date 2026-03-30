"""Tests for the contract compile workflow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from workflows.contract_compile.workflow import ContractCompileResult, ContractCompileWorkflow


class TestContractCompileWorkflow:
    """Tests for ContractCompileWorkflow end-to-end with mocked services."""

    @pytest.mark.asyncio
    async def test_compile_workflow_success(self):
        """Compile workflow should parse document and create control objects."""
        # Mock parser
        mock_parser = MagicMock()
        mock_parsed = MagicMock()
        mock_parsed.clauses = [MagicMock(), MagicMock(), MagicMock()]
        mock_parsed.obligations = [MagicMock()]
        mock_parsed.penalties = [MagicMock()]
        mock_parser.parse_contract.return_value = mock_parsed

        # Mock validator
        mock_validator = MagicMock()
        mock_validation_result = MagicMock()
        mock_validation_result.status = MagicMock(value="passed")
        mock_validator.validate.return_value = mock_validation_result

        # Mock audit
        mock_audit = AsyncMock()
        mock_audit.log = AsyncMock()

        workflow = ContractCompileWorkflow(
            parser=mock_parser,
            validator=mock_validator,
            audit_logger=mock_audit,
        )

        result = await workflow.run(
            case_id="case-001",
            document_id="doc-001",
            tenant_id="tenant-001",
        )

        assert isinstance(result, ContractCompileResult)
        assert result.case_id == "case-001"
        assert result.document_id == "doc-001"
        assert result.control_objects_created == 5  # 3 clauses + 1 obligation + 1 penalty
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_compile_workflow_parser_error(self):
        """Compile workflow should handle parser errors gracefully."""
        mock_parser = MagicMock()
        mock_parser.parse_contract.side_effect = ValueError("Parse error")

        workflow = ContractCompileWorkflow(parser=mock_parser)
        result = await workflow.run(
            case_id="case-002",
            document_id="doc-002",
            tenant_id="tenant-001",
        )

        assert result.status == "completed"
        assert any("Parser error" in w for w in result.warnings)
        assert result.control_objects_created == 0

    @pytest.mark.asyncio
    async def test_compile_workflow_no_parser(self):
        """Compile workflow without parser should still complete."""
        workflow = ContractCompileWorkflow()
        result = await workflow.run(
            case_id="case-003",
            document_id="doc-003",
            tenant_id="tenant-001",
        )

        assert result.status == "completed"
        assert result.control_objects_created == 0

    @pytest.mark.asyncio
    async def test_compile_workflow_validation_warning(self):
        """Compile workflow should report validation warnings."""
        mock_validator = MagicMock()
        mock_result = MagicMock()
        mock_result.status = MagicMock(value="warned")
        mock_validator.validate.return_value = mock_result

        workflow = ContractCompileWorkflow(validator=mock_validator)
        result = await workflow.run(
            case_id="case-004",
            document_id="doc-004",
            tenant_id="tenant-001",
        )

        assert any("warning" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_compile_workflow_audit_logged(self):
        """Compile workflow should log audit events."""
        mock_audit = AsyncMock()
        mock_audit.log = AsyncMock()

        workflow = ContractCompileWorkflow(audit_logger=mock_audit)
        await workflow.run(
            case_id="case-005",
            document_id="doc-005",
            tenant_id="tenant-001",
        )

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args
        assert call_kwargs.kwargs["event_type"] == "contract.compiled"
