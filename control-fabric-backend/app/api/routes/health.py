"""Health, readiness, and metrics endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.telemetry import get_health_status, get_readiness_status, metrics

router = APIRouter(tags=["health"])


@router.get("/health", response_model=dict[str, Any])
async def health() -> dict[str, Any]:
    """Liveness probe -- returns basic health status."""
    return get_health_status()


@router.get("/ready", response_model=dict[str, Any])
async def readiness() -> dict[str, Any]:
    """Readiness probe -- indicates whether the service can accept traffic."""
    return get_readiness_status()


@router.get("/metrics", response_model=dict[str, Any])
async def metrics_snapshot() -> dict[str, Any]:
    """Return a point-in-time snapshot of application metrics counters."""
    return {
        "counters": metrics.snapshot(),
    }
