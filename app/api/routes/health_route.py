"""
Health and readiness endpoints.
/health — is the service alive?
/ready  — is the service ready to handle traffic?
/metrics — Prometheus-compatible metrics (text format)
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Response

router = APIRouter(tags=["health"])
_start_time = time.time()


@router.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {
        "status": "healthy",
        "service": "control-fabric-platform",
        "version": "1.0.0",
        "uptime_seconds": round(time.time() - _start_time),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/ready")
async def ready() -> dict:
    """Readiness probe."""
    checks: dict[str, str] = {}
    overall = "ready"

    db_url = os.getenv("DATABASE_URL", "")
    checks["database"] = "configured" if db_url else "not_configured"

    redis_url = os.getenv("REDIS_URL", "")
    checks["redis"] = "configured" if redis_url else "not_configured"

    checks["api"] = "ready"
    checks["worker"] = "unknown"

    return {
        "status": overall,
        "checks": checks,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus-compatible metrics endpoint."""
    uptime = round(time.time() - _start_time)
    lines = [
        "# HELP cfp_uptime_seconds Platform uptime in seconds",
        "# TYPE cfp_uptime_seconds gauge",
        f"cfp_uptime_seconds {uptime}",
        "# HELP cfp_api_up API health status (1=up, 0=down)",
        "# TYPE cfp_api_up gauge",
        "cfp_api_up 1",
        "# HELP cfp_info Platform version info",
        "# TYPE cfp_info gauge",
        'cfp_info{version="1.0.0",service="control-fabric-platform"} 1',
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain")
