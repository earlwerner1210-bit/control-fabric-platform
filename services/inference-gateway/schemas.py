"""Inference gateway request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema


class GenerateRequest(BaseModel):
    prompt: str
    system_prompt: str | None = None
    max_tokens: int = Field(default=1024, ge=1, le=16384)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    response_format: str | None = Field(default=None, description="json or text")
    provider: str | None = None


class SummarizeRequest(BaseModel):
    text: str
    max_length: int = Field(default=200, ge=10, le=2000)
    provider: str | None = None


class ClassifyRequest(BaseModel):
    text: str
    categories: list[str]
    provider: str | None = None


class ExplainRequest(BaseModel):
    text: str
    context: str | None = None
    provider: str | None = None


class GenerateResponse(BaseSchema):
    output: str
    model: str
    usage: dict[str, int] = Field(default_factory=dict)


class SummarizeResponse(BaseSchema):
    summary: str
    model: str


class ClassifyResponse(BaseSchema):
    category: str
    confidence: float
    model: str


class ExplainResponse(BaseSchema):
    explanation: str
    model: str
