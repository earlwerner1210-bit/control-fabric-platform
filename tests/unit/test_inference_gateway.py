"""Tests for the inference gateway."""

from __future__ import annotations

import pytest

from services.inference_gateway.gateway import (
    FakeProvider,
    InferenceGateway,
    InferenceRequest,
)


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider(
        default_response='{"result": "ok", "confidence": 0.95}',
        responses={
            "extract_clauses": '{"clauses": [{"id": "CL-001", "type": "obligation"}]}',
            "error_test": "not valid json {{{",
        },
    )


@pytest.fixture
def gateway(fake_provider: FakeProvider) -> InferenceGateway:
    gw = InferenceGateway()
    gw.register_provider("fake", fake_provider)
    return gw


class TestFakeProvider:
    """Tests for the FakeProvider."""

    @pytest.mark.asyncio
    async def test_default_response(self, fake_provider: FakeProvider):
        """FakeProvider should return default response."""
        request = InferenceRequest(prompt="Hello", provider="fake")
        response = await fake_provider.generate(request)
        assert response.provider == "fake"
        parsed = response.to_json()
        assert parsed is not None
        assert parsed["result"] == "ok"

    @pytest.mark.asyncio
    async def test_matched_response(self, fake_provider: FakeProvider):
        """FakeProvider should return matched response based on prompt."""
        request = InferenceRequest(prompt="Please extract_clauses from this", provider="fake")
        response = await fake_provider.generate(request)
        parsed = response.to_json()
        assert parsed is not None
        assert "clauses" in parsed

    @pytest.mark.asyncio
    async def test_call_count(self, fake_provider: FakeProvider):
        """FakeProvider should track call count."""
        assert fake_provider.call_count == 0
        await fake_provider.generate(InferenceRequest(prompt="test", provider="fake"))
        assert fake_provider.call_count == 1
        await fake_provider.generate(InferenceRequest(prompt="test2", provider="fake"))
        assert fake_provider.call_count == 2

    @pytest.mark.asyncio
    async def test_last_request_tracked(self, fake_provider: FakeProvider):
        """FakeProvider should track the last request."""
        request = InferenceRequest(prompt="tracked prompt", provider="fake", model="test-model")
        await fake_provider.generate(request)
        assert fake_provider.last_request is not None
        assert fake_provider.last_request.prompt == "tracked prompt"

    @pytest.mark.asyncio
    async def test_token_counts(self, fake_provider: FakeProvider):
        """FakeProvider should estimate token counts from word count."""
        request = InferenceRequest(prompt="one two three four five", provider="fake")
        response = await fake_provider.generate(request)
        assert response.input_tokens == 5
        assert response.output_tokens > 0


class TestInferenceGateway:
    """Tests for the InferenceGateway."""

    @pytest.mark.asyncio
    async def test_generate_routes_to_provider(self, gateway: InferenceGateway):
        """Gateway should route to registered provider."""
        request = InferenceRequest(prompt="test", provider="fake")
        response = await gateway.generate(request)
        assert response.content is not None
        assert response.provider == "fake"

    @pytest.mark.asyncio
    async def test_generate_unknown_provider_raises(self, gateway: InferenceGateway):
        """Gateway should raise for unknown provider."""
        request = InferenceRequest(prompt="test", provider="nonexistent")
        with pytest.raises(ValueError, match="Unknown provider"):
            await gateway.generate(request)

    @pytest.mark.asyncio
    async def test_generate_structured_returns_json(self, gateway: InferenceGateway):
        """generate_structured should return parsed JSON."""
        request = InferenceRequest(prompt="test", provider="fake")
        result = await gateway.generate_structured(request)
        assert isinstance(result, dict)
        assert result["result"] == "ok"

    @pytest.mark.asyncio
    async def test_generate_structured_invalid_json_raises(self, gateway: InferenceGateway):
        """generate_structured should raise on invalid JSON response."""
        request = InferenceRequest(prompt="error_test", provider="fake")
        with pytest.raises(ValueError, match="not valid JSON"):
            await gateway.generate_structured(request)

    @pytest.mark.asyncio
    async def test_latency_tracked(self, gateway: InferenceGateway):
        """Gateway should track latency."""
        request = InferenceRequest(prompt="test", provider="fake")
        response = await gateway.generate(request)
        assert response.latency_ms >= 0
