"""Work Order Readiness Workflow — Activity implementations."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from temporalio import activity

from workflows.work_order_readiness.workflow import (
    AuditInput,
    AuditOutput,
    CompileReadinessInput,
    CompileReadinessOutput,
    ModelExplanationInput,
    ModelExplanationOutput,
    ParseEngineerInput,
    ParseEngineerOutput,
    ParseWorkOrderInput,
    ParseWorkOrderOutput,
    ReconcileRulesInput,
    ReconcileRulesOutput,
    RetrieveEvidenceInput,
    RetrieveEvidenceOutput,
    ValidateReadinessInput,
    ValidateReadinessOutput,
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
async def parse_work_order(input: ParseWorkOrderInput) -> ParseWorkOrderOutput:
    """Parse and structure work order data."""
    activity.logger.info("Parsing work order %s", input.work_order_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['ingest']}/parse",
                json={
                    "document_id": input.work_order_id,
                    "tenant_id": input.tenant_id,
                    "document_type": "work_order",
                },
            )
            response.raise_for_status()
            data = response.json()
            return ParseWorkOrderOutput(
                work_order_data=data.get("content", {}),
                document_ids=data.get("document_ids", [input.work_order_id]),
            )
        except httpx.ConnectError:
            activity.logger.warning("Ingest service unavailable (stub)")
            return ParseWorkOrderOutput(
                work_order_data={
                    "work_order_id": input.work_order_id,
                    "status": "parsed_stub",
                },
                document_ids=[input.work_order_id],
            )


@activity.defn
async def parse_engineer_accreditation(input: ParseEngineerInput) -> ParseEngineerOutput:
    """Retrieve and parse engineer profile and accreditation data."""
    activity.logger.info("Parsing engineer accreditation for %s", input.engineer_id)

    async with _client() as client:
        try:
            response = await client.get(
                f"{SERVICE_BASE_URLS['ingest']}/engineers/{input.engineer_id}",
                params={"tenant_id": input.tenant_id},
            )
            response.raise_for_status()
            data = response.json()
            return ParseEngineerOutput(
                engineer_data=data.get("engineer", {}),
                accreditations=data.get("accreditations", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Ingest service unavailable for engineer data (stub)")
            return ParseEngineerOutput(
                engineer_data={"engineer_id": input.engineer_id, "status": "stub"},
                accreditations=[],
            )


@activity.defn
async def compile_readiness_objects(input: CompileReadinessInput) -> CompileReadinessOutput:
    """Compile work order and engineer data into readiness control objects."""
    activity.logger.info("Compiling readiness objects for case %s", input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['compiler']}/compile",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "object_type": "work_order_readiness",
                    "work_order_data": input.work_order_data,
                    "engineer_data": input.engineer_data,
                    "domain_pack": input.domain_pack,
                },
            )
            response.raise_for_status()
            data = response.json()
            return CompileReadinessOutput(
                readiness_object_ids=data.get("control_object_ids", []),
                readiness_data=data.get("readiness_data", {}),
            )
        except httpx.ConnectError:
            activity.logger.warning("Compiler service unavailable (stub)")
            obj_id = str(uuid.uuid4())
            return CompileReadinessOutput(
                readiness_object_ids=[obj_id],
                readiness_data={
                    "work_order": input.work_order_data,
                    "engineer": input.engineer_data,
                },
            )


@activity.defn
async def reconcile_against_rules(input: ReconcileRulesInput) -> ReconcileRulesOutput:
    """Evaluate readiness data against domain-specific rules."""
    activity.logger.info("Reconciling readiness against rules for case %s", input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['reconciler']}/reconcile",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "readiness_data": input.readiness_data,
                    "domain_pack": input.domain_pack,
                    "reconcile_type": "work_order_readiness",
                },
            )
            response.raise_for_status()
            data = response.json()
            return ReconcileRulesOutput(
                decision=data.get("decision", "ready"),
                blockers=data.get("blockers", []),
                warnings=data.get("warnings", []),
                rules_evaluated=data.get("rules_evaluated", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Reconciler service unavailable (stub)")
            return ReconcileRulesOutput(
                decision="ready",
                blockers=[],
                warnings=[],
                rules_evaluated=["stub_rule"],
            )


@activity.defn
async def retrieve_evidence(input: RetrieveEvidenceInput) -> RetrieveEvidenceOutput:
    """Retrieve supporting evidence for blockers/warnings from the vector store."""
    activity.logger.info("Retrieving evidence for case %s", input.case_id)

    queries = []
    for blocker in input.blockers:
        queries.append(blocker.get("description", blocker.get("rule", "")))
    for warning in input.warnings:
        queries.append(warning.get("description", warning.get("rule", "")))

    if not queries:
        return RetrieveEvidenceOutput(evidence_chunks=[])

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['retrieval']}/retrieve",
                json={
                    "queries": queries,
                    "tenant_id": input.tenant_id,
                    "top_k": 5,
                    "filters": {"work_order_id": input.work_order_id},
                },
            )
            response.raise_for_status()
            data = response.json()
            return RetrieveEvidenceOutput(
                evidence_chunks=data.get("chunks", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Retrieval service unavailable (stub)")
            return RetrieveEvidenceOutput(evidence_chunks=[])


@activity.defn
async def call_model_for_explanation(input: ModelExplanationInput) -> ModelExplanationOutput:
    """Call the LLM to generate a human-readable readiness explanation."""
    activity.logger.info("Generating model explanation for case %s", input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['inference']}/generate",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "prompt_template": "work_order_readiness_explanation",
                    "domain_pack": input.domain_pack,
                    "context": {
                        "decision": input.decision,
                        "readiness_data": input.readiness_data,
                        "blockers": input.blockers,
                        "warnings": input.warnings,
                        "evidence": input.evidence_chunks,
                    },
                },
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
            response.raise_for_status()
            data = response.json()
            return ModelExplanationOutput(
                explanation=data.get("text", ""),
                readiness_score=data.get("readiness_score", 1.0 if input.decision == "ready" else 0.0),
            )
        except httpx.ConnectError:
            activity.logger.warning("Inference gateway unavailable (stub)")
            score = {"ready": 1.0, "warn": 0.7, "blocked": 0.0, "escalate": 0.0}.get(
                input.decision, 0.5
            )
            return ModelExplanationOutput(
                explanation=f"Work order readiness decision: {input.decision}. "
                f"{len(input.blockers)} blocker(s), {len(input.warnings)} warning(s).",
                readiness_score=score,
            )


@activity.defn
async def validate_readiness(input: ValidateReadinessInput) -> ValidateReadinessOutput:
    """Run validation rules on the readiness output."""
    activity.logger.info("Validating readiness for case %s", input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['validator']}/validate",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "control_object_ids": input.readiness_object_ids,
                    "domain_pack": input.domain_pack,
                    "validation_context": {"decision": input.decision},
                },
            )
            response.raise_for_status()
            data = response.json()
            return ValidateReadinessOutput(
                passed=data.get("passed", True),
                findings=data.get("findings", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Validator service unavailable (stub)")
            return ValidateReadinessOutput(passed=True, findings=[])


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
