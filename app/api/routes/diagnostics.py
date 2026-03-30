"""Diagnostics and system health routes."""

from __future__ import annotations

import platform
import sys
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_role
from app.core.config import get_settings
from app.core.security import TenantContext
from app.core.telemetry import metrics
from app.db.session import get_db

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


class SystemInfo(BaseModel):
    app_name: str
    app_version: str
    environment: str
    python_version: str
    platform: str
    timestamp: str


class DatabaseHealth(BaseModel):
    connected: bool
    pool_size: int = 0
    pool_checked_out: int = 0
    pool_overflow: int = 0


class ServiceHealth(BaseModel):
    system: SystemInfo
    database: DatabaseHealth
    metrics_snapshot: dict = Field(default_factory=dict)
    domain_packs: list[str] = Field(default_factory=list)


@router.get("/info", response_model=SystemInfo)
async def system_info():
    """Return basic system information."""
    settings = get_settings()
    return SystemInfo(
        app_name=settings.APP_NAME,
        app_version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        python_version=sys.version,
        platform=platform.platform(),
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get("/health/deep", response_model=ServiceHealth)
async def deep_health(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    """Deep health check including database connectivity."""
    settings = get_settings()

    # Check database
    db_healthy = True
    try:
        from sqlalchemy import text

        await db.execute(text("SELECT 1"))
    except Exception:
        db_healthy = False

    return ServiceHealth(
        system=SystemInfo(
            app_name=settings.APP_NAME,
            app_version=settings.APP_VERSION,
            environment=settings.ENVIRONMENT,
            python_version=sys.version,
            platform=platform.platform(),
            timestamp=datetime.now(UTC).isoformat(),
        ),
        database=DatabaseHealth(
            connected=db_healthy,
            pool_size=settings.DATABASE_POOL_SIZE,
        ),
        metrics_snapshot=metrics.snapshot(),
        domain_packs=["contract_margin", "utilities_field", "telco_ops"],
    )


@router.get("/metrics/detailed")
async def detailed_metrics(
    ctx: TenantContext = Depends(require_role("admin")),
):
    """Return detailed metrics snapshot."""
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "metrics": metrics.snapshot(),
    }


@router.post("/cache/clear")
async def clear_cache(
    ctx: TenantContext = Depends(require_role("admin")),
):
    """Clear application caches (settings, etc.)."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    return {"status": "cache_cleared", "timestamp": datetime.now(UTC).isoformat()}
