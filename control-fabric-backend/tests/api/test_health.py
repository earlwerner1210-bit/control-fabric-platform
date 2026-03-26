"""API tests for health, readiness, and metrics endpoints."""

from __future__ import annotations

import pytest

from app.core.telemetry import get_health_status, get_readiness_status, metrics


class TestHealthEndpoint:
    def test_health_status(self):
        result = get_health_status()
        assert result["status"] == "healthy"
        assert "version" in result
        assert "environment" in result
        assert "uptime_seconds" in result

    def test_health_includes_app_name(self):
        result = get_health_status()
        assert result["app"] == "control-fabric-backend"


class TestReadinessEndpoint:
    def test_readiness_status(self):
        result = get_readiness_status()
        assert result["status"] == "ready"
        assert "version" in result

    def test_readiness_includes_flags(self):
        result = get_readiness_status()
        assert "metrics_enabled" in result
        assert "otel_enabled" in result


class TestMetrics:
    def test_metrics_increment(self):
        metrics.increment("test_counter", 1)
        snapshot = metrics.snapshot()
        assert "test_counter" in snapshot
        assert snapshot["test_counter"] >= 1

    def test_metrics_snapshot_returns_dict(self):
        snapshot = metrics.snapshot()
        assert isinstance(snapshot, dict)
