"""Shared test fixtures for the Control Fabric Platform test suite."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Project root & data paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# Deterministic IDs for tests
# ---------------------------------------------------------------------------

TEST_TENANT_ID = "00000000-0000-0000-0000-000000000099"
TEST_USER_ID = "00000000-0000-0000-0000-000000000098"
TEST_USER_EMAIL = "test@controlfabric.io"

# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_contract() -> dict[str, Any]:
    """Load the sample MSA contract."""
    path = DATA_DIR / "sample-contracts" / "master_services_agreement.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def sample_work_order() -> dict[str, Any]:
    """Load the sample work order."""
    path = DATA_DIR / "sample-work-orders" / "work_order_001.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def sample_incident() -> dict[str, Any]:
    """Load the sample incident."""
    path = DATA_DIR / "sample-incidents" / "incident_001.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def sample_runbook() -> dict[str, Any]:
    """Load the sample runbook."""
    path = DATA_DIR / "sample-runbooks" / "network_degradation_runbook.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def sample_tenant() -> dict[str, Any]:
    """Return a sample tenant dict."""
    return {
        "id": TEST_TENANT_ID,
        "name": "Test Tenant",
        "slug": "test",
        "is_active": True,
    }


@pytest.fixture
def sample_user() -> dict[str, Any]:
    """Return a sample user dict."""
    return {
        "id": TEST_USER_ID,
        "email": TEST_USER_EMAIL,
        "full_name": "Test User",
        "role": "admin",
        "tenant_id": TEST_TENANT_ID,
        "is_active": True,
    }


@pytest.fixture
def auth_token() -> str:
    """Create a valid JWT token for test requests."""
    from shared.security.auth import create_access_token

    return create_access_token(
        tenant_id=uuid.UUID(TEST_TENANT_ID),
        user_id=uuid.UUID(TEST_USER_ID),
        roles=["admin"],
        extra_claims={"email": TEST_USER_EMAIL},
    )


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """Return Authorization headers for test requests."""
    return {"Authorization": f"Bearer {auth_token}"}


# ---------------------------------------------------------------------------
# Database fixtures (using in-memory sqlite for unit tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Return a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.close = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Test app & async client (for API tests)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client(auth_headers: dict[str, str]) -> AsyncGenerator[AsyncClient, None]:
    """Create an httpx AsyncClient pointing at the test app.

    This fixture patches:
    - Database dependency to use an in-memory mock
    - Auth dependency to return the test user
    - Lifespan to skip DB connectivity check
    """
    from contextlib import asynccontextmanager
    from collections.abc import AsyncGenerator as AG

    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from apps.api.routes import auth, cases, compile, documents, evals, admin

    # Build a minimal test app without lifespan DB check
    @asynccontextmanager
    async def test_lifespan(app: FastAPI) -> AG[None, None]:
        yield

    test_app = FastAPI(lifespan=test_lifespan)
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    API_PREFIX = "/api/v1"
    test_app.include_router(auth.router, prefix=API_PREFIX)
    test_app.include_router(documents.router, prefix=API_PREFIX)
    test_app.include_router(compile.router, prefix=API_PREFIX)
    test_app.include_router(cases.router, prefix=API_PREFIX)
    test_app.include_router(evals.router, prefix=API_PREFIX)
    test_app.include_router(admin.router, prefix=API_PREFIX)

    @test_app.get("/health")
    async def health():
        return {"status": "ok"}

    # Override dependencies
    from apps.api.dependencies import get_db, get_current_user, get_tenant_context

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(
        mappings=MagicMock(return_value=MagicMock(
            first=MagicMock(return_value=None),
            all=MagicMock(return_value=[]),
        )),
        scalar=MagicMock(return_value=0),
        first=MagicMock(return_value=None),
    ))
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    async def override_get_db():
        yield mock_db

    async def override_get_current_user():
        return {
            "sub": TEST_USER_ID,
            "email": TEST_USER_EMAIL,
            "role": "admin",
            "tenant_id": TEST_TENANT_ID,
        }

    async def override_get_tenant_context():
        return TEST_TENANT_ID

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_current_user] = override_get_current_user
    test_app.dependency_overrides[get_tenant_context] = override_get_tenant_context

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
