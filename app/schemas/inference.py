"""Inference gateway schemas."""

from __future__ import annotations

import uuid
from typing import Any

from app.schemas.common import BaseSchema


class InferenceRequest(BaseSchema):
    operation: str  # generate, summarize, classify, explain
    prompt_template_name: str | None = None
    system_prompt: str | None = None
    user_prompt: str
    variables: dict[str, Any] = {}
    output_schema: dict | None = None
    max_tokens: int = 2048
    temperature: float = 0.1


class InferenceResponse(BaseSchema):
    output: dict[str, Any] | str
    provider: str
    model: str
    latency_ms: int
    token_count_input: int | None = None
    token_count_output: int | None = None


class ModelRunResponse(BaseSchema):
    id: uuid.UUID
    provider: str
    model_name: str
    operation: str
    latency_ms: int | None = None
    success: bool
    created_at: Any
