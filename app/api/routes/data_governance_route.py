"""
Data governance API — classification, legal hold, redaction.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth.middleware import CurrentUser, get_current_user
from app.core.data_governance.classification import (
    ClassificationLevel,
    DataCategory,
)
from app.core.data_governance.manager import data_governance_manager

router = APIRouter(prefix="/data-governance", tags=["data-governance"])


class ClassifyRequest(BaseModel):
    entity_type: str
    entity_id: str
    classification: ClassificationLevel
    data_category: DataCategory
    sensitivity_reason: str = ""
    review_due: str | None = None


class BulkClassifyRequest(BaseModel):
    entity_ids: list[str]
    entity_type: str
    classification: ClassificationLevel
    data_category: DataCategory


class PlaceHoldRequest(BaseModel):
    hold_name: str
    description: str
    entity_ids: list[str]
    entity_types: list[str]
    legal_contact: str


class ReleaseHoldRequest(BaseModel):
    released_by: str


@router.post("/classify")
def classify_entity(
    req: ClassifyRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    record = data_governance_manager.classify(
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        classification=req.classification,
        data_category=req.data_category,
        classified_by=current_user.username,
        tenant_id=current_user.tenant_id,
        sensitivity_reason=req.sensitivity_reason,
        review_due=req.review_due,
    )
    return asdict(record)


@router.post("/classify/bulk")
def bulk_classify(
    req: BulkClassifyRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    records = data_governance_manager.bulk_classify(
        entity_ids=req.entity_ids,
        entity_type=req.entity_type,
        classification=req.classification,
        data_category=req.data_category,
        classified_by=current_user.username,
        tenant_id=current_user.tenant_id,
    )
    return {
        "classified_count": len(records),
        "classification": req.classification.value,
    }


@router.get("/classifications")
def get_classifications(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    records = data_governance_manager.get_all_classifications(current_user.tenant_id)
    return {
        "count": len(records),
        "records": [asdict(r) for r in records[:100]],
    }


@router.post("/holds")
def place_hold(
    req: PlaceHoldRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if "platform_admin" not in current_user.roles and "policy_admin" not in current_user.roles:
        raise HTTPException(
            status_code=403,
            detail="Platform admin or policy admin required",
        )
    hold = data_governance_manager.place_hold(
        hold_name=req.hold_name,
        description=req.description,
        entity_ids=req.entity_ids,
        entity_types=req.entity_types,
        placed_by=current_user.username,
        legal_contact=req.legal_contact,
        tenant_id=current_user.tenant_id,
    )
    return asdict(hold)


@router.get("/holds")
def get_active_holds(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    holds = data_governance_manager.get_active_holds(current_user.tenant_id)
    return {
        "active_hold_count": len(holds),
        "holds": [asdict(h) for h in holds],
    }


@router.post("/holds/{hold_id}/release")
def release_hold(
    hold_id: str,
    req: ReleaseHoldRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if "platform_admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Platform admin required")
    try:
        hold = data_governance_manager.release_hold(hold_id, req.released_by)
        return asdict(hold)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/holds/{entity_id}/check")
def check_hold(entity_id: str) -> dict:
    can_delete, reason = data_governance_manager.can_delete(entity_id)
    return {
        "entity_id": entity_id,
        "can_delete": can_delete,
        "reason": reason,
    }


@router.get("/summary")
def get_summary(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    return data_governance_manager.get_summary(current_user.tenant_id)
