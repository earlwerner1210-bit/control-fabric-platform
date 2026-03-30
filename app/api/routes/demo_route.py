"""Demo tenant routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.demo.demo_tenant import demo_tenant

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/reset")
def reset_demo() -> dict:
    """Reset the demo tenant to a clean seeded state."""
    return demo_tenant.reset()


@router.get("/scenarios")
def list_scenarios() -> dict:
    return {"scenarios": demo_tenant.get_scenarios()}


@router.post("/scenarios/{scenario_id}/run")
def run_scenario(scenario_id: str) -> dict:
    try:
        return demo_tenant.run_scenario(scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/run-all")
def run_all_scenarios() -> dict:
    """Run all 6 demo scenarios in sequence. Returns pass/fail for each."""
    return demo_tenant.run_all_scenarios()


@router.get("/results")
def get_results() -> dict:
    return {"results": demo_tenant.get_results()}
