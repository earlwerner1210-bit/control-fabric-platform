"""Temporal worker that registers all Control Fabric workflows and activities.

Run with::

    python -m temporal_worker.worker
"""

from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.workflows.contract_compile.workflow import (
    ContractCompileWorkflow,
    compile_objects_activity,
    load_documents_activity,
    parse_documents_activity,
    validate_output_activity,
)
from app.workflows.contract_compile.workflow import (
    log_audit_activity as cc_log_audit_activity,
)
from app.workflows.margin_diagnosis.workflow import (
    MarginDiagnosisWorkflow,
    load_contract_objects_activity,
    parse_incident_activity,
    parse_work_order_activity,
    persist_results_activity,
    reconcile_activity,
    run_inference_activity,
    validate_diagnosis_activity,
)
from app.workflows.margin_diagnosis.workflow import (
    log_audit_activity as md_log_audit_activity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

WORKFLOWS = [
    ContractCompileWorkflow,
    MarginDiagnosisWorkflow,
]

ACTIVITIES = [
    # Contract-compile activities
    load_documents_activity,
    parse_documents_activity,
    compile_objects_activity,
    validate_output_activity,
    cc_log_audit_activity,
    # Margin-diagnosis activities
    load_contract_objects_activity,
    parse_work_order_activity,
    parse_incident_activity,
    reconcile_activity,
    run_inference_activity,
    validate_diagnosis_activity,
    persist_results_activity,
    md_log_audit_activity,
]


# ---------------------------------------------------------------------------
# Worker bootstrap
# ---------------------------------------------------------------------------


async def run_worker() -> None:
    """Connect to Temporal and start the worker loop."""
    settings = get_settings()

    logger.info(
        "Connecting to Temporal at %s (namespace=%s, queue=%s)",
        settings.TEMPORAL_HOST,
        settings.TEMPORAL_NAMESPACE,
        settings.TEMPORAL_TASK_QUEUE,
    )

    client = await Client.connect(
        settings.TEMPORAL_HOST,
        namespace=settings.TEMPORAL_NAMESPACE,
    )

    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
    )

    logger.info("Temporal worker started on queue '%s'", settings.TEMPORAL_TASK_QUEUE)
    await worker.run()


def main() -> None:
    """Entry point for ``python -m temporal_worker.worker``."""
    setup_logging()
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
