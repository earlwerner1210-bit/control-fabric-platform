"""vLLM / OpenAI-compatible inference provider."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import InferenceError
from app.core.logging import get_logger
from app.services.inference.provider_base import BaseInferenceProvider

logger = get_logger("inference.vllm")


class VLLMProvider(BaseInferenceProvider):
    provider_name = "vllm"

    def __init__(
        self, base_url: str | None = None, model: str | None = None, api_key: str | None = None
    ) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.VLLM_BASE_URL
        self.model = model or settings.VLLM_MODEL
        self.api_key = api_key or settings.OPENAI_API_KEY or "no-key"

    async def _chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.1,
        response_format: dict | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            logger.error("vllm_request_failed", error=str(e))
            raise InferenceError(f"vLLM request failed: {e}") from e

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response_format = {"type": "json_object"} if output_schema else None
        result = await self._chat_completion(messages, max_tokens, temperature, response_format)
        content = result["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw_response": content}

    async def summarize(self, text: str, system_prompt: str | None = None) -> str:
        sys_prompt = (
            system_prompt or "You are an expert summarizer. Provide a concise, accurate summary."
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Summarize the following:\n\n{text}"},
        ]
        result = await self._chat_completion(messages, max_tokens=1024, temperature=0.2)
        return result["choices"][0]["message"]["content"]

    async def classify(
        self, text: str, categories: list[str], system_prompt: str | None = None
    ) -> dict[str, Any]:
        sys_prompt = (
            system_prompt
            or "Classify the text into exactly one category. Return JSON with 'category' and 'confidence' fields."
        )
        cat_list = ", ".join(categories)
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Categories: {cat_list}\n\nText: {text}"},
        ]
        result = await self._chat_completion(
            messages, max_tokens=256, temperature=0.1, response_format={"type": "json_object"}
        )
        content = result["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"category": "unknown", "confidence": 0.0, "raw": content}

    async def explain(self, context: str, question: str, system_prompt: str | None = None) -> str:
        sys_prompt = (
            system_prompt or "Provide an evidence-backed explanation based on the given context."
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ]
        result = await self._chat_completion(messages, max_tokens=2048, temperature=0.2)
        return result["choices"][0]["message"]["content"]
