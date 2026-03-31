"""
Notification preferences API.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth.middleware import CurrentUser, get_current_user
from app.core.notifications.manager import notification_manager
from app.core.notifications.preferences import NotificationChannel, NotificationEvent

router = APIRouter(prefix="/notifications", tags=["notifications"])


class SetPreferenceBody(BaseModel):
    event: NotificationEvent
    channel: NotificationChannel
    destination: str
    enabled: bool = True
    min_severity: str = "critical"


class TestNotificationBody(BaseModel):
    event: NotificationEvent
    subject: str = "Test notification from Control Fabric Platform"


@router.get("/preferences")
def get_preferences(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    prefs = notification_manager.get_preferences(current_user.user_id, current_user.tenant_id)
    return {
        "user_id": current_user.user_id,
        "count": len(prefs),
        "preferences": [asdict(p) for p in prefs],
    }


@router.post("/preferences")
def set_preference(
    body: SetPreferenceBody,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    pref = notification_manager.set_preference(
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        event=body.event,
        channel=body.channel,
        destination=body.destination,
        enabled=body.enabled,
        min_severity=body.min_severity,
    )
    return asdict(pref)


@router.delete("/preferences/{pref_id}")
def delete_preference(
    pref_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    deleted = notification_manager.delete_preference(pref_id, current_user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preference not found")
    return {"deleted": True, "pref_id": pref_id}


@router.get("/history")
def get_history(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    records = notification_manager.get_notification_history(user_id=current_user.user_id)
    return {
        "count": len(records),
        "records": [asdict(r) for r in records],
    }


@router.get("/events")
def list_events() -> dict:
    return {
        "events": [e.value for e in NotificationEvent],
        "channels": [c.value for c in NotificationChannel],
    }
