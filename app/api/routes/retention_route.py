"""Data retention policy routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.retention.policy import RetentionPolicyManager

router = APIRouter(prefix="/retention", tags=["retention"])
_manager = RetentionPolicyManager()


class UpdateRuleBody(BaseModel):
    data_type: str
    retain_days: int


@router.get("/rules")
def get_rules() -> dict:
    return {"rules": _manager.get_all_rules()}


@router.put("/rules")
def update_rule(body: UpdateRuleBody) -> dict:
    rule = _manager.update_rule(body.data_type, body.retain_days)
    return {"updated": True, "data_type": rule.data_type, "retain_days": rule.retain_days}


@router.get("/simulate")
def simulate_cleanup() -> dict:
    return {
        "simulation": _manager.run_cleanup_simulation(),
        "note": "Simulation only — no data deleted",
    }


@router.post("/run")
def run_cleanup() -> dict:
    """Trigger the retention cleanup Celery task."""
    try:
        from app.worker.tasks import run_retention_cleanup

        result = run_retention_cleanup.delay()
        return {"task_id": str(result.id), "status": "queued"}
    except Exception as e:
        return {
            "status": "error",
            "detail": str(e),
            "note": "Celery worker may not be running",
        }
