"""vLLM-compatible inference provider using OpenAI-compatible API."""

from __future__ import annotations

from typing import Any

import httpx

from .base import BaseInferenceProvider


class VLLMProvider(BaseInferenceProvider):
    """Calls a vLLM-compatible API (OpenAI chat completions format)."""

    def __init__(self, base_url: str = "http://localhost:8000/v1", api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = "default"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format == "json":
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})
        return {
            "output": choice["message"]["content"],
            "model": data.get("model", self.model),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        }

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return await self._chat_completion(messages, max_tokens, temperature, response_format)

    async def summarize(self, text: str, max_length: int = 200) -> dict[str, Any]:
        prompt = f"Summarize the following text in at most {max_length} words:\n\n{text}"
        result = await self.generate(
            prompt, system_prompt="You are a concise summarizer.", max_tokens=max_length * 2
        )
        return {"summary": result["output"], "model": result["model"]}

    async def classify(self, text: str, categories: list[str]) -> dict[str, Any]:
        cats = ", ".join(categories)
        prompt = (
            f"Classify the following text into one of these categories: {cats}.\n\n"
            f"Text: {text}\n\n"
            f'Respond with JSON: {{"category": "<chosen>", "confidence": <0.0-1.0>}}'
        )
        result = await self.generate(prompt, response_format="json", temperature=0.1)
        import json

        try:
            parsed = json.loads(result["output"])
            return {
                "category": parsed.get("category", categories[0]),
                "confidence": float(parsed.get("confidence", 0.5)),
                "model": result["model"],
            }
        except (json.JSONDecodeError, ValueError):
            return {"category": categories[0], "confidence": 0.0, "model": result["model"]}

    async def explain(self, text: str, context: str | None = None) -> dict[str, Any]:
        ctx = f"\n\nContext: {context}" if context else ""
        prompt = f"Explain the following in clear, simple terms:{ctx}\n\n{text}"
        result = await self.generate(prompt, system_prompt="You explain complex topics clearly.")
        return {"explanation": result["output"], "model": result["model"]}
