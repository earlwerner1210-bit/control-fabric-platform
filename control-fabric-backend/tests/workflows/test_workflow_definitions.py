"""Tests for workflow class attributes, activity definitions, and data structures.

Since the Temporal workflow modules cannot be imported directly in tests
(they require the Temporal sandbox with RetryPolicy), these tests verify
structural properties by reading the source files and by testing the I/O
schemas used by the workflows.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.workflows import (
    ContractCompileInput,
    ContractCompileOutput,
    MarginDiagnosisInput,
    MarginDiagnosisOutput,
    MarginVerdict,
    ValidationStatus,
    WorkflowStatusEnum,
)

_WORKFLOW_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "workflows"
_CC_SOURCE = (_WORKFLOW_DIR / "contract_compile" / "workflow.py").read_text()
_MD_SOURCE = (_WORKFLOW_DIR / "margin_diagnosis" / "workflow.py").read_text()


# ---------------------------------------------------------------------------
# ContractCompileWorkflow structural tests
# ---------------------------------------------------------------------------


class TestContractCompileWorkflowDefinition:
    """Verify the contract_compile workflow module defines expected symbols."""

    def test_module_file_exists(self):
        assert (_WORKFLOW_DIR / "contract_compile" / "workflow.py").exists()

    def test_source_contains_workflow_defn(self):
        assert "@workflow.defn" in _CC_SOURCE
        assert "class ContractCompileWorkflow" in _CC_SOURCE

    def test_source_defines_activities(self):
        expected_activities = [
            "load_documents_activity",
            "parse_documents_activity",
            "compile_objects_activity",
            "validate_output_activity",
            "log_audit_activity",
        ]
        for act in expected_activities:
            assert f"async def {act}" in _CC_SOURCE, f"Activity {act} not found"

    def test_source_defines_workflow_input(self):
        assert "class WorkflowInput" in _CC_SOURCE
        assert "tenant_id" in _CC_SOURCE
        assert "user_id" in _CC_SOURCE
        assert "payload" in _CC_SOURCE

    def test_source_defines_workflow_output(self):
        assert "class WorkflowOutput" in _CC_SOURCE
        assert "case_id" in _CC_SOURCE
        assert "errors" in _CC_SOURCE

    def test_source_has_retry_policy(self):
        assert "RetryPolicy" in _CC_SOURCE
        assert "maximum_attempts" in _CC_SOURCE

    def test_activity_count(self):
        count = _CC_SOURCE.count("@activity.defn")
        assert count == 5


# ---------------------------------------------------------------------------
# MarginDiagnosisWorkflow structural tests
# ---------------------------------------------------------------------------


class TestMarginDiagnosisWorkflowDefinition:
    """Verify the margin_diagnosis workflow module defines expected symbols."""

    def test_module_file_exists(self):
        assert (_WORKFLOW_DIR / "margin_diagnosis" / "workflow.py").exists()

    def test_source_contains_workflow_defn(self):
        assert "@workflow.defn" in _MD_SOURCE
        assert "class MarginDiagnosisWorkflow" in _MD_SOURCE

    def test_source_defines_activities(self):
        expected_activities = [
            "load_contract_objects_activity",
            "parse_work_order_activity",
            "parse_incident_activity",
            "reconcile_activity",
            "run_inference_activity",
            "validate_diagnosis_activity",
            "persist_results_activity",
            "log_audit_activity",
        ]
        for act in expected_activities:
            assert f"async def {act}" in _MD_SOURCE, f"Activity {act} not found"

    def test_source_has_retry_policy(self):
        assert "RetryPolicy" in _MD_SOURCE
        assert "maximum_attempts" in _MD_SOURCE

    def test_source_has_inference_timeout(self):
        assert "_INFERENCE_TIMEOUT" in _MD_SOURCE

    def test_activity_count(self):
        count = _MD_SOURCE.count("@activity.defn")
        assert count == 8

    def test_source_defines_workflow_input(self):
        assert "class WorkflowInput" in _MD_SOURCE
        assert "tenant_id" in _MD_SOURCE

    def test_source_defines_workflow_output(self):
        assert "class WorkflowOutput" in _MD_SOURCE
        assert "case_id" in _MD_SOURCE


# ---------------------------------------------------------------------------
# Workflow I/O schema tests (using the API schemas)
# ---------------------------------------------------------------------------


class TestWorkflowIOSchemas:
    def test_contract_compile_input_defaults(self):
        inp = ContractCompileInput(contract_document_id=uuid4())
        assert inp.sla_document_ids == []
        assert inp.rate_card_document_ids == []

    def test_contract_compile_output_defaults(self):
        out = ContractCompileOutput(
            case_id=uuid4(),
            status=WorkflowStatusEnum.COMPLETED,
        )
        assert out.obligation_count == 0
        assert out.penalty_count == 0

    def test_contract_compile_output_validation_status(self):
        out = ContractCompileOutput(
            case_id=uuid4(),
            status=WorkflowStatusEnum.COMPLETED,
            validation_status=ValidationStatus.APPROVED,
        )
        assert out.validation_status == ValidationStatus.APPROVED

    def test_margin_diagnosis_input_defaults(self):
        inp = MarginDiagnosisInput(contract_document_id=uuid4())
        assert inp.work_order_document_id is None
        assert inp.incident_document_id is None

    def test_margin_diagnosis_output_defaults(self):
        out = MarginDiagnosisOutput(
            case_id=uuid4(),
            verdict=MarginVerdict.BILLABLE,
        )
        assert out.leakage_drivers == []
        assert out.recovery_recommendations == []

    def test_margin_verdict_enum_values(self):
        assert MarginVerdict.BILLABLE == "billable"
        assert MarginVerdict.NON_BILLABLE == "non_billable"
        assert MarginVerdict.UNDER_RECOVERY == "under_recovery"
        assert MarginVerdict.PENALTY_RISK == "penalty_risk"

    def test_workflow_status_enum_values(self):
        assert WorkflowStatusEnum.PENDING.value == "pending"
        assert WorkflowStatusEnum.COMPLETED.value == "completed"
        assert WorkflowStatusEnum.FAILED.value == "failed"
