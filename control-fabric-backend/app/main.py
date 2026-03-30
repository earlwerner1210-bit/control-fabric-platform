"""FastAPI application factory and entry point for Control Fabric backend."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.middleware.request_id import RequestIdMiddleware
from app.api.routes import auth, cases, contracts, documents, evals, health
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: run setup on startup, teardown on shutdown."""
    setup_logging()
    yield


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Control Fabric Backend",
        description="AI platform for telecom margin assurance, contract intelligence, and operational control.",
        version=settings.APP_VERSION,
        lifespan=_lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS (permissive for development) ─────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Custom middleware (outermost first) ────────────────────────────────
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(RateLimitMiddleware, max_tokens=60.0, refill_rate=10.0)

    # ── Exception handlers ────────────────────────────────────────────────
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "code": exc.code,
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────
    # Health / readiness / metrics (no prefix -- lives at root)
    app.include_router(health.router)

    # API v1 routes
    app.include_router(auth.router)
    app.include_router(documents.router)
    app.include_router(contracts.router)
    app.include_router(cases.router)
    app.include_router(evals.router)

    return app


# ---------------------------------------------------------------------------
# Module-level app instance for uvicorn
# ---------------------------------------------------------------------------

app = create_app()
