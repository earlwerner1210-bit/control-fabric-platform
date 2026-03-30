"""API tests for baseline comparison endpoints."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes.baseline import router

app = FastAPI()
app.include_router(router)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


CASE_ID = str(uuid.uuid4())


@pytest.mark.asyncio
async def test_create_and_get_baseline(client):
    # Create
    resp = await client.post(
        f"/api/v1/pilot-cases/{CASE_ID}/baseline",
        json={
            "expected_outcome": "billable",
            "expected_confidence": 0.95,
            "expected_reasoning": "Standard rate card",
            "source": "human_expert",
            "expected_status": "approved",
            "expected_billability": "full",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["expected_outcome"] == "billable"
    assert data["expected_confidence"] == 0.95
    assert data["expected_status"] == "approved"

    # Get
    resp = await client.get(f"/api/v1/pilot-cases/{CASE_ID}/baseline")
    assert resp.status_code == 200
    assert resp.json()["expected_outcome"] == "billable"


@pytest.mark.asyncio
async def test_get_missing_baseline(client):
    resp = await client.get(f"/api/v1/pilot-cases/{uuid.uuid4()}/baseline")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compare_exact_match(client):
    case_id = str(uuid.uuid4())
    await client.post(
        f"/api/v1/pilot-cases/{case_id}/baseline",
        json={"expected_outcome": "billable"},
    )

    resp = await client.post(
        f"/api/v1/pilot-cases/{case_id}/baseline/compare",
        json={"platform_outcome": "billable"},
    )
    assert resp.status_code == 200
    assert resp.json()["match_type"] == "exact_match"


@pytest.mark.asyncio
async def test_compare_false_positive(client):
    case_id = str(uuid.uuid4())
    await client.post(
        f"/api/v1/pilot-cases/{case_id}/baseline",
        json={"expected_outcome": "rejected"},
    )

    resp = await client.post(
        f"/api/v1/pilot-cases/{case_id}/baseline/compare",
        json={"platform_outcome": "approved"},
    )
    assert resp.status_code == 200
    assert resp.json()["match_type"] == "false_positive"


@pytest.mark.asyncio
async def test_compare_missing_expectation(client):
    resp = await client.post(
        f"/api/v1/pilot-cases/{uuid.uuid4()}/baseline/compare",
        json={"platform_outcome": "billable"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_baseline_summary(client):
    resp = await client.get("/api/v1/pilot-reports/baseline-comparison")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_compared" in data
    assert "accuracy_rate" in data
