"""Shared test fixtures for the Control Fabric Backend test suite."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── Path constants ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "fixtures"

# ── Deterministic test IDs ────────────────────────────────────────────────────

TEST_TENANT_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
TEST_USER_ID = uuid.UUID("b2c3d4e5-f6a7-8901-bcde-f12345678901")


# ── Event loop ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Fixture data loaders ──────────────────────────────────────────────────────


def _load_fixture(filename: str) -> dict[str, Any]:
    """Load a JSON fixture file from data/fixtures/."""
    path = DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_contract() -> dict[str, Any]:
    """Load the sample SPEN MSA contract fixture."""
    return _load_fixture("sample_contract.json")


@pytest.fixture
def sample_work_order() -> dict[str, Any]:
    """Load the sample HV switching work order fixture."""
    return _load_fixture("sample_work_order.json")


@pytest.fixture
def sample_incident() -> dict[str, Any]:
    """Load the sample P1 power outage incident fixture."""
    return _load_fixture("sample_incident.json")


# ── Mock DB session ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_db_session():
    """Provide a mock AsyncSession for unit tests that don't need a real DB."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
    )
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


# ── Environment overrides ────────────────────────────────────────────────────

# Ensure tests run with fake providers and dev settings
os.environ.setdefault("ENVIRONMENT", "dev")
os.environ.setdefault("INFERENCE_PROVIDER", "fake")
os.environ.setdefault("EMBEDDING_PROVIDER", "fake")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-unit-tests")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/control_fabric_test"
)
