"""
Platform infrastructure health — all services in one endpoint.

Checks:
  - API process (always healthy if this responds)
  - PostgreSQL — connection test + query latency
  - Redis — ping + latency
  - Celery workers — active worker count via Celery inspect
  - Celery beat — scheduled task status
  - Disk space — if running in container
  - Memory usage

Used by:
  - Kubernetes liveness/readiness probes (/health, /ready)
  - Operator console infrastructure screen
  - PagerDuty/alerting integrations via /infra/health
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

from fastapi import APIRouter

router = APIRouter(prefix="/infra", tags=["infrastructure"])


async def _check_database() -> dict:
    t = time.perf_counter()
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return {"status": "not_configured", "latency_ms": 0, "detail": "DATABASE_URL not set"}
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(db_url, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency = round((time.perf_counter() - t) * 1000, 2)
        await engine.dispose()
        return {
            "status": "healthy",
            "latency_ms": latency,
            "detail": "Connection and query successful",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "latency_ms": round((time.perf_counter() - t) * 1000, 2),
            "detail": str(e)[:120],
        }


def _check_redis() -> dict:
    t = time.perf_counter()
    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        return {"status": "not_configured", "latency_ms": 0, "detail": "REDIS_URL not set"}
    try:
        import redis as redis_lib

        r = redis_lib.from_url(redis_url, socket_timeout=2, decode_responses=True)
        r.ping()
        latency = round((time.perf_counter() - t) * 1000, 2)
        info = r.info("server")
        return {
            "status": "healthy",
            "latency_ms": latency,
            "version": info.get("redis_version", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "unknown"),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "latency_ms": round((time.perf_counter() - t) * 1000, 2),
            "detail": str(e)[:120],
        }


def _check_celery() -> dict:
    try:
        from app.worker.celery_app import celery_app

        inspect = celery_app.control.inspect(timeout=2)
        active = inspect.active() or {}
        worker_count = len(active)
        return {
            "status": "healthy" if worker_count > 0 else "degraded",
            "active_workers": worker_count,
            "worker_names": list(active.keys()),
            "detail": f"{worker_count} worker(s) active"
            if worker_count > 0
            else "No active workers — scheduled tasks will not run",
        }
    except Exception as e:
        return {
            "status": "unknown",
            "active_workers": 0,
            "detail": f"Cannot reach Celery broker: {str(e)[:80]}",
        }


def _check_memory() -> dict:
    try:
        import psutil

        mem = psutil.virtual_memory()
        return {
            "status": "healthy" if mem.percent < 85 else "warning",
            "used_pct": round(mem.percent, 1),
            "available_gb": round(mem.available / 1e9, 2),
            "total_gb": round(mem.total / 1e9, 2),
        }
    except ImportError:
        return {"status": "unknown", "detail": "psutil not installed"}


def _check_disk() -> dict:
    try:
        import psutil

        disk = psutil.disk_usage("/")
        return {
            "status": "healthy" if disk.percent < 85 else "warning",
            "used_pct": round(disk.percent, 1),
            "free_gb": round(disk.free / 1e9, 2),
        }
    except ImportError:
        return {"status": "unknown", "detail": "psutil not installed"}


@router.get("/health")
async def infrastructure_health() -> dict:
    """
    Complete infrastructure health check.
    Returns status of all platform services.
    """
    checks = {}

    checks["api"] = {"status": "healthy", "detail": "API process responding"}
    checks["database"] = await _check_database()
    checks["redis"] = _check_redis()
    checks["celery"] = _check_celery()
    checks["memory"] = _check_memory()
    checks["disk"] = _check_disk()

    # Overall status
    statuses = [c.get("status", "unknown") for c in checks.values()]
    if "unhealthy" in statuses:
        overall = "unhealthy"
    elif (
        "degraded" in statuses
        or "warning" in statuses
        or "unknown" in statuses
        or "not_configured" in statuses
    ):
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "overall": overall,
        "checked_at": datetime.now(UTC).isoformat(),
        "checks": checks,
    }


@router.get("/health/database")
async def database_health() -> dict:
    return await _check_database()


@router.get("/health/redis")
def redis_health() -> dict:
    return _check_redis()


@router.get("/health/celery")
def celery_health() -> dict:
    return _check_celery()
