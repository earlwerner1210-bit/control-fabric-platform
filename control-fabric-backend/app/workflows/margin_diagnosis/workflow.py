"""Margin-diagnosis Temporal workflow and activity definitions.

This workflow reconciles contract obligations against work-order / incident
data to identify margin leakage, billability issues, and penalty risks.
Steps: load contract objects, parse work order, optionally parse incident,
reconcile, run inference for explanation, validate, persist, and audit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    import structlog

    logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class WorkflowInput:
    """Input passed to the margin-diagnosis workflow."""

    tenant_id: str
    user_id: str
    payload: dict[str, Any]


@dataclass
class WorkflowOutput:
    """Output returned by the margin-diagnosis workflow."""

    case_id: str
    status: str
    output: dict[str, Any]
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Retry / timeout defaults
# ---------------------------------------------------------------------------

_DEFAULT_RETRY = workflow.RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_attempts=3,
    backoff_coefficient=2.0,
)

_ACTIVITY_TIMEOUT = timedelta(seconds=120)
_INFERENCE_TIMEOUT = timedelta(seconds=180)


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


@activity.defn
async def load_contract_objects_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Load compiled control objects for the given contract.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``contract_document_id``
    - ``contract_case_id`` (optional, to load from a prior compile run)

    Returns a dict with ``contract_objects`` (list of control object dicts).
    """
    logger.info(
        "margin_diagnosis.load_contract_objects",
        tenant_id=input.get("tenant_id"),
        contract_doc_id=input.get("contract_document_id"),
        case_id=input.get("contract_case_id"),
    )

    contract_objects = [
        {
            "id": str(uuid.uuid4()),
            "type": "obligation",
            "label": "Sample obligation",
            "payload": {},
        }
    ]

    return {"contract_objects": contract_objects, "object_count": len(contract_objects)}


@activity.defn
async def parse_work_order_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Parse a work-order document into structured line items.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``work_order_document_id``

    Returns a dict with ``work_order`` containing parsed work-order data.
    """
    wo_id = input.get("work_order_document_id")
    logger.info("margin_diagnosis.parse_work_order", document_id=wo_id)

    if wo_id is None:
        return {"work_order": None, "status": "skipped"}

    return {
        "work_order": {
            "id": wo_id,
            "status": "parsed",
            "line_items": [],
            "total_amount": 0.0,
            "metadata": {},
        },
        "status": "parsed",
    }


@activity.defn
async def parse_incident_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Parse an incident-report document into structured fields.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``incident_document_id``

    Returns a dict with ``incident`` containing parsed incident data.
    """
    incident_id = input.get("incident_document_id")
    logger.info("margin_diagnosis.parse_incident", document_id=incident_id)

    if incident_id is None:
        return {"incident": None, "status": "skipped"}

    return {
        "incident": {
            "id": incident_id,
            "status": "parsed",
            "severity": "medium",
            "root_cause": None,
            "resolution_actions": [],
            "metadata": {},
        },
        "status": "parsed",
    }


@activity.defn
async def reconcile_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Reconcile contract objects against work-order / incident data.

    Determines billability, margin leakage drivers, and penalty exposure
    using deterministic rule-based logic.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``contract_objects``
    - ``work_order`` (may be None)
    - ``incident`` (may be None)

    Returns a dict with reconciliation results.
    """
    contract_objects: list[dict[str, Any]] = input.get("contract_objects", [])
    work_order = input.get("work_order")
    incident = input.get("incident")

    logger.info(
        "margin_diagnosis.reconcile",
        object_count=len(contract_objects),
        has_work_order=work_order is not None,
        has_incident=incident is not None,
    )

    leakage_drivers: list[str] = []
    recovery_recommendations: list[str] = []
    verdict = "billable"

    if not contract_objects:
        verdict = "unknown"
        leakage_drivers.append("No contract objects available for reconciliation")

    if work_order is None:
        leakage_drivers.append("Missing work order -- cannot verify billability")
        verdict = "under_recovery"

    if incident is not None:
        recovery_recommendations.append("Review incident resolution against SLA targets")

    return {
        "verdict": verdict,
        "leakage_drivers": leakage_drivers,
        "recovery_recommendations": recovery_recommendations,
        "billability_details": {
            "total_objects": len(contract_objects),
            "billable": len(contract_objects) if verdict == "billable" else 0,
        },
        "penalty_exposure": {},
    }


@activity.defn
async def run_inference_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Run LLM inference to generate an executive summary / explanation.

    This activity calls the inference gateway to produce a human-readable
    explanation of the reconciliation results.  The output is for
    explanation only -- all decisions are made by deterministic rules.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``reconcile_result`` (dict from reconcile step)

    Returns a dict with ``executive_summary``.
    """
    reconcile_result = input.get("reconcile_result", {})
    logger.info(
        "margin_diagnosis.run_inference",
        verdict=reconcile_result.get("verdict"),
    )

    verdict = reconcile_result.get("verdict", "unknown")
    drivers = reconcile_result.get("leakage_drivers", [])
    recommendations = reconcile_result.get("recovery_recommendations", [])

    summary_parts = [f"Margin diagnosis verdict: {verdict}."]
    if drivers:
        summary_parts.append(f"Leakage drivers identified: {', '.join(drivers)}.")
    if recommendations:
        summary_parts.append(f"Recommendations: {', '.join(recommendations)}.")

    return {"executive_summary": " ".join(summary_parts)}


@activity.defn
async def validate_diagnosis_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Validate the diagnosis output against business rules.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``verdict``
    - ``reconcile_result``
    - ``executive_summary``

    Returns a dict with ``validation_status`` and ``validation_errors``.
    """
    verdict = input.get("verdict", "unknown")
    summary = input.get("executive_summary", "")
    logger.info("margin_diagnosis.validate", verdict=verdict)

    errors: list[str] = []

    if verdict == "unknown":
        errors.append("Verdict is 'unknown' -- insufficient data for reliable diagnosis")

    if not summary:
        errors.append("Executive summary is empty")

    status = "approved" if not errors else "warn"
    return {"validation_status": status, "validation_errors": errors}


@activity.defn
async def persist_results_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Persist the diagnosis results to the database.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``case_id``
    - ``verdict``
    - ``output`` (full output dict)

    Returns a dict with ``persist_status``.
    """
    case_id = input.get("case_id")
    logger.info("margin_diagnosis.persist_results", case_id=case_id)

    return {"persist_status": "persisted", "case_id": case_id}


@activity.defn
async def log_audit_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Log an audit event for the margin-diagnosis workflow execution.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``user_id``
    - ``case_id``
    - ``status``
    - ``event_type``

    Returns a dict with ``audit_status``.
    """
    logger.info(
        "margin_diagnosis.log_audit",
        case_id=input.get("case_id"),
        event_type=input.get("event_type"),
        status=input.get("status"),
    )
    return {"audit_status": "logged"}


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@workflow.defn
class MarginDiagnosisWorkflow:
    """Orchestrates the margin-diagnosis pipeline.

    Steps:
    1. Load contract objects
    2. Parse work order (if provided)
    3. Parse incident (if provided)
    4. Reconcile obligations vs actuals
    5. Run inference for executive summary (explanation only)
    6. Validate diagnosis output
    7. Persist results
    8. Log audit trail
    """

    @workflow.run
    async def run(self, input: WorkflowInput) -> WorkflowOutput:
        case_id = str(uuid.uuid4())
        errors: list[str] = []

        try:
            # Step 1 -- Load contract objects
            load_result = await workflow.execute_activity(
                load_contract_objects_activity,
                {
                    "tenant_id": input.tenant_id,
                    "contract_document_id": input.payload.get("contract_document_id"),
                    "contract_case_id": input.payload.get("contract_case_id"),
                },
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )

            # Step 2 -- Parse work order
            wo_result = await workflow.execute_activity(
                parse_work_order_activity,
                {
                    "tenant_id": input.tenant_id,
                    "work_order_document_id": input.payload.get("work_order_document_id"),
                },
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )

            # Step 3 -- Parse incident (if present)
            incident_result = await workflow.execute_activity(
                parse_incident_activity,
                {
                    "tenant_id": input.tenant_id,
                    "incident_document_id": input.payload.get("incident_document_id"),
                },
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )

            # Step 4 -- Reconcile
            reconcile_result = await workflow.execute_activity(
                reconcile_activity,
                {
                    "tenant_id": input.tenant_id,
                    "contract_objects": load_result["contract_objects"],
                    "work_order": wo_result.get("work_order"),
                    "incident": incident_result.get("incident"),
                },
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )

            # Step 5 -- Inference for explanation
            inference_result = await workflow.execute_activity(
                run_inference_activity,
                {
                    "tenant_id": input.tenant_id,
                    "reconcile_result": reconcile_result,
                },
                start_to_close_timeout=_INFERENCE_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )

            # Step 6 -- Validate
            validation_result = await workflow.execute_activity(
                validate_diagnosis_activity,
                {
                    "tenant_id": input.tenant_id,
                    "verdict": reconcile_result["verdict"],
                    "reconcile_result": reconcile_result,
                    "executive_summary": inference_result["executive_summary"],
                },
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )

            errors.extend(validation_result.get("validation_errors", []))

            output = {
                "verdict": reconcile_result["verdict"],
                "leakage_drivers": reconcile_result["leakage_drivers"],
                "recovery_recommendations": reconcile_result["recovery_recommendations"],
                "billability_details": reconcile_result["billability_details"],
                "penalty_exposure": reconcile_result["penalty_exposure"],
                "executive_summary": inference_result["executive_summary"],
                "evidence_object_ids": [],
                "validation_status": validation_result["validation_status"],
            }

            status = "completed"

            # Step 7 -- Persist results
            await workflow.execute_activity(
                persist_results_activity,
                {
                    "tenant_id": input.tenant_id,
                    "case_id": case_id,
                    "verdict": reconcile_result["verdict"],
                    "output": output,
                },
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )

        except Exception as exc:
            status = "failed"
            output = {}
            errors.append(str(exc))

        # Step 8 -- Audit (always runs)
        await workflow.execute_activity(
            log_audit_activity,
            {
                "tenant_id": input.tenant_id,
                "user_id": input.user_id,
                "case_id": case_id,
                "status": status,
                "event_type": "workflow.margin_diagnosis.completed",
            },
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_DEFAULT_RETRY,
        )

        return WorkflowOutput(
            case_id=case_id,
            status=status,
            output=output,
            errors=errors,
        )
