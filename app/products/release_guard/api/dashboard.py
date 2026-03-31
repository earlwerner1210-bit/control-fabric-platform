"""Dashboard endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from app.products.release_guard.services.dashboard_service import dashboard_service

router = APIRouter(prefix="/dashboard")


@router.get("/summary/{workspace_id}")
def get_summary(workspace_id: str, days: int = 30) -> dict:
    summary = dashboard_service.get_summary(workspace_id, days)
    return asdict(summary)
