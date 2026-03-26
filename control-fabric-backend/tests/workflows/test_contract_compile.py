"""Tests for contract compile workflow structure and I/O schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from app.schemas.workflows import (
    ContractCompileInput,
    ContractCompileOutput,
    ValidationStatus,
    WorkflowStatusEnum,
)


# ── Workflow dataclasses (mirroring Temporal workflow structure) ──────────────


@dataclass
class ContractCompileWorkflowInput:
    """Input for the contract compile Temporal workflow."""

    contract_document_id: str
    sla_document_ids: list[str] = field(default_factory=list)
    rate_card_document_ids: list[str] = field(default_factory=list)
    tenant_id: str = ""
    user_id: str = ""


@dataclass
class ContractCompileWorkflowOutput:
    """Output from the contract compile Temporal workflow."""

    case_id: str
    status: str = "completed"
    clause_count: int = 0
    obligation_count: int = 0
    penalty_count: int = 0
    billable_event_count: int = 0
    control_object_ids: list[str] = field(default_factory=list)
    validation_status: str = "approved"
    errors: list[str] = field(default_factory=list)


class ContractCompileWorkflow:
    """Placeholder workflow class for structural testing."""

    TASK_QUEUE = "control-fabric-queue"
    WORKFLOW_ID_PREFIX = "contract-compile"

    @staticmethod
    def build_workflow_id(document_id: str) -> str:
        return f"contract-compile-{document_id}"

    @staticmethod
    def activities() -> list[str]:
        return [
            "parse_contract",
            "extract_clauses",
            "extract_sla_table",
            "extract_rate_card",
            "extract_obligations",
            "extract_penalties",
            "extract_billable_events",
            "create_control_objects",
            "validate_results",
        ]


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestContractCompileWorkflowInput:
    def test_input_creation(self):
        inp = ContractCompileWorkflowInput(
            contract_document_id=str(uuid4()),
            tenant_id=str(uuid4()),
        )
        assert inp.contract_document_id
        assert inp.sla_document_ids == []

    def test_input_with_supplementary_docs(self):
        sla_id = str(uuid4())
        rate_id = str(uuid4())
        inp = ContractCompileWorkflowInput(
            contract_document_id=str(uuid4()),
            sla_document_ids=[sla_id],
            rate_card_document_ids=[rate_id],
        )
        assert len(inp.sla_document_ids) == 1
        assert len(inp.rate_card_document_ids) == 1


class TestContractCompileWorkflowOutput:
    def test_output_creation(self):
        out = ContractCompileWorkflowOutput(
            case_id=str(uuid4()),
            clause_count=6,
            obligation_count=3,
        )
        assert out.clause_count == 6
        assert out.status == "completed"
        assert out.errors == []

    def test_output_with_errors(self):
        out = ContractCompileWorkflowOutput(
            case_id=str(uuid4()),
            status="failed",
            errors=["Parse error on page 3"],
        )
        assert out.status == "failed"
        assert len(out.errors) == 1


class TestContractCompileWorkflow:
    def test_workflow_id_generation(self):
        doc_id = str(uuid4())
        wf_id = ContractCompileWorkflow.build_workflow_id(doc_id)
        assert wf_id.startswith("contract-compile-")
        assert doc_id in wf_id

    def test_activities_list(self):
        activities = ContractCompileWorkflow.activities()
        assert len(activities) == 9
        assert "parse_contract" in activities
        assert "validate_results" in activities

    def test_task_queue(self):
        assert ContractCompileWorkflow.TASK_QUEUE == "control-fabric-queue"


class TestContractCompileSchemas:
    def test_input_schema(self):
        inp = ContractCompileInput(contract_document_id=uuid4())
        assert isinstance(inp.contract_document_id, UUID)

    def test_output_schema(self):
        out = ContractCompileOutput(
            case_id=uuid4(),
            status=WorkflowStatusEnum.COMPLETED,
            obligation_count=5,
            validation_status=ValidationStatus.APPROVED,
        )
        assert out.status == WorkflowStatusEnum.COMPLETED
        assert out.validation_status == ValidationStatus.APPROVED
