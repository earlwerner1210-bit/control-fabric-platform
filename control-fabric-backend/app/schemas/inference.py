"""Inference gateway schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schemas.common import BaseSchema


class InferenceRequest(BaseSchema):
    """Request to the inference gateway."""

    prompt: str = Field(..., min_length=1, description="User / task prompt")
    system_prompt: str | None = Field(
        default=None,
        description="Optional system prompt to set model behaviour",
    )
    model: str | None = Field(
        default=None,
        description="Model identifier override; defaults to configured model",
    )
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128_000)
    response_format: dict[str, Any] | None = Field(
        default=None,
        description="Optional JSON-schema or format hint for structured output",
    )


class InferenceResponse(BaseSchema):
    """Response from the inference gateway."""

    content: str = Field(..., description="Generated text from the model")
    model: str = Field(..., description="Model that actually served the request")
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    latency_ms: float = Field(..., ge=0.0, description="Round-trip latency in milliseconds")
