"""
Inbound webhook receiver routes.

POST /webhooks/github           — GitHub Actions events
POST /webhooks/jira             — Jira issue events
POST /webhooks/servicenow       — ServiceNow notifications
POST /webhooks/azure-devops     — Azure DevOps events
POST /webhooks/generic/{source} — Any signed webhook
GET  /webhooks/log              — Recent event audit log
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.core.connectors.webhook_receiver import webhook_receiver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github")
async def receive_github(
    request: Request,
    x_hub_signature_256: str = Header(default="", alias="X-Hub-Signature-256"),
    x_github_event: str = Header(default="ping", alias="X-GitHub-Event"),
) -> dict:
    raw_body = await request.body()
    result = webhook_receiver.receive(
        source="github",
        event_type=x_github_event,
        raw_body=raw_body,
        signature=x_hub_signature_256,
    )
    if not result.accepted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Webhook rejected: {result.rejection_reason}",
        )
    return {
        "accepted": True,
        "event_type": x_github_event,
        "artefacts_created": result.artefacts_created,
        "reconciliation_triggered": result.reconciliation_triggered,
    }


@router.post("/jira")
async def receive_jira(
    request: Request,
    x_atlassian_token: str = Header(default="", alias="X-Atlassian-Token"),
) -> dict:
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    event_type = payload.get("webhookEvent", "jira:issue_updated")
    result = webhook_receiver.receive(
        source="jira",
        event_type=event_type,
        raw_body=raw_body,
        signature=x_atlassian_token,
    )
    if not result.accepted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Webhook rejected: {result.rejection_reason}",
        )
    return {
        "accepted": True,
        "event_type": event_type,
        "artefacts_created": result.artefacts_created,
    }


@router.post("/servicenow")
async def receive_servicenow(
    request: Request,
    authorization: str = Header(default="", alias="Authorization"),
) -> dict:
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    event_type = payload.get("event_type", "change_request.updated")
    result = webhook_receiver.receive(
        source="servicenow",
        event_type=event_type,
        raw_body=raw_body,
        signature=authorization,
    )
    if not result.accepted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Webhook rejected: {result.rejection_reason}",
        )
    return {
        "accepted": True,
        "event_type": event_type,
        "artefacts_created": result.artefacts_created,
    }


@router.post("/azure-devops")
async def receive_azure_devops(
    request: Request,
    x_vsts_signature: str = Header(default="", alias="X-Vsts-Signature"),
) -> dict:
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    event_type = payload.get("eventType", "build.complete")
    result = webhook_receiver.receive(
        source="azure_devops",
        event_type=event_type,
        raw_body=raw_body,
        signature=x_vsts_signature,
    )
    if not result.accepted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Webhook rejected: {result.rejection_reason}",
        )
    return {
        "accepted": True,
        "event_type": event_type,
        "artefacts_created": result.artefacts_created,
    }


@router.post("/generic/{source}")
async def receive_generic(
    source: str,
    request: Request,
    x_signature: str = Header(default="", alias="X-Signature"),
    x_timestamp: str = Header(default="", alias="X-Timestamp"),
) -> dict:
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    event_type = payload.get("event_type", "generic_event")
    result = webhook_receiver.receive(
        source=source,
        event_type=event_type,
        raw_body=raw_body,
        signature=x_signature,
        timestamp=x_timestamp,
    )
    if not result.accepted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Webhook rejected: {result.rejection_reason}",
        )
    return {
        "accepted": True,
        "source": source,
        "event_type": event_type,
        "artefacts_created": result.artefacts_created,
    }


@router.get("/log")
def get_webhook_log(limit: int = 50) -> dict:
    return {"events": webhook_receiver.get_event_log(limit)}
