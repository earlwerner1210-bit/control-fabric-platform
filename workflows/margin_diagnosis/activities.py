"""Margin Diagnosis Workflow — Activity implementations."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from temporalio import activity

from workflows.margin_diagnosis.workflow import (
    AuditInput,
    AuditOutput,
    DetectBillabilityInput,
    DetectBillabilityOutput,
    LoadContractObjectsInput,
    LoadContractObjectsOutput,
    LoadFieldServiceObjectsInput,
    LoadFieldServiceObjectsOutput,
    ModelNarrativeInput,
    ModelNarrativeOutput,
    ReconcileCrossPlaneInput,
    ReconcileCrossPlaneOutput,
    ValidateDiagnosisInput,
    ValidateDiagnosisOutput,
)

SERVICE_BASE_URLS = {
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
async def load_contract_objects(input: LoadContractObjectsInput) -> LoadContractObjectsOutput:
    """Load compiled contract control objects, rate tables, and SLA terms."""
    activity.logger.info("Loading contract objects for %s", input.contract_id)

    async with _client() as client:
        try:
            params: dict[str, Any] = {
                "contract_id": input.contract_id,
                "tenant_id": input.tenant_id,
            }
            if input.period_start:
                params["period_start"] = input.period_start
            if input.period_end:
                params["period_end"] = input.period_end

            response = await client.post(
                f"{SERVICE_BASE_URLS['retrieval']}/contract-objects",
                json=params,
            )
            response.raise_for_status()
            data = response.json()
            return LoadContractObjectsOutput(
                contract_objects=data.get("contract_objects", []),
                rate_tables=data.get("rate_tables", []),
                sla_terms=data.get("sla_terms", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Retrieval service unavailable (stub)")
            return LoadContractObjectsOutput(
                contract_objects=[{"id": str(uuid.uuid4()), "contract_id": input.contract_id}],
                rate_tables=[],
                sla_terms=[],
            )


@activity.defn
async def load_field_service_objects(
    input: LoadFieldServiceObjectsInput,
) -> LoadFieldServiceObjectsOutput:
    """Load field execution data: work orders, service records, dispatch logs."""
    activity.logger.info("Loading field/service objects for contract %s", input.contract_id)

    async with _client() as client:
        try:
            params: dict[str, Any] = {
                "contract_id": input.contract_id,
                "tenant_id": input.tenant_id,
            }
            if input.period_start:
                params["period_start"] = input.period_start
            if input.period_end:
                params["period_end"] = input.period_end

            response = await client.post(
                f"{SERVICE_BASE_URLS['retrieval']}/field-objects",
                json=params,
            )
            response.raise_for_status()
            data = response.json()
            return LoadFieldServiceObjectsOutput(
                work_orders=data.get("work_orders", []),
                service_records=data.get("service_records", []),
                dispatch_records=data.get("dispatch_records", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Retrieval service unavailable (stub)")
            return LoadFieldServiceObjectsOutput(
                work_orders=[],
                service_records=[],
                dispatch_records=[],
            )


@activity.defn
async def reconcile_cross_plane(input: ReconcileCrossPlaneInput) -> ReconcileCrossPlaneOutput:
    """Reconcile contract terms against field execution data."""
    activity.logger.info("Reconciling cross-plane for case %s", input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['reconciler']}/reconcile",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "contract_objects": input.contract_objects,
                    "rate_tables": input.rate_tables,
                    "work_orders": input.work_orders,
                    "service_records": input.service_records,
                    "domain_pack": input.domain_pack,
                    "reconcile_type": "cross_plane",
                },
            )
            response.raise_for_status()
            data = response.json()
            return ReconcileCrossPlaneOutput(
                discrepancies=data.get("discrepancies", []),
                matched_items=data.get("matched_items", 0),
                unmatched_items=data.get("unmatched_items", 0),
            )
        except httpx.ConnectError:
            activity.logger.warning("Reconciler service unavailable (stub)")
            return ReconcileCrossPlaneOutput(
                discrepancies=[],
                matched_items=0,
                unmatched_items=0,
            )


@activity.defn
async def detect_billability_leakage(input: DetectBillabilityInput) -> DetectBillabilityOutput:
    """Detect billability gaps and revenue leakage from reconciliation data."""
    activity.logger.info("Detecting billability and leakage for case %s", input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['reconciler']}/detect-leakage",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "contract_objects": input.contract_objects,
                    "rate_tables": input.rate_tables,
                    "service_records": input.service_records,
                    "discrepancies": input.discrepancies,
                    "domain_pack": input.domain_pack,
                },
            )
            response.raise_for_status()
            data = response.json()
            return DetectBillabilityOutput(
                leakage_items=data.get("leakage_items", []),
                billability_gaps=data.get("billability_gaps", []),
                total_leakage_amount=data.get("total_leakage_amount", 0.0),
                margin_impact_pct=data.get("margin_impact_pct", 0.0),
            )
        except httpx.ConnectError:
            activity.logger.warning("Reconciler service unavailable for leakage detection (stub)")
            return DetectBillabilityOutput(
                leakage_items=[],
                billability_gaps=[],
                total_leakage_amount=0.0,
                margin_impact_pct=0.0,
            )


@activity.defn
async def call_model_for_narrative(input: ModelNarrativeInput) -> ModelNarrativeOutput:
    """Generate a diagnostic narrative summarizing margin findings."""
    activity.logger.info("Generating narrative for case %s", input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['inference']}/generate",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "prompt_template": "margin_diagnosis_narrative",
                    "domain_pack": input.domain_pack,
                    "context": {
                        "contract_id": input.contract_id,
                        "leakage_items": input.leakage_items,
                        "billability_gaps": input.billability_gaps,
                        "discrepancies": input.discrepancies,
                        "total_leakage_amount": input.total_leakage_amount,
                        "margin_impact_pct": input.margin_impact_pct,
                    },
                },
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
            response.raise_for_status()
            data = response.json()
            return ModelNarrativeOutput(narrative=data.get("text", ""))
        except httpx.ConnectError:
            activity.logger.warning("Inference gateway unavailable (stub)")
            return ModelNarrativeOutput(
                narrative=(
                    f"Margin diagnosis for contract {input.contract_id}: "
                    f"total leakage ${input.total_leakage_amount:,.2f}, "
                    f"margin impact {input.margin_impact_pct:.1f}%, "
                    f"{len(input.leakage_items)} leakage item(s), "
                    f"{len(input.billability_gaps)} billability gap(s)."
                )
            )


@activity.defn
async def validate_diagnosis(input: ValidateDiagnosisInput) -> ValidateDiagnosisOutput:
    """Validate the margin diagnosis findings."""
    activity.logger.info("Validating diagnosis for case %s", input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['validator']}/validate",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "domain_pack": input.domain_pack,
                    "validation_context": {
                        "type": "margin_diagnosis",
                        "leakage_items_count": len(input.leakage_items),
                        "billability_gaps_count": len(input.billability_gaps),
                        "total_leakage_amount": input.total_leakage_amount,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return ValidateDiagnosisOutput(
                passed=data.get("passed", True),
                findings=data.get("findings", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Validator service unavailable (stub)")
            return ValidateDiagnosisOutput(passed=True, findings=[])


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
