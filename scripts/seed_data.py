"""
Seed sample data into the Control Fabric Platform database.
Run: poetry run python scripts/seed_data.py
"""
import asyncio
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


async def seed():
    print("=== Seeding Control Fabric Platform ===")
    print(f"Data directory: {DATA_DIR}")

    # TODO: Implement seeding logic once services are scaffolded
    # Example:
    # await seed_contracts(DATA_DIR / "sample-contracts")
    # await seed_work_orders(DATA_DIR / "sample-work-orders")
    # await seed_incidents(DATA_DIR / "sample-incidents")

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
