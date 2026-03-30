"""API tests for health, readiness, and metrics route handlers using TestClient.

Exercises the actual FastAPI routes defined in app/api/routes/health.py through
the application's ASGI stack.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


class TestHealthRoute:
    def test_health_returns_200(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_body_has_status(self, client: TestClient):
        data = client.get("/health").json()
        assert data["status"] == "healthy"

    def test_health_body_has_version(self, client: TestClient):
        data = client.get("/health").json()
        assert "version" in data

    def test_health_body_has_uptime(self, client: TestClient):
        data = client.get("/health").json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))


class TestReadinessRoute:
    def test_readiness_returns_200(self, client: TestClient):
        resp = client.get("/ready")
        assert resp.status_code == 200

    def test_readiness_body_has_status(self, client: TestClient):
        data = client.get("/ready").json()
        assert data["status"] == "ready"

    def test_readiness_body_has_flags(self, client: TestClient):
        data = client.get("/ready").json()
        assert "metrics_enabled" in data
        assert "otel_enabled" in data


class TestMetricsRoute:
    def test_metrics_returns_200(self, client: TestClient):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_body_has_counters(self, client: TestClient):
        data = client.get("/metrics").json()
        assert "counters" in data
        assert isinstance(data["counters"], dict)
