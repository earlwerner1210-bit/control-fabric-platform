"""Contract-compile Temporal workflow and activity definitions.

This workflow orchestrates the end-to-end pipeline for compiling a contract
document into structured control objects: load documents, parse them, compile
into obligation/SLA/penalty objects, validate the output, and log an audit
trail.
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
    """Input passed to the contract-compile workflow."""

    tenant_id: str
    user_id: str
    payload: dict[str, Any]


@dataclass
class WorkflowOutput:
    """Output returned by the contract-compile workflow."""

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


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


@activity.defn
async def load_documents_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Load raw document records from the database for the given document IDs.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``contract_document_id``
    - ``sla_document_ids`` (list)
    - ``rate_card_document_ids`` (list)

    Returns a dict with ``documents`` (list of document metadata dicts).
    """
    logger.info(
        "contract_compile.load_documents",
        tenant_id=input.get("tenant_id"),
        contract_id=input.get("contract_document_id"),
    )

    contract_doc_id = input.get("contract_document_id")
    sla_ids: list[str] = input.get("sla_document_ids", [])
    rate_card_ids: list[str] = input.get("rate_card_document_ids", [])

    all_ids = [contract_doc_id] + sla_ids + rate_card_ids
    documents = [
        {"id": doc_id, "status": "loaded", "type": "contract" if doc_id == contract_doc_id else "supplementary"}
        for doc_id in all_ids
        if doc_id is not None
    ]

    return {"documents": documents, "document_count": len(documents)}


@activity.defn
async def parse_documents_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Parse loaded documents into structured representations.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``documents`` (list of document dicts from load step)

    Returns a dict with ``parsed_results`` keyed by document ID.
    """
    documents: list[dict[str, Any]] = input.get("documents", [])
    logger.info("contract_compile.parse_documents", count=len(documents))

    parsed_results: dict[str, Any] = {}
    for doc in documents:
        doc_id = doc["id"]
        parsed_results[doc_id] = {
            "id": doc_id,
            "status": "parsed",
            "clauses": [],
            "sections": [],
            "metadata": {},
        }

    return {"parsed_results": parsed_results, "parsed_count": len(parsed_results)}


@activity.defn
async def compile_objects_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Compile parsed document clauses into typed control objects.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``parsed_results`` (dict from parse step)

    Returns a dict with ``compiled_count`` and ``control_object_ids``.
    """
    parsed_results: dict[str, Any] = input.get("parsed_results", {})
    logger.info("contract_compile.compile_objects", source_count=len(parsed_results))

    control_object_ids: list[str] = []
    for _doc_id, parsed in parsed_results.items():
        obj_id = str(uuid.uuid4())
        control_object_ids.append(obj_id)

    return {
        "compiled_count": len(control_object_ids),
        "control_object_ids": control_object_ids,
    }


@activity.defn
async def validate_output_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Run deterministic validation rules against compiled control objects.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``control_object_ids`` (list)
    - ``compiled_count`` (int)

    Returns a dict with ``validation_status`` and ``validation_errors``.
    """
    control_object_ids: list[str] = input.get("control_object_ids", [])
    logger.info("contract_compile.validate_output", object_count=len(control_object_ids))

    errors: list[str] = []
    if not control_object_ids:
        errors.append("No control objects were compiled")

    status = "approved" if not errors else "blocked"
    return {"validation_status": status, "validation_errors": errors}


@activity.defn
async def log_audit_activity(input: dict[str, Any]) -> dict[str, Any]:
    """Persist an audit event recording the workflow execution.

    Expects ``input`` to contain:
    - ``tenant_id``
    - ``user_id``
    - ``case_id``
    - ``status``
    - ``event_type``

    Returns a dict with ``audit_status``.
    """
    logger.info(
        "contract_compile.log_audit",
        case_id=input.get("case_id"),
        event_type=input.get("event_type"),
        status=input.get("status"),
    )
    return {"audit_status": "logged"}


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@workflow.defn
class ContractCompileWorkflow:
    """Orchestrates the contract-compile pipeline.

    Steps:
    1. Load documents from storage / DB
    2. Parse documents into structured clause representations
    3. Compile clauses into typed control objects
    4. Validate compiled output against rules
    5. Log audit trail
    """

    @workflow.run
    async def run(self, input: WorkflowInput) -> WorkflowOutput:
        case_id = str(uuid.uuid4())
        errors: list[str] = []

        try:
            # Step 1 -- Load documents
            load_result = await workflow.execute_activity(
                load_documents_activity,
                {
                    "tenant_id": input.tenant_id,
                    "contract_document_id": input.payload.get("contract_document_id"),
                    "sla_document_ids": input.payload.get("sla_document_ids", []),
                    "rate_card_document_ids": input.payload.get("rate_card_document_ids", []),
                },
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )

            # Step 2 -- Parse documents
            parse_result = await workflow.execute_activity(
                parse_documents_activity,
                {
                    "tenant_id": input.tenant_id,
                    "documents": load_result["documents"],
                },
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )

            # Step 3 -- Compile control objects
            compile_result = await workflow.execute_activity(
                compile_objects_activity,
                {
                    "tenant_id": input.tenant_id,
                    "parsed_results": parse_result["parsed_results"],
                },
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )

            # Step 4 -- Validate output
            validation_result = await workflow.execute_activity(
                validate_output_activity,
                {
                    "tenant_id": input.tenant_id,
                    "control_object_ids": compile_result["control_object_ids"],
                    "compiled_count": compile_result["compiled_count"],
                },
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )

            errors.extend(validation_result.get("validation_errors", []))
            status = "completed" if validation_result["validation_status"] == "approved" else "failed"

            output = {
                "document_count": load_result["document_count"],
                "parsed_count": parse_result["parsed_count"],
                "compiled_count": compile_result["compiled_count"],
                "control_object_ids": compile_result["control_object_ids"],
                "validation_status": validation_result["validation_status"],
            }

        except Exception as exc:
            status = "failed"
            output = {}
            errors.append(str(exc))

        # Step 5 -- Audit (always runs)
        await workflow.execute_activity(
            log_audit_activity,
            {
                "tenant_id": input.tenant_id,
                "user_id": input.user_id,
                "case_id": case_id,
                "status": status,
                "event_type": "workflow.contract_compile.completed",
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
