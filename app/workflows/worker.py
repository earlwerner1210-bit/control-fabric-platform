"""Temporal worker entry point.

Starts a Temporal worker that polls the configured task queue and
executes workflow and activity definitions.

Usage:
    python -m app.workflows.worker
"""

from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from app.core.config import get_settings
from app.workflows.temporal_workflows import (
    ContractCompileWorkflow,
    IncidentDispatchWorkflow,
    MarginDiagnosisWorkflow,
    WorkOrderReadinessWorkflow,
    chunk_and_embed_activity,
    compile_objects_activity,
    log_audit_activity,
    parse_documents_activity,
    run_inference_activity,
    validate_output_activity,
)

logger = logging.getLogger("worker")

# All workflow classes the worker should register
WORKFLOWS = [
    ContractCompileWorkflow,
    WorkOrderReadinessWorkflow,
    IncidentDispatchWorkflow,
    MarginDiagnosisWorkflow,
]

# All activity functions the worker should register
ACTIVITIES = [
    parse_documents_activity,
    chunk_and_embed_activity,
    compile_objects_activity,
    validate_output_activity,
    log_audit_activity,
    run_inference_activity,
]


async def run_worker() -> None:
    """Connect to Temporal and start the worker."""
    settings = get_settings()

    logger.info(
        "Connecting to Temporal at %s namespace=%s queue=%s",
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

    logger.info("Worker started on queue %s", settings.TEMPORAL_TASK_QUEUE)
    await worker.run()


def main() -> None:
    """Entry point for ``python -m app.workflows.worker``."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
