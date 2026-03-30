"""Lightweight metrics collection and health/readiness probes."""

from __future__ import annotations

import time
from threading import Lock
from typing import Any

from app.core.config import get_settings


class MetricsCollector:
    """Thread-safe in-process counter store.

    This is intentionally simple: a dict of named counters that can be
    incremented and snapshotted.  In production the counters can be exported to
    an OpenTelemetry collector; this class provides the local bookkeeping.
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._lock = Lock()

    def increment(self, name: str, value: int = 1) -> None:
        """Increment counter *name* by *value* (default 1)."""
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def snapshot(self) -> dict[str, int]:
        """Return an immutable copy of all current counter values."""
        with self._lock:
            return dict(self._counters)


# Global singleton
metrics = MetricsCollector()

_start_time = time.monotonic()


def get_health_status() -> dict[str, Any]:
    """Return a liveness health-check payload."""
    settings = get_settings()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.monotonic() - _start_time, 2),
    }


def get_readiness_status() -> dict[str, Any]:
    """Return a readiness-check payload.

    This is a lightweight probe; deeper dependency checks (DB, Redis) should
    be added as the platform matures.
    """
    settings = get_settings()
    return {
        "status": "ready",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "metrics_enabled": settings.METRICS_ENABLED,
        "otel_enabled": settings.OTEL_ENABLED,
    }
