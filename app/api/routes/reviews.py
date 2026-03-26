"""Operator review workflow API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.schemas.review import (
    ReviewDecisionCreate,
    ReviewDecisionResponse,
    ReviewerNoteCreate,
    ReviewerNoteResponse,
    ReviewRequest,
    ReviewResponse,
    ReviewSummary,
)
from app.services.review import ReviewService

router = APIRouter(prefix="/pilot-cases", tags=["reviews"])

_review_service = ReviewService()

DEMO_USER = uuid.UUID("00000000-0000-0000-0000-000000000098")


@router.post("/{pilot_case_id}/review", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(pilot_case_id: uuid.UUID, data: ReviewRequest):
    return _review_service.create_review(pilot_case_id, data)


@router.get("/{pilot_case_id}/review", response_model=ReviewResponse)
async def get_review(pilot_case_id: uuid.UUID):
    review = _review_service.get_review(pilot_case_id)
    if review is None:
        raise HTTPException(status_code=404, detail="No review found for this case")
    return review


@router.post("/{pilot_case_id}/review/decision", response_model=ReviewDecisionResponse, status_code=status.HTTP_201_CREATED)
async def add_review_decision(pilot_case_id: uuid.UUID, data: ReviewDecisionCreate):
    try:
        return _review_service.add_decision(pilot_case_id, DEMO_USER, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{pilot_case_id}/review/note", response_model=ReviewerNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_reviewer_note(pilot_case_id: uuid.UUID, data: ReviewerNoteCreate):
    try:
        return _review_service.add_note(pilot_case_id, DEMO_USER, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{pilot_case_id}/review/summary", response_model=ReviewSummary)
async def get_review_summary(pilot_case_id: uuid.UUID):
    summary = _review_service.get_summary(pilot_case_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="No review found for this case")
    return summary
