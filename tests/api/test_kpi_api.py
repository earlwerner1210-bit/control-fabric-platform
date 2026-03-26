"""API tests for KPI endpoints."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes.kpis import router

app = FastAPI()
app.include_router(router)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


CASE_ID = str(uuid.uuid4())


@pytest.mark.asyncio
async def test_record_and_get_kpi(client):
    resp = await client.post(
        f"/api/v1/pilot-cases/{CASE_ID}/kpis",
        json={
            "metric_name": "time_to_decision",
            "metric_value": 2.5,
            "metric_unit": "hours",
            "dimension": "workflow_type",
            "dimension_value": "margin_diagnosis",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metric_name"] == "time_to_decision"
    assert data["metric_value"] == 2.5

    resp = await client.get(f"/api/v1/pilot-cases/{CASE_ID}/kpis")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_empty_kpis(client):
    resp = await client.get(f"/api/v1/pilot-cases/{uuid.uuid4()}/kpis")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_kpi_summary(client):
    resp = await client.get("/api/v1/pilot-cases/kpis/summary")
    assert resp.status_code == 200
    assert "total_cases" in resp.json()


@pytest.mark.asyncio
async def test_workflow_kpis(client):
    resp = await client.get("/api/v1/pilot-cases/kpis/workflows")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_reviewer_kpis(client):
    resp = await client.get("/api/v1/pilot-cases/kpis/reviewers")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
