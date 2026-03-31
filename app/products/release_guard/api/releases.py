"""Release request endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.products.release_guard.domain.enums import ReleaseRisk, ReleaseStatus
from app.products.release_guard.services.release_request_service import release_request_service
from app.products.release_guard.services.workspace_service import workspace_service

router = APIRouter(prefix="/releases")


class CreateReleaseBody(BaseModel):
    workspace_id: str
    title: str
    service_name: str
    environment: str = "production"
    risk_level: ReleaseRisk = ReleaseRisk.MEDIUM
    description: str = ""
    submitted_by: str = "api-user"


class SubmitReleaseBody(BaseModel):
    workspace_id: str


@router.post("")
def create_release(body: CreateReleaseBody) -> dict:
    ws = workspace_service.get(body.workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    release = release_request_service.create(
        workspace_id=body.workspace_id,
        tenant_id=ws.tenant_id,
        title=body.title,
        service_name=body.service_name,
        environment=body.environment,
        risk_level=body.risk_level,
        submitted_by=body.submitted_by,
        description=body.description,
    )
    return asdict(release)


@router.get("")
def list_releases(workspace_id: str, status: str | None = None) -> dict:
    status_filter = ReleaseStatus(status) if status else None
    releases = release_request_service.list_for_workspace(workspace_id, status_filter)
    return {
        "count": len(releases),
        "releases": [
            {
                "release_id": r.release_id,
                "title": r.title,
                "service_name": r.service_name,
                "environment": r.environment,
                "status": r.status.value,
                "risk_level": r.risk_level.value,
                "submitted_by": r.submitted_by,
                "created_at": r.created_at,
                "blocked_reason": r.blocked_reason,
                "evidence_count": len(r.evidence_items),
                "missing_evidence": r.missing_evidence,
            }
            for r in releases
        ],
    }


@router.get("/{release_id}")
def get_release(release_id: str) -> dict:
    try:
        return asdict(release_request_service.get(release_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{release_id}/submit")
def submit_release(release_id: str, body: SubmitReleaseBody) -> dict:
    ws = workspace_service.get(body.workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        release = release_request_service.submit(release_id, ws.policy_profile)
        # Auto-request approval if needed
        from app.products.release_guard.policies.profiles import approvers_required, needs_approval
        from app.products.release_guard.services.approval_service import approval_service

        if release.status == ReleaseStatus.PENDING:
            members = workspace_service.get_members(body.workspace_id)
            approvers = [m for m in members if m.role in ("approver", "admin")]
            needed = approvers_required(ws.policy_profile)
            for approver in approvers[:needed]:
                approval_service.request(release_id, approver.email)
        return {
            "release_id": release_id,
            "status": release.status.value,
            "blocked_reason": release.blocked_reason,
            "missing_evidence": release.missing_evidence,
            "awaiting_approval": release.status == ReleaseStatus.PENDING,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{release_id}/cancel")
def cancel_release(release_id: str, cancelled_by: str = "api-user") -> dict:
    try:
        release = release_request_service.cancel(release_id, cancelled_by)
        return {"release_id": release_id, "status": release.status.value}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{release_id}/timeline")
def get_timeline(release_id: str) -> dict:
    try:
        release = release_request_service.get(release_id)
        return {"release_id": release_id, "timeline": release.audit_trail}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{release_id}/explain")
def explain_release(release_id: str) -> dict:
    try:
        return release_request_service.get_explain(release_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
