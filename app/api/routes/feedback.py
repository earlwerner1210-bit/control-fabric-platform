"""Feedback capture API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.schemas.feedback import (
    FeedbackEntryCreate,
    FeedbackEntryResponse,
    FeedbackSummary,
)
from app.services.feedback import FeedbackService

router = APIRouter(tags=["feedback"])

_feedback_service = FeedbackService()

DEMO_USER = uuid.UUID("00000000-0000-0000-0000-000000000098")


@router.post(
    "/pilot-cases/{pilot_case_id}/feedback",
    response_model=FeedbackEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(pilot_case_id: uuid.UUID, data: FeedbackEntryCreate):
    return _feedback_service.submit_feedback(pilot_case_id, DEMO_USER, data)


@router.get("/pilot-cases/{pilot_case_id}/feedback", response_model=list[FeedbackEntryResponse])
async def get_case_feedback(pilot_case_id: uuid.UUID):
    return _feedback_service.get_case_feedback(pilot_case_id)


@router.get("/feedback/summary", response_model=FeedbackSummary)
async def get_feedback_summary():
    return _feedback_service.get_summary()
