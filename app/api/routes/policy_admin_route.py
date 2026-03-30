"""API routes for the Policy Administration Layer."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.policy_admin import PolicyDefinition, PolicyManager

router = APIRouter(prefix="/policies", tags=["policies"])

_manager = PolicyManager()


class CreatePolicyRequest(BaseModel):
    policy_name: str
    description: str = ""
    rules: list[str] = []
    target_packs: list[str] = []
    created_by: str = "system"


@router.post("/", response_model=PolicyDefinition)
async def create_policy(req: CreatePolicyRequest) -> PolicyDefinition:
    """Create a new policy draft."""
    return _manager.create_draft(
        policy_name=req.policy_name,
        description=req.description,
        rules=req.rules,
        target_packs=req.target_packs,
        created_by=req.created_by,
    )


@router.get("/", response_model=list[PolicyDefinition])
async def list_policies(status: str | None = None) -> list[PolicyDefinition]:
    """List policies, optionally filtered by status."""
    from app.core.policy_admin import PolicyStatus

    if status:
        try:
            ps = PolicyStatus(status)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from e
        return _manager.list_policies(ps)
    return _manager.list_policies()


@router.get("/{policy_id}", response_model=PolicyDefinition)
async def get_policy(policy_id: str) -> PolicyDefinition:
    """Get a policy by ID."""
    policy = _manager.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.post("/{policy_id}/simulate")
async def simulate_policy(policy_id: str, sample_size: int = 100) -> dict[str, object]:
    """Run a simulation against sample data."""
    try:
        result = _manager.simulate(policy_id, sample_size)
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{policy_id}/publish", response_model=PolicyDefinition)
async def publish_policy(policy_id: str, published_by: str = "system") -> PolicyDefinition:
    """Publish a draft policy."""
    try:
        return _manager.publish(policy_id, published_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{policy_id}/rollback", response_model=PolicyDefinition)
async def rollback_policy(policy_id: str) -> PolicyDefinition:
    """Roll back a published policy."""
    try:
        return _manager.rollback(policy_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{policy_id}/archive", response_model=PolicyDefinition)
async def archive_policy(policy_id: str) -> PolicyDefinition:
    """Archive a policy."""
    try:
        return _manager.archive(policy_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
