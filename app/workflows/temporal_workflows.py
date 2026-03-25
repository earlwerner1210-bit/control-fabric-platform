"""Temporal workflow definitions.

These are the Temporal SDK workflow classes that would be registered with
the Temporal worker. They delegate to activities that call the same service
layer used by the in-process orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import activity, workflow


# ── Shared dataclasses for Temporal serialization ──────────────


@dataclass
class WorkflowInput:
    tenant_id: str
    user_id: str
    payload: dict[str, Any]


@dataclass
class WorkflowOutput:
    case_id: str
    status: str
    output: dict[str, Any]
    errors: list[str]


# ── Activities ─────────────────────────────────────────────────


@activity.defn
async def parse_documents_activity(input_data: dict) -> dict:
    """Parse uploaded documents."""
    # In production: instantiate IngestService, call parse
    return {"status": "parsed", "document_ids": input_data.get("document_ids", [])}


@activity.defn
async def chunk_and_embed_activity(input_data: dict) -> dict:
    """Chunk and embed parsed documents."""
    return {"status": "embedded", "chunk_count": 0}


@activity.defn
async def compile_objects_activity(input_data: dict) -> dict:
    """Compile control objects from parsed data."""
    return {"status": "compiled", "object_count": 0, "object_ids": []}


@activity.defn
async def validate_output_activity(input_data: dict) -> dict:
    """Run validation pipeline."""
    return {"status": "passed", "rule_results": []}


@activity.defn
async def log_audit_activity(input_data: dict) -> dict:
    """Log audit event."""
    return {"status": "logged"}


@activity.defn
async def run_inference_activity(input_data: dict) -> dict:
    """Call inference gateway."""
    return {"status": "completed", "output": {}}


# ── Contract Compile Workflow ──────────────────────────────────


@workflow.defn
class ContractCompileWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowOutput:
        retry_policy = workflow.RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        # Step 1: Parse
        parse_result = await workflow.execute_activity(
            parse_documents_activity,
            input_data.payload,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )

        # Step 2: Chunk and embed
        await workflow.execute_activity(
            chunk_and_embed_activity,
            parse_result,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )

        # Step 3: Compile
        compile_result = await workflow.execute_activity(
            compile_objects_activity,
            {**parse_result, "workflow_type": "contract_compile"},
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )

        # Step 4: Validate
        validation = await workflow.execute_activity(
            validate_output_activity,
            compile_result,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry_policy,
        )

        # Step 5: Audit
        await workflow.execute_activity(
            log_audit_activity,
            {"event": "contract_compile_complete", "case_id": input_data.payload.get("case_id")},
            start_to_close_timeout=timedelta(seconds=30),
        )

        return WorkflowOutput(
            case_id=input_data.payload.get("case_id", ""),
            status="completed",
            output=compile_result,
            errors=[],
        )


# ── Work Order Readiness Workflow ──────────────────────────────


@workflow.defn
class WorkOrderReadinessWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowOutput:
        retry_policy = workflow.RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=3)

        parse_result = await workflow.execute_activity(
            parse_documents_activity, input_data.payload,
            start_to_close_timeout=timedelta(minutes=5), retry_policy=retry_policy,
        )
        compile_result = await workflow.execute_activity(
            compile_objects_activity, {**parse_result, "workflow_type": "work_order_readiness"},
            start_to_close_timeout=timedelta(minutes=5), retry_policy=retry_policy,
        )
        inference_result = await workflow.execute_activity(
            run_inference_activity, compile_result,
            start_to_close_timeout=timedelta(minutes=5), retry_policy=retry_policy,
        )
        validation = await workflow.execute_activity(
            validate_output_activity, inference_result,
            start_to_close_timeout=timedelta(minutes=2), retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            log_audit_activity, {"event": "readiness_complete"},
            start_to_close_timeout=timedelta(seconds=30),
        )

        return WorkflowOutput(case_id="", status="completed", output=inference_result, errors=[])


# ── Incident Dispatch Workflow ─────────────────────────────────


@workflow.defn
class IncidentDispatchWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowOutput:
        retry_policy = workflow.RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=3)

        parse_result = await workflow.execute_activity(
            parse_documents_activity, input_data.payload,
            start_to_close_timeout=timedelta(minutes=5), retry_policy=retry_policy,
        )
        compile_result = await workflow.execute_activity(
            compile_objects_activity, {**parse_result, "workflow_type": "incident_dispatch"},
            start_to_close_timeout=timedelta(minutes=5), retry_policy=retry_policy,
        )
        inference_result = await workflow.execute_activity(
            run_inference_activity, compile_result,
            start_to_close_timeout=timedelta(minutes=5), retry_policy=retry_policy,
        )
        validation = await workflow.execute_activity(
            validate_output_activity, inference_result,
            start_to_close_timeout=timedelta(minutes=2), retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            log_audit_activity, {"event": "incident_dispatch_complete"},
            start_to_close_timeout=timedelta(seconds=30),
        )

        return WorkflowOutput(case_id="", status="completed", output=inference_result, errors=[])


# ── Margin Diagnosis Workflow ──────────────────────────────────


@workflow.defn
class MarginDiagnosisWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowOutput:
        retry_policy = workflow.RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=3)

        parse_result = await workflow.execute_activity(
            parse_documents_activity, input_data.payload,
            start_to_close_timeout=timedelta(minutes=5), retry_policy=retry_policy,
        )
        compile_result = await workflow.execute_activity(
            compile_objects_activity, {**parse_result, "workflow_type": "margin_diagnosis"},
            start_to_close_timeout=timedelta(minutes=5), retry_policy=retry_policy,
        )
        inference_result = await workflow.execute_activity(
            run_inference_activity, compile_result,
            start_to_close_timeout=timedelta(minutes=5), retry_policy=retry_policy,
        )
        validation = await workflow.execute_activity(
            validate_output_activity, inference_result,
            start_to_close_timeout=timedelta(minutes=2), retry_policy=retry_policy,
        )
        await workflow.execute_activity(
            log_audit_activity, {"event": "margin_diagnosis_complete"},
            start_to_close_timeout=timedelta(seconds=30),
        )

        return WorkflowOutput(case_id="", status="completed", output=inference_result, errors=[])
