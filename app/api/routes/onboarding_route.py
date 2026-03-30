"""API routes for the Onboarding Modelling Studio."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.onboarding import OnboardingSession, OnboardingStep, OnboardingStudio, StepOutcome

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_studio = OnboardingStudio()


@router.post("/sessions", response_model=OnboardingSession)
async def create_session(domain_name: str, created_by: str) -> OnboardingSession:
    """Start a new onboarding session."""
    return _studio.create_session(domain_name, created_by)


@router.get("/sessions", response_model=list[OnboardingSession])
async def list_sessions() -> list[OnboardingSession]:
    """List all onboarding sessions."""
    return _studio.list_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, object]:
    """Get session details and progress."""
    session = _studio.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _studio.get_progress(session_id)


@router.post("/sessions/{session_id}/advance", response_model=StepOutcome)
async def advance_step(session_id: str) -> StepOutcome:
    """Advance to the next step."""
    try:
        return _studio.advance_step(session_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sessions/{session_id}/skip", response_model=StepOutcome)
async def skip_step(session_id: str, reason: str = "") -> StepOutcome:
    """Skip the current step (if not required)."""
    try:
        return _studio.skip_step(session_id, reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/steps", response_model=list[OnboardingStep])
async def get_step_definitions() -> list[OnboardingStep]:
    """Return all step definitions."""
    return _studio.get_step_definitions()
