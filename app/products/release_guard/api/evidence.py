"""Evidence attachment endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.products.release_guard.domain.enums import EvidenceType
from app.products.release_guard.services.release_request_service import release_request_service
from app.products.release_guard.services.workspace_service import workspace_service

router = APIRouter(prefix="/releases/{release_id}/evidence")


class AddEvidenceBody(BaseModel):
    workspace_id: str
    title: str
    reference: str
    url: str = ""
    added_by: str = "api-user"


@router.post("/ticket")
def attach_ticket(release_id: str, body: AddEvidenceBody) -> dict:
    try:
        item = release_request_service.add_evidence(
            release_id,
            EvidenceType.JIRA_TICKET,
            body.title,
            body.reference,
            body.url,
            body.added_by,
        )
        return asdict(item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pr")
def attach_pr(release_id: str, body: AddEvidenceBody) -> dict:
    try:
        item = release_request_service.add_evidence(
            release_id,
            EvidenceType.GITHUB_PR,
            body.title,
            body.reference,
            body.url,
            body.added_by,
        )
        return asdict(item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/build")
def attach_build(release_id: str, body: AddEvidenceBody) -> dict:
    try:
        item = release_request_service.add_evidence(
            release_id,
            EvidenceType.BUILD_RESULT,
            body.title,
            body.reference,
            body.url,
            body.added_by,
        )
        return asdict(item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rollback")
def attach_rollback(release_id: str, body: AddEvidenceBody) -> dict:
    try:
        item = release_request_service.add_evidence(
            release_id,
            EvidenceType.ROLLBACK_PLAN,
            body.title,
            body.reference,
            body.url,
            body.added_by,
        )
        return asdict(item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
def get_evidence(release_id: str, workspace_id: str) -> dict:
    try:
        release = release_request_service.get(release_id)
        ws = workspace_service.get(workspace_id)
        profile = ws.policy_profile if ws else None
        result: dict = {
            "release_id": release_id,
            "evidence_count": len(release.evidence_items),
            "evidence": [asdict(e) for e in release.evidence_items],
        }
        if profile:
            result["completeness"] = release_request_service.check_evidence_completeness(
                release_id, profile
            )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/check")
def check_evidence(release_id: str, workspace_id: str) -> dict:
    try:
        ws = workspace_service.get(workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return release_request_service.check_evidence_completeness(release_id, ws.policy_profile)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{evidence_id}")
def remove_evidence(release_id: str, evidence_id: str) -> dict:
    release_request_service.remove_evidence(release_id, evidence_id)
    return {"removed": True, "evidence_id": evidence_id}
