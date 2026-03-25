"""Tests for health and readiness endpoints."""

import pytest


@pytest.mark.asyncio
async def test_health(async_client):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio
async def test_ready(async_client):
    resp = await async_client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert "ready" in data


@pytest.mark.asyncio
async def test_metrics(async_client):
    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_requests" in data
