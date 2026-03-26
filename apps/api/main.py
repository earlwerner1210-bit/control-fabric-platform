"""Control Fabric Platform — FastAPI API Gateway."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes import admin, auth, cases, compile, documents, evals
from shared.config import get_settings
from shared.db.base import engine

# ── Lifespan ──────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown hooks."""
    settings = get_settings()
    app.state.settings = settings
    # Connection pool is created lazily by SQLAlchemy; we just verify here.
    async with engine.connect() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    yield
    await engine.dispose()


# ── App ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Control Fabric Platform API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow all origins in dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request timing middleware ─────────────────────────────────────────────


@app.middleware("http")
async def add_timing_header(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
    start = time.perf_counter()
    response: Response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - start) * 1000:.2f}"
    return response


# ── Route registration ───────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)
app.include_router(compile.router, prefix=API_PREFIX)
app.include_router(cases.router, prefix=API_PREFIX)
app.include_router(evals.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)


# ── Infrastructure endpoints ─────────────────────────────────────────────


@app.get("/health", tags=["infra"])
async def health() -> dict[str, str]:
    """Liveness probe — always returns OK if the process is running."""
    return {"status": "ok"}


@app.get("/ready", tags=["infra"])
async def ready() -> dict[str, Any]:
    """Readiness probe — verifies database connectivity."""
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "ready": db_ok,
        "checks": {"database": "up" if db_ok else "down"},
    }


@app.get("/metrics", tags=["infra"])
async def metrics() -> dict[str, Any]:
    """Basic runtime metrics (placeholder for Prometheus integration)."""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
    }
