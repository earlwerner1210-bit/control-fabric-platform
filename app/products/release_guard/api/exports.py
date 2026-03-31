"""Audit export endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.products.release_guard.services.export_service import export_service

router = APIRouter(prefix="/exports")


class ExportBody(BaseModel):
    workspace_id: str
    requested_by: str = "api-user"
    format: str = "csv"
    date_from: str | None = None
    date_to: str | None = None


@router.post("/releases")
def export_releases(body: ExportBody) -> dict:
    job = export_service.export_releases(
        body.workspace_id,
        body.requested_by,
        body.format,
        body.date_from,
        body.date_to,
    )
    return asdict(job)


@router.post("/approvals")
def export_approvals(body: ExportBody) -> dict:
    job = export_service.export_approvals(body.workspace_id, body.requested_by, body.format)
    return asdict(job)


@router.post("/exceptions")
def export_exceptions(body: ExportBody) -> dict:
    job = export_service.export_exceptions(body.workspace_id, body.requested_by, body.format)
    return asdict(job)


@router.get("")
def list_exports(workspace_id: str) -> dict:
    jobs = export_service.list_jobs(workspace_id)
    return {"count": len(jobs), "exports": [asdict(j) for j in jobs]}


@router.get("/{export_id}/download")
def download_export(export_id: str) -> Response:
    try:
        job = export_service.get_job(export_id)
        content = export_service.get_content(export_id)
        media_type = "text/csv" if job.format == "csv" else "application/json"
        filename = f"release-guard-{job.export_type}-{job.export_id[:8]}.{job.format}"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
