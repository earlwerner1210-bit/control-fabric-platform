"""Observability: metrics, health, and OpenTelemetry hooks."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings


@dataclass
class RequestMetrics:
    """In-process metrics collector."""

    total_requests: int = 0
    total_errors: int = 0
    latencies: list[float] = field(default_factory=list)
    _start_times: dict[str, float] = field(default_factory=dict)

    def start_request(self, request_id: str) -> None:
        self._start_times[request_id] = time.monotonic()
        self.total_requests += 1

    def end_request(self, request_id: str, error: bool = False) -> None:
        start = self._start_times.pop(request_id, None)
        if start is not None:
            self.latencies.append(time.monotonic() - start)
        if error:
            self.total_errors += 1

    def snapshot(self) -> dict[str, Any]:
        avg_latency = sum(self.latencies[-100:]) / max(len(self.latencies[-100:]), 1)
        return {
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "avg_latency_ms": round(avg_latency * 1000, 2),
            "error_rate": round(self.total_errors / max(self.total_requests, 1), 4),
        }


# Singleton
metrics = RequestMetrics()


def get_health_status() -> dict[str, Any]:
    """Return health-check payload."""
    settings = get_settings()
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


def get_readiness_status(db_ok: bool = True, redis_ok: bool = True) -> dict[str, Any]:
    """Return readiness-check payload."""
    ready = db_ok and redis_ok
    return {
        "ready": ready,
        "checks": {
            "database": "ok" if db_ok else "unavailable",
            "redis": "ok" if redis_ok else "unavailable",
        },
    }
