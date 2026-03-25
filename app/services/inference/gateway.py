"""Inference gateway – unified interface for model invocation."""

from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import ModelRun
from app.services.inference.provider_base import BaseInferenceProvider
from app.services.inference.provider_fake import FakeProvider
from app.services.inference.provider_mlx import MLXProvider
from app.services.inference.provider_vllm import VLLMProvider

logger = get_logger("inference_gateway")


def get_inference_provider() -> BaseInferenceProvider:
    """Factory for inference providers based on configuration."""
    settings = get_settings()
    if settings.INFERENCE_PROVIDER == "vllm" or settings.INFERENCE_PROVIDER == "openai":
        return VLLMProvider()
    elif settings.INFERENCE_PROVIDER == "mlx":
        return MLXProvider(model_path=settings.MLX_MODEL_PATH)
    else:
        return FakeProvider()


class InferenceGateway:
    def __init__(
        self,
        db: AsyncSession,
        provider: BaseInferenceProvider | None = None,
    ) -> None:
        self.db = db
        self.provider = provider or get_inference_provider()

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        tenant_id: uuid.UUID,
        workflow_case_id: uuid.UUID | None = None,
        output_schema: dict | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        start = time.monotonic()
        try:
            result = await self.provider.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=output_schema,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            latency = int((time.monotonic() - start) * 1000)
            await self._log_run(tenant_id, "generate", workflow_case_id, result, latency, True)
            return result
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            await self._log_run(tenant_id, "generate", workflow_case_id, {}, latency, False, str(e))
            raise

    async def summarize(
        self,
        text: str,
        tenant_id: uuid.UUID,
        workflow_case_id: uuid.UUID | None = None,
        system_prompt: str | None = None,
    ) -> str:
        start = time.monotonic()
        result = await self.provider.summarize(text, system_prompt)
        latency = int((time.monotonic() - start) * 1000)
        await self._log_run(tenant_id, "summarize", workflow_case_id, {"summary": result}, latency, True)
        return result

    async def classify(
        self,
        text: str,
        categories: list[str],
        tenant_id: uuid.UUID,
        workflow_case_id: uuid.UUID | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        start = time.monotonic()
        result = await self.provider.classify(text, categories, system_prompt)
        latency = int((time.monotonic() - start) * 1000)
        await self._log_run(tenant_id, "classify", workflow_case_id, result, latency, True)
        return result

    async def explain(
        self,
        context: str,
        question: str,
        tenant_id: uuid.UUID,
        workflow_case_id: uuid.UUID | None = None,
        system_prompt: str | None = None,
    ) -> str:
        start = time.monotonic()
        result = await self.provider.explain(context, question, system_prompt)
        latency = int((time.monotonic() - start) * 1000)
        await self._log_run(tenant_id, "explain", workflow_case_id, {"explanation": result}, latency, True)
        return result

    async def _log_run(
        self,
        tenant_id: uuid.UUID,
        operation: str,
        workflow_case_id: uuid.UUID | None,
        output: dict,
        latency_ms: int,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        run = ModelRun(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_case_id=workflow_case_id,
            provider=self.provider.provider_name,
            model_name=getattr(self.provider, "model", "fake"),
            operation=operation,
            input_payload={},  # Don't log full prompts to avoid data leakage
            output_payload=output,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message,
        )
        self.db.add(run)
        await self.db.flush()
