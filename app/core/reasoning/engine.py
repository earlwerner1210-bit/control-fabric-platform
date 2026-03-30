"""Bounded reasoning engine — policy-scoped, deterministic-first reasoning."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.control_object import ControlObject
from app.core.errors import ReasoningPolicyViolation, ReasoningScopeViolation
from app.core.graph.service import GraphService
from app.core.reasoning.provider import (
    DeterministicRulesProvider,
    ReasoningProvider,
    StubReasoningProvider,
)
from app.core.reasoning.types import (
    ReasoningMode,
    ReasoningPolicy,
    ReasoningRequest,
    ReasoningResult,
    ReasoningStatus,
    ReasoningStep,
)
from app.core.types import (
    ConfidenceScore,
    ControlObjectId,
    DeterminismLevel,
    ReasoningScope,
)


class BoundedReasoningEngine:
    """Policy-scoped reasoning: deterministic rules first, model-assisted when allowed."""

    def __init__(
        self,
        graph_service: GraphService,
        provider: ReasoningProvider | None = None,
        default_policy: ReasoningPolicy | None = None,
    ) -> None:
        self._graph = graph_service
        self._provider = provider or StubReasoningProvider()
        self._default_policy = default_policy or ReasoningPolicy()
        self._deterministic_provider = DeterministicRulesProvider()

    @property
    def provider(self) -> ReasoningProvider:
        return self._provider

    def register_deterministic_rule(self, name: str, rule_fn: Any) -> None:
        self._deterministic_provider.register_rule(name, rule_fn)

    def reason(self, request: ReasoningRequest) -> ReasoningResult:
        """Execute bounded reasoning within policy constraints."""
        policy = request.policy or self._default_policy

        # Validate scope
        self._enforce_policy(request, policy)

        # Gather objects within scope
        objects = self._gather_scoped_objects(request, policy)

        steps: list[ReasoningStep] = []
        all_consulted: list[ControlObjectId] = []

        # Step 1: Gather evidence from objects
        step1 = ReasoningStep(
            step_number=1,
            action="gather_evidence",
            input_summary=f"Scope: {request.scope.value}, {len(objects)} objects",
            output_summary=f"Collected evidence from {len(objects)} objects",
            determinism_level=DeterminismLevel.DETERMINISTIC,
            objects_consulted=[o.id for o in objects],
        )
        steps.append(step1)
        all_consulted.extend(o.id for o in objects)

        # Step 2: Apply deterministic rules
        det_conclusion, det_confidence = self._apply_deterministic_rules(request, objects)
        step2 = ReasoningStep(
            step_number=2,
            action="deterministic_rules",
            input_summary=f"{len(objects)} objects evaluated",
            output_summary=det_conclusion,
            determinism_level=DeterminismLevel.DETERMINISTIC,
            confidence=ConfidenceScore(det_confidence),
        )
        steps.append(step2)

        conclusion = det_conclusion
        confidence = det_confidence
        determinism = DeterminismLevel.DETERMINISTIC

        # Step 3: Model-assisted reasoning if allowed and needed
        if (
            request.mode in (ReasoningMode.MODEL_ASSISTED, ReasoningMode.HYBRID)
            and ReasoningMode.MODEL_ASSISTED in policy.allowed_modes
            and det_confidence < policy.max_confidence_for_auto
        ):
            model_conclusion, model_conf = self._provider.reason(
                request.question,
                {
                    "objects": [o.model_dump(mode="json") for o in objects[:10]],
                    "deterministic_result": det_conclusion,
                    **request.context,
                },
            )
            step3 = ReasoningStep(
                step_number=3,
                action="model_assisted",
                input_summary=f"Provider: {self._provider.provider_name}",
                output_summary=model_conclusion,
                determinism_level=DeterminismLevel.MODEL_ASSISTED,
                confidence=ConfidenceScore(model_conf),
            )
            steps.append(step3)

            if model_conf > det_confidence:
                conclusion = model_conclusion
                confidence = model_conf
                determinism = DeterminismLevel.MODEL_ASSISTED
            else:
                conclusion = det_conclusion
                confidence = det_confidence

        result = ReasoningResult(
            request_id=request.id,
            tenant_id=request.tenant_id,
            status=ReasoningStatus.COMPLETED,
            mode=request.mode,
            scope=request.scope,
            conclusion=conclusion,
            confidence=ConfidenceScore(confidence),
            determinism_level=determinism,
            steps=steps,
            objects_consulted=list(set(all_consulted)),
            timestamp=datetime.now(UTC),
        )
        result.compute_hash()
        return result

    def _enforce_policy(
        self,
        request: ReasoningRequest,
        policy: ReasoningPolicy,
    ) -> None:
        if request.scope not in policy.allowed_scopes:
            raise ReasoningScopeViolation(
                f"Scope {request.scope.value} not allowed. "
                f"Allowed: {[s.value for s in policy.allowed_scopes]}"
            )
        if request.mode not in policy.allowed_modes:
            raise ReasoningPolicyViolation(
                f"Mode {request.mode.value} not allowed. "
                f"Allowed: {[m.value for m in policy.allowed_modes]}"
            )
        if request.plane and request.plane not in policy.allowed_planes:
            raise ReasoningScopeViolation(f"Plane {request.plane.value} not in allowed planes")

    def _gather_scoped_objects(
        self,
        request: ReasoningRequest,
        policy: ReasoningPolicy,
    ) -> list[ControlObject]:
        objects: list[ControlObject] = []

        if request.target_object_ids:
            for oid in request.target_object_ids:
                obj = self._graph.get_object(oid)
                if obj:
                    objects.append(obj)
        elif request.scope == ReasoningScope.SINGLE_OBJECT:
            return objects  # Caller must provide target IDs

        if request.scope == ReasoningScope.PLANE_LOCAL and request.plane:
            plane_objects = self._graph.list_objects(
                request.tenant_id, plane=request.plane, domain=request.domain
            )
            for obj in plane_objects:
                if obj.id not in {o.id for o in objects}:
                    objects.append(obj)

        if request.scope in (ReasoningScope.CROSS_PLANE, ReasoningScope.FULL_GRAPH):
            all_objects = self._graph.list_objects(request.tenant_id, domain=request.domain)
            for obj in all_objects:
                if obj.id not in {o.id for o in objects}:
                    objects.append(obj)

        return objects[: policy.max_objects]

    def _apply_deterministic_rules(
        self,
        request: ReasoningRequest,
        objects: list[ControlObject],
    ) -> tuple[str, float]:
        rule_name = request.context.get("rule_name", "")
        if rule_name:
            result, conf = self._deterministic_provider.reason(
                request.question,
                {"rule_name": rule_name, "objects": objects, **request.context},
            )
            if conf > 0.0:
                return result, conf

        # Default deterministic analysis: summarise object states
        if not objects:
            return "No objects in scope", 0.5

        state_counts: dict[str, int] = {}
        for obj in objects:
            state_counts[obj.state.value] = state_counts.get(obj.state.value, 0) + 1

        summary_parts = [f"{v} {k}" for k, v in sorted(state_counts.items())]
        summary = f"Objects in scope: {', '.join(summary_parts)}"
        return summary, 0.8
