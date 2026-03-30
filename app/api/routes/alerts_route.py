"""Alert management routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.alerting.service import AlertPayload, alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AddAlertConfigBody(BaseModel):
    channel: str
    destination: str
    min_severity: str = "critical"
    name: str = ""


class TestAlertBody(BaseModel):
    severity: str = "critical"
    title: str = "Test alert from Control Fabric Platform"


@router.post("/config")
def add_config(body: AddAlertConfigBody) -> dict:
    alert_service.add_config(body.channel, body.destination, body.min_severity, body.name)
    return {"added": True, "channel": body.channel}


@router.post("/test")
async def test_alert(body: TestAlertBody) -> dict:
    payload = AlertPayload(
        severity=body.severity,
        title=body.title,
        case_id="test-case-000",
        affected_planes=["operations"],
        remediation=["This is a test alert — no action required"],
        tenant_id="default",
    )
    results = await alert_service.alert(payload)
    return {"results": results}


@router.get("/history")
def get_history() -> dict:
    return {"history": alert_service.get_history()}
