"""Temporal worker entry point -- polls the control-fabric-workflows task queue."""

from __future__ import annotations

import asyncio
import os
import sys

# Placeholder worker -- requires temporalio to be installed
# In production, this registers workflow and activity implementations
# with the Temporal task queue.


async def main() -> None:
    """Start the Temporal worker."""
    print("Control Fabric Platform -- Temporal Worker")
    print(f"  TEMPORAL_HOST: {os.environ.get('TEMPORAL_HOST', 'localhost:7233')}")
    print(f"  TEMPORAL_NAMESPACE: {os.environ.get('TEMPORAL_NAMESPACE', 'default')}")
    print("")

    try:
        from temporalio.client import Client
        from temporalio.worker import Worker

        client = await Client.connect(
            os.environ.get("TEMPORAL_HOST", "localhost:7233"),
            namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        )

        worker = Worker(
            client,
            task_queue="control-fabric-workflows",
            workflows=[],  # Register workflow classes here
            activities=[],  # Register activity functions here
        )

        print("Worker started. Polling task queue: control-fabric-workflows")
        await worker.run()

    except ImportError:
        print("temporalio not installed. Worker cannot start.")
        print("Install with: pip install temporalio")
        sys.exit(1)
    except Exception as e:
        print(f"Worker error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
