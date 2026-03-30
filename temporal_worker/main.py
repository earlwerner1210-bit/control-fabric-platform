"""Temporal worker bootstrap – registers all workflows and activities."""

from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
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

logger = get_logger("temporal_worker")

WORKFLOWS = [
    ContractCompileWorkflow,
    WorkOrderReadinessWorkflow,
    IncidentDispatchWorkflow,
    MarginDiagnosisWorkflow,
]

ACTIVITIES = [
    parse_documents_activity,
    chunk_and_embed_activity,
    compile_objects_activity,
    validate_output_activity,
    log_audit_activity,
    run_inference_activity,
]


async def run_worker() -> None:
    settings = get_settings()
    setup_logging()
    logger.info("connecting_to_temporal", host=settings.TEMPORAL_HOST)

    client = await Client.connect(settings.TEMPORAL_HOST, namespace=settings.TEMPORAL_NAMESPACE)

    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
    )

    logger.info("worker_started", task_queue=settings.TEMPORAL_TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
