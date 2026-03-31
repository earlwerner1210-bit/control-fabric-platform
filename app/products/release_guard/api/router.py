"""Release Guard API router — mounts all /rg/ routes."""

from fastapi import APIRouter

from app.products.release_guard.api import (
    approvals,
    dashboard,
    demo,
    evidence,
    exceptions,
    exports,
    integrations,
    onboarding,
    policies,
    releases,
    workspaces,
)

rg_router = APIRouter(prefix="/rg", tags=["release-guard"])

rg_router.include_router(workspaces.router)
rg_router.include_router(onboarding.router)
rg_router.include_router(releases.router)
rg_router.include_router(evidence.router)
rg_router.include_router(approvals.router)
rg_router.include_router(exceptions.router)
rg_router.include_router(policies.router)
rg_router.include_router(integrations.router)
rg_router.include_router(dashboard.router)
rg_router.include_router(exports.router)
rg_router.include_router(demo.router)
