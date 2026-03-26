"""Tests for margin diagnosis workflow structure and I/O schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from app.schemas.workflows import (
    MarginDiagnosisInput,
    MarginDiagnosisOutput,
    MarginVerdict,
    WorkflowStatusEnum,
)


# ── Workflow dataclasses (mirroring Temporal workflow structure) ──────────────


@dataclass
class MarginDiagnosisWorkflowInput:
    """Input for the margin diagnosis Temporal workflow."""

    contract_document_id: str
    contract_case_id: str = ""
    work_order_document_id: str = ""
    incident_document_id: str = ""
    execution_history: list[dict] = field(default_factory=list)
    tenant_id: str = ""
    user_id: str = ""


@dataclass
class MarginDiagnosisWorkflowOutput:
    """Output from the margin diagnosis Temporal workflow."""

    case_id: str
    verdict: str = "unknown"
    leakage_drivers: list[str] = field(default_factory=list)
    recovery_recommendations: list[str] = field(default_factory=list)
    evidence_object_ids: list[str] = field(default_factory=list)
    executive_summary: str = ""
    total_leakage_value: float = 0.0
    penalty_exposure: float = 0.0


class MarginDiagnosisWorkflow:
    """Placeholder workflow class for structural testing."""

    TASK_QUEUE = "control-fabric-queue"
    WORKFLOW_ID_PREFIX = "margin-diagnosis"

    @staticmethod
    def build_workflow_id(contract_id: str) -> str:
        return f"margin-diagnosis-{contract_id}"

    @staticmethod
    def activities() -> list[str]:
        return [
            "load_contract_compile",
            "evaluate_billability",
            "detect_leakage",
            "analyze_penalties",
            "assemble_evidence",
            "generate_recovery_recommendations",
            "reconcile_margin",
            "validate_diagnosis",
            "create_audit_event",
        ]


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestMarginDiagnosisWorkflowInput:
    def test_input_creation(self):
        inp = MarginDiagnosisWorkflowInput(
            contract_document_id=str(uuid4()),
        )
        assert inp.contract_document_id
        assert inp.work_order_document_id == ""

    def test_input_with_all_fields(self):
        inp = MarginDiagnosisWorkflowInput(
            contract_document_id=str(uuid4()),
            contract_case_id=str(uuid4()),
            work_order_document_id=str(uuid4()),
            incident_document_id=str(uuid4()),
            execution_history=[{"type": "switching", "status": "completed"}],
        )
        assert len(inp.execution_history) == 1


class TestMarginDiagnosisWorkflowOutput:
    def test_output_creation(self):
        out = MarginDiagnosisWorkflowOutput(
            case_id=str(uuid4()),
            verdict="billable",
        )
        assert out.verdict == "billable"
        assert out.total_leakage_value == 0.0

    def test_output_with_leakage(self):
        out = MarginDiagnosisWorkflowOutput(
            case_id=str(uuid4()),
            verdict="partial",
            leakage_drivers=["unbilled_completed_work", "missing_daywork_sheet"],
            total_leakage_value=450.0,
        )
        assert len(out.leakage_drivers) == 2
        assert out.total_leakage_value == 450.0


class TestMarginDiagnosisWorkflow:
    def test_workflow_id_generation(self):
        contract_id = str(uuid4())
        wf_id = MarginDiagnosisWorkflow.build_workflow_id(contract_id)
        assert wf_id.startswith("margin-diagnosis-")

    def test_activities_registered(self):
        activities = MarginDiagnosisWorkflow.activities()
        assert len(activities) == 9
        assert "evaluate_billability" in activities
        assert "detect_leakage" in activities
        assert "reconcile_margin" in activities

    def test_task_queue(self):
        assert MarginDiagnosisWorkflow.TASK_QUEUE == "control-fabric-queue"


class TestMarginDiagnosisSchemas:
    def test_input_schema(self):
        inp = MarginDiagnosisInput(contract_document_id=uuid4())
        assert isinstance(inp.contract_document_id, UUID)
        assert inp.work_order_document_id is None

    def test_output_schema(self):
        out = MarginDiagnosisOutput(
            case_id=uuid4(),
            verdict=MarginVerdict.BILLABLE,
        )
        assert out.verdict == MarginVerdict.BILLABLE
        assert out.leakage_drivers == []

    def test_verdict_enum_values(self):
        assert MarginVerdict.BILLABLE == "billable"
        assert MarginVerdict.NON_BILLABLE == "non_billable"
        assert MarginVerdict.UNDER_RECOVERY == "under_recovery"
        assert MarginVerdict.PENALTY_RISK == "penalty_risk"
