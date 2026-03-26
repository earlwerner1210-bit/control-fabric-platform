"""Feedback capture schemas."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FeedbackCategory(str, enum.Enum):
    PARSER_ACCURACY = "parser_accuracy"
    RULE_ACCURACY = "rule_accuracy"
    EVIDENCE_GAP = "evidence_gap"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    UNCLEAR_EXPLANATION = "unclear_explanation"
    MISSING_BUSINESS_CONTEXT = "missing_business_context"
    WORKFLOW_GAP = "workflow_gap"
    PROMPT_ISSUE = "prompt_issue"
    MODEL_QUALITY = "model_quality"
    DATA_QUALITY = "data_quality"
    OTHER = "other"


class FeedbackSeverity(str, enum.Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FeedbackEntryCreate(BaseModel):
    category: FeedbackCategory
    severity: FeedbackSeverity = FeedbackSeverity.MEDIUM
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1)
    affected_component: str | None = Field(None, description="parser, rule_engine, validator, inference, evidence, workflow")
    suggested_improvement: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilot_case_id: uuid.UUID
    submitted_by: uuid.UUID
    category: FeedbackCategory
    severity: FeedbackSeverity
    title: str
    description: str
    affected_component: str | None
    suggested_improvement: str | None
    tags: list[str]
    metadata: dict[str, Any]
    created_at: datetime


class FeedbackSummary(BaseModel):
    total_entries: int
    by_category: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_component: dict[str, int] = Field(default_factory=dict)
    top_issues: list[FeedbackEntryResponse] = Field(default_factory=list)
