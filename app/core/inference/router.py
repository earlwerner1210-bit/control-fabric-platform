"""Inference gateway HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from shared.schemas.common import TenantContext
from shared.security.auth import get_current_user

from .schemas import (
    ClassifyRequest,
    ClassifyResponse,
    ExplainRequest,
    ExplainResponse,
    GenerateRequest,
    GenerateResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from .service import InferenceGateway

router = APIRouter(prefix="/inference", tags=["inference"])


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    body: GenerateRequest,
    ctx: TenantContext = Depends(get_current_user),
):
    gw = InferenceGateway(body.provider)
    result = await gw.generate_structured(
        prompt=body.prompt,
        system_prompt=body.system_prompt,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
        response_format=body.response_format,
    )
    return GenerateResponse(**result)


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(
    body: SummarizeRequest,
    ctx: TenantContext = Depends(get_current_user),
):
    gw = InferenceGateway(body.provider)
    result = await gw.summarize(body.text, body.max_length)
    return SummarizeResponse(**result)


@router.post("/classify", response_model=ClassifyResponse)
async def classify(
    body: ClassifyRequest,
    ctx: TenantContext = Depends(get_current_user),
):
    gw = InferenceGateway(body.provider)
    result = await gw.classify(body.text, body.categories)
    return ClassifyResponse(**result)


@router.post("/explain", response_model=ExplainResponse)
async def explain(
    body: ExplainRequest,
    ctx: TenantContext = Depends(get_current_user),
):
    gw = InferenceGateway(body.provider)
    result = await gw.explain(body.text, body.context)
    return ExplainResponse(**result)
