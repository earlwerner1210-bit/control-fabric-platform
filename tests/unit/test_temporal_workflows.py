"""Tests for Temporal workflow definitions."""

from __future__ import annotations

from app.workflows.temporal_workflows import (
    ContractCompileWorkflow,
    IncidentDispatchWorkflow,
    MarginDiagnosisWorkflow,
    WorkflowInput,
    WorkflowOutput,
    WorkOrderReadinessWorkflow,
)


class TestWorkflowInput:
    """Test WorkflowInput dataclass."""

    def test_create(self):
        inp = WorkflowInput(
            tenant_id="tenant-001",
            user_id="user-001",
            payload={"document_id": "doc-001"},
        )
        assert inp.tenant_id == "tenant-001"
        assert inp.payload["document_id"] == "doc-001"

    def test_empty_payload(self):
        inp = WorkflowInput(tenant_id="t", user_id="u", payload={})
        assert inp.payload == {}


class TestWorkflowOutput:
    """Test WorkflowOutput dataclass."""

    def test_create(self):
        out = WorkflowOutput(
            case_id="case-001",
            status="completed",
            output={"verdict": "billable"},
            errors=[],
        )
        assert out.status == "completed"
        assert out.output["verdict"] == "billable"
        assert len(out.errors) == 0

    def test_with_errors(self):
        out = WorkflowOutput(
            case_id="case-002",
            status="failed",
            output={},
            errors=["Parse failed", "Validation error"],
        )
        assert out.status == "failed"
        assert len(out.errors) == 2


class TestWorkflowRegistration:
    """Test that workflow classes have the correct structure."""

    def test_contract_compile_has_run(self):
        assert hasattr(ContractCompileWorkflow, "run")

    def test_readiness_has_run(self):
        assert hasattr(WorkOrderReadinessWorkflow, "run")

    def test_incident_dispatch_has_run(self):
        assert hasattr(IncidentDispatchWorkflow, "run")

    def test_margin_diagnosis_has_run(self):
        assert hasattr(MarginDiagnosisWorkflow, "run")


class TestWorkerModule:
    """Test worker module imports."""

    def test_worker_imports(self):
        from app.workflows.worker import ACTIVITIES, WORKFLOWS

        assert len(WORKFLOWS) == 4
        assert len(ACTIVITIES) == 6

    def test_main_callable(self):
        from app.workflows.worker import main

        assert callable(main)
