"""Reasoning provider abstraction — pluggable backends for model-assisted reasoning."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.reasoning.types import ReasoningRequest, ReasoningStep
from app.core.types import ConfidenceScore, DeterminismLevel


class ReasoningProvider(ABC):
    """Abstract provider for model-assisted reasoning."""

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def reason(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> tuple[str, float]: ...


class StubReasoningProvider(ReasoningProvider):
    """Stub provider that returns deterministic placeholder results.

    Used for testing and as a fallback when no model is configured.
    """

    @property
    def provider_name(self) -> str:
        return "stub"

    def reason(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> tuple[str, float]:
        return (
            f"Stub reasoning result for: {prompt[:100]}",
            0.5,
        )


class DeterministicRulesProvider(ReasoningProvider):
    """Provider that delegates to registered deterministic rule functions."""

    def __init__(self) -> None:
        self._rules: dict[str, Any] = {}

    @property
    def provider_name(self) -> str:
        return "deterministic_rules"

    def register_rule(self, name: str, rule_fn: Any) -> None:
        self._rules[name] = rule_fn

    def reason(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> tuple[str, float]:
        rule_name = context.get("rule_name", "")
        rule_fn = self._rules.get(rule_name)
        if rule_fn:
            result = rule_fn(context)
            return str(result), 1.0
        return f"No rule found for: {rule_name}", 0.0
