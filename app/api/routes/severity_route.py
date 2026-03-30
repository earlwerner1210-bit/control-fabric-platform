"""API routes for the Severity and Prioritisation Engine."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.severity import ScoredCase, SeverityEngine, SeverityInput

router = APIRouter(prefix="/severity", tags=["severity"])

_engine = SeverityEngine()


@router.post("/score", response_model=ScoredCase)
async def score_case(inp: SeverityInput) -> ScoredCase:
    """Score a single case."""
    return _engine.score(inp)


@router.post("/score-batch", response_model=list[ScoredCase])
async def score_batch(inputs: list[SeverityInput]) -> list[ScoredCase]:
    """Score and rank a batch of cases."""
    return _engine.score_batch(inputs)


@router.post("/priority-queue", response_model=list[ScoredCase])
async def priority_queue(inputs: list[SeverityInput]) -> list[ScoredCase]:
    """Score, rank, and filter to actionable cases only."""
    scored = _engine.score_batch(inputs)
    return _engine.get_priority_queue(scored)


@router.get("/weights")
async def get_weights() -> list[dict[str, object]]:
    """Return current scoring weights."""
    return [w.model_dump() for w in _engine.weights]
