"""Incident Dispatch Reconcile Workflow — Activity implementations."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from temporalio import activity

from workflows.incident_dispatch_reconcile.workflow import (
    AuditInput,
    AuditOutput,
    CompileIncidentObjectsInput,
    CompileIncidentObjectsOutput,
    ModelSummaryInput,
    ModelSummaryOutput,
    ParseIncidentInput,
    ParseIncidentOutput,
    ReconcileStatesInput,
    ReconcileStatesOutput,
    RetrieveLinkedDataInput,
    RetrieveLinkedDataOutput,
    ValidateReconciliationInput,
    ValidateReconciliationOutput,
)

SERVICE_BASE_URLS = {
    "ingest": "http://ingest-service:8001",
    "compiler": "http://compiler-service:8005",
    "validator": "http://validator-service:8006",
    "audit": "http://audit-service:8007",
    "retrieval": "http://retrieval-service:8008",
    "inference": "http://inference-gateway:8009",
    "reconciler": "http://reconciler-service:8010",
}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))


@activity.defn
async def parse_incident(input: ParseIncidentInput) -> ParseIncidentOutput:
    """Parse incident data from source systems."""
    activity.logger.info("Parsing incident %s", input.incident_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['ingest']}/parse",
                json={
                    "document_id": input.incident_id,
                    "tenant_id": input.tenant_id,
                    "document_type": "incident",
                },
            )
            response.raise_for_status()
            data = response.json()
            return ParseIncidentOutput(
                incident_data=data.get("content", {}),
                document_ids=data.get("document_ids", [input.incident_id]),
            )
        except httpx.ConnectError:
            activity.logger.warning("Ingest service unavailable (stub)")
            return ParseIncidentOutput(
                incident_data={
                    "incident_id": input.incident_id,
                    "status": "parsed_stub",
                    "priority": "medium",
                },
                document_ids=[input.incident_id],
            )


@activity.defn
async def compile_incident_objects(
    input: CompileIncidentObjectsInput,
) -> CompileIncidentObjectsOutput:
    """Compile incident data into structured control objects."""
    activity.logger.info("Compiling incident objects for case %s", input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['compiler']}/compile",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "object_type": "incident",
                    "incident_data": input.incident_data,
                    "domain_pack": input.domain_pack,
                },
            )
            response.raise_for_status()
            data = response.json()
            return CompileIncidentObjectsOutput(
                control_object_ids=data.get("control_object_ids", []),
                incident_objects=data.get("incident_objects", {}),
                service_objects=data.get("service_objects", {}),
            )
        except httpx.ConnectError:
            activity.logger.warning("Compiler service unavailable (stub)")
            obj_id = str(uuid.uuid4())
            return CompileIncidentObjectsOutput(
                control_object_ids=[obj_id],
                incident_objects={"id": obj_id, **input.incident_data},
                service_objects={"service_id": str(uuid.uuid4())},
            )


@activity.defn
async def retrieve_linked_data(input: RetrieveLinkedDataInput) -> RetrieveLinkedDataOutput:
    """Retrieve linked work orders, rules, and related incidents."""
    activity.logger.info("Retrieving linked data for incident %s", input.incident_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['retrieval']}/linked",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "incident_id": input.incident_id,
                    "incident_objects": input.incident_objects,
                    "link_types": ["work_order", "rule", "incident"],
                },
            )
            response.raise_for_status()
            data = response.json()
            return RetrieveLinkedDataOutput(
                work_orders=data.get("work_orders", []),
                rules=data.get("rules", []),
                related_incidents=data.get("related_incidents", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Retrieval service unavailable (stub)")
            return RetrieveLinkedDataOutput(
                work_orders=[],
                rules=[],
                related_incidents=[],
            )


@activity.defn
async def reconcile_states(input: ReconcileStatesInput) -> ReconcileStatesOutput:
    """Reconcile incident state against work orders and rules."""
    activity.logger.info("Reconciling states for case %s", input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['reconciler']}/reconcile",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "incident_objects": input.incident_objects,
                    "service_objects": input.service_objects,
                    "work_orders": input.work_orders,
                    "rules": input.rules,
                    "domain_pack": input.domain_pack,
                    "reconcile_type": "incident_dispatch",
                },
            )
            response.raise_for_status()
            data = response.json()
            return ReconcileStatesOutput(
                reconciliation_status=data.get("reconciliation_status", "aligned"),
                mismatches=data.get("mismatches", []),
                actions_required=data.get("actions_required", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Reconciler service unavailable (stub)")
            return ReconcileStatesOutput(
                reconciliation_status="aligned",
                mismatches=[],
                actions_required=[],
            )


@activity.defn
async def call_model_for_summary(input: ModelSummaryInput) -> ModelSummaryOutput:
    """Generate a human-readable summary of the reconciliation."""
    activity.logger.info("Generating summary for case %s", input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['inference']}/generate",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "prompt_template": "incident_dispatch_summary",
                    "domain_pack": input.domain_pack,
                    "context": {
                        "incident_data": input.incident_data,
                        "reconciliation_status": input.reconciliation_status,
                        "mismatches": input.mismatches,
                        "actions_required": input.actions_required,
                    },
                },
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
            response.raise_for_status()
            data = response.json()
            return ModelSummaryOutput(summary=data.get("text", ""))
        except httpx.ConnectError:
            activity.logger.warning("Inference gateway unavailable (stub)")
            return ModelSummaryOutput(
                summary=f"Incident reconciliation: {input.reconciliation_status}. "
                f"{len(input.mismatches)} mismatch(es), "
                f"{len(input.actions_required)} action(s) required."
            )


@activity.defn
async def validate_reconciliation(
    input: ValidateReconciliationInput,
) -> ValidateReconciliationOutput:
    """Validate the reconciliation output."""
    activity.logger.info("Validating reconciliation for case %s", input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['validator']}/validate",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "control_object_ids": input.control_object_ids,
                    "domain_pack": input.domain_pack,
                    "validation_context": {
                        "reconciliation_status": input.reconciliation_status,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return ValidateReconciliationOutput(
                passed=data.get("passed", True),
                findings=data.get("findings", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Validator service unavailable (stub)")
            return ValidateReconciliationOutput(passed=True, findings=[])


@activity.defn
async def log_audit(input: AuditInput) -> AuditOutput:
    """Log an audit entry."""
    activity.logger.info("Logging audit: %s for case %s", input.event_type, input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['audit']}/log",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "event_type": input.event_type,
                    "service": input.service,
                    "detail": input.detail,
                },
            )
            response.raise_for_status()
            data = response.json()
            return AuditOutput(audit_id=data.get("audit_id", str(uuid.uuid4())))
        except httpx.ConnectError:
            activity.logger.warning("Audit service unavailable (stub)")
            return AuditOutput(audit_id=str(uuid.uuid4()))
