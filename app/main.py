"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.middleware.request_id import RequestIdMiddleware
from app.api.middleware.tenant_context import TenantContextMiddleware
from app.api.routes import (
    admin,
    auth,
    cases,
    compile,
    diagnostics,
    documents,
    evals,
    reconciliation,
)
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger, setup_logging
from app.core.telemetry import get_health_status, get_readiness_status, metrics

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("starting_application", version=get_settings().APP_VERSION)
    yield
    logger.info("shutting_down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(RateLimitMiddleware, max_tokens=200.0, refill_rate=20.0)

    # Exception handler
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "code": exc.code,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    # Routes
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(compile.router, prefix="/api/v1")
    app.include_router(cases.router, prefix="/api/v1")
    app.include_router(evals.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(reconciliation.router, prefix="/api/v1")
    app.include_router(diagnostics.router, prefix="/api/v1")

    # Health / readiness / metrics
    @app.get("/health")
    async def health():
        return get_health_status()

    @app.get("/ready")
    async def ready():
        return get_readiness_status()

    @app.get("/metrics")
    async def metrics_endpoint():
        return metrics.snapshot()

    return app


app = create_app()
