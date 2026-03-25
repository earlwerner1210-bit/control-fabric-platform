"""Temporal Worker — registers all workflows and activities.

Usage:
    python -m workflows.worker

Connects to the Temporal server and starts polling the
'control-fabric-workflows' task queue.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Any

from temporalio.client import Client as TemporalClient
from temporalio.worker import Worker

from shared.config import get_settings

# ── Workflow classes ──────────────────────────────────────────────────────
from workflows.contract_compile.workflow import ContractCompileWorkflow
from workflows.work_order_readiness.workflow import WorkOrderReadinessWorkflow
from workflows.incident_dispatch_reconcile.workflow import IncidentDispatchWorkflow
from workflows.margin_diagnosis.workflow import MarginDiagnosisWorkflow

# ── Activity functions ────────────────────────────────────────────────────
from workflows.contract_compile.activities import (
    parse_documents as cc_parse_documents,
    chunk_and_embed as cc_chunk_and_embed,
    canonicalize_entities as cc_canonicalize_entities,
    extract_clauses as cc_extract_clauses,
    compile_control_objects as cc_compile_control_objects,
    create_links as cc_create_links,
    validate_output as cc_validate_output,
    log_audit as cc_log_audit,
)
from workflows.work_order_readiness.activities import (
    parse_work_order as wor_parse_work_order,
    parse_engineer_accreditation as wor_parse_engineer,
    compile_readiness_objects as wor_compile_readiness,
    reconcile_against_rules as wor_reconcile_rules,
    retrieve_evidence as wor_retrieve_evidence,
    call_model_for_explanation as wor_model_explanation,
    validate_readiness as wor_validate_readiness,
    log_audit as wor_log_audit,
)
from workflows.incident_dispatch_reconcile.activities import (
    parse_incident as idr_parse_incident,
    compile_incident_objects as idr_compile_incident,
    retrieve_linked_data as idr_retrieve_linked,
    reconcile_states as idr_reconcile_states,
    call_model_for_summary as idr_model_summary,
    validate_reconciliation as idr_validate_reconciliation,
    log_audit as idr_log_audit,
)
from workflows.margin_diagnosis.activities import (
    load_contract_objects as md_load_contract,
    load_field_service_objects as md_load_field,
    reconcile_cross_plane as md_reconcile_cross_plane,
    detect_billability_leakage as md_detect_billability,
    call_model_for_narrative as md_model_narrative,
    validate_diagnosis as md_validate_diagnosis,
    log_audit as md_log_audit,
)

logger = logging.getLogger("workflows.worker")

TASK_QUEUE = "control-fabric-workflows"

ALL_WORKFLOWS = [
    ContractCompileWorkflow,
    WorkOrderReadinessWorkflow,
    IncidentDispatchWorkflow,
    MarginDiagnosisWorkflow,
]

ALL_ACTIVITIES = [
    # Contract Compile
    cc_parse_documents,
    cc_chunk_and_embed,
    cc_canonicalize_entities,
    cc_extract_clauses,
    cc_compile_control_objects,
    cc_create_links,
    cc_validate_output,
    cc_log_audit,
    # Work Order Readiness
    wor_parse_work_order,
    wor_parse_engineer,
    wor_compile_readiness,
    wor_reconcile_rules,
    wor_retrieve_evidence,
    wor_model_explanation,
    wor_validate_readiness,
    wor_log_audit,
    # Incident Dispatch Reconcile
    idr_parse_incident,
    idr_compile_incident,
    idr_retrieve_linked,
    idr_reconcile_states,
    idr_model_summary,
    idr_validate_reconciliation,
    idr_log_audit,
    # Margin Diagnosis
    md_load_contract,
    md_load_field,
    md_reconcile_cross_plane,
    md_detect_billability,
    md_model_narrative,
    md_validate_diagnosis,
    md_log_audit,
]


async def run_worker() -> None:
    """Connect to Temporal and run the worker until interrupted."""
    settings = get_settings()

    logger.info(
        "Connecting to Temporal at %s (namespace: %s)",
        settings.TEMPORAL_HOST,
        settings.TEMPORAL_NAMESPACE,
    )

    client = await TemporalClient.connect(
        settings.TEMPORAL_HOST,
        namespace=settings.TEMPORAL_NAMESPACE,
    )

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=ALL_WORKFLOWS,
        activities=ALL_ACTIVITIES,
    )

    logger.info(
        "Starting worker on task queue '%s' with %d workflows and %d activities",
        TASK_QUEUE,
        len(ALL_WORKFLOWS),
        len(ALL_ACTIVITIES),
    )

    # Graceful shutdown on SIGINT / SIGTERM
    shutdown_event = asyncio.Event()

    def _signal_handler(sig: int, frame: Any) -> None:
        logger.info("Received signal %s, shutting down worker...", signal.Signals(sig).name)
        shutdown_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Run until shutdown signal
    async with worker:
        await shutdown_event.wait()

    logger.info("Worker shut down cleanly.")


def main() -> None:
    """Entry point for ``python -m workflows.worker``."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
