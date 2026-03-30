"""Tests for bounded reasoning engine — scope enforcement, deterministic-first."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.control_object import ControlObjectCreate
from app.core.errors import ReasoningPolicyViolation, ReasoningScopeViolation
from app.core.graph.service import GraphService
from app.core.reasoning.engine import BoundedReasoningEngine
from app.core.reasoning.provider import StubReasoningProvider
from app.core.reasoning.types import (
    ReasoningMode,
    ReasoningPolicy,
    ReasoningRequest,
    ReasoningStatus,
)
from app.core.types import (
    ControlObjectType,
    DeterminismLevel,
    PlaneType,
    ReasoningScope,
)

TENANT = uuid.uuid4()


def _make_graph_with_objects():
    svc = GraphService()
    obj1 = svc.create_object(
        TENANT,
        ControlObjectCreate(
            object_type=ControlObjectType.OBLIGATION,
            plane=PlaneType.COMMERCIAL,
            domain="test",
            label="Obligation A",
        ),
    )
    obj2 = svc.create_object(
        TENANT,
        ControlObjectCreate(
            object_type=ControlObjectType.WORK_ORDER,
            plane=PlaneType.FIELD,
            domain="test",
            label="Work Order B",
        ),
    )
    return svc, obj1, obj2


class TestReasoningScopeEnforcement:
    def test_disallowed_scope_raises(self):
        svc, obj1, _ = _make_graph_with_objects()
        engine = BoundedReasoningEngine(svc)
        request = ReasoningRequest(
            tenant_id=TENANT,
            scope=ReasoningScope.FULL_GRAPH,
            target_object_ids=[obj1.id],
            policy=ReasoningPolicy(
                allowed_scopes=[ReasoningScope.SINGLE_OBJECT],
            ),
        )
        with pytest.raises(ReasoningScopeViolation, match="full_graph"):
            engine.reason(request)

    def test_disallowed_mode_raises(self):
        svc, obj1, _ = _make_graph_with_objects()
        engine = BoundedReasoningEngine(svc)
        request = ReasoningRequest(
            tenant_id=TENANT,
            scope=ReasoningScope.SINGLE_OBJECT,
            mode=ReasoningMode.MODEL_ASSISTED,
            target_object_ids=[obj1.id],
            policy=ReasoningPolicy(
                allowed_scopes=[ReasoningScope.SINGLE_OBJECT],
                allowed_modes=[ReasoningMode.DETERMINISTIC_RULES],
            ),
        )
        with pytest.raises(ReasoningPolicyViolation, match="model_assisted"):
            engine.reason(request)

    def test_disallowed_plane_raises(self):
        svc, obj1, _ = _make_graph_with_objects()
        engine = BoundedReasoningEngine(svc)
        request = ReasoningRequest(
            tenant_id=TENANT,
            scope=ReasoningScope.SINGLE_OBJECT,
            plane=PlaneType.SERVICE,
            target_object_ids=[obj1.id],
            policy=ReasoningPolicy(
                allowed_scopes=[ReasoningScope.SINGLE_OBJECT],
                allowed_planes=[PlaneType.COMMERCIAL],
            ),
        )
        with pytest.raises(ReasoningScopeViolation, match="service"):
            engine.reason(request)


class TestDeterministicReasoning:
    def test_deterministic_rules_mode(self):
        svc, obj1, _ = _make_graph_with_objects()
        engine = BoundedReasoningEngine(svc)
        request = ReasoningRequest(
            tenant_id=TENANT,
            scope=ReasoningScope.SINGLE_OBJECT,
            mode=ReasoningMode.DETERMINISTIC_RULES,
            target_object_ids=[obj1.id],
            policy=ReasoningPolicy(
                allowed_scopes=[ReasoningScope.SINGLE_OBJECT],
            ),
        )
        result = engine.reason(request)
        assert result.status == ReasoningStatus.COMPLETED
        assert result.determinism_level == DeterminismLevel.DETERMINISTIC
        assert len(result.steps) >= 2

    def test_registered_deterministic_rule(self):
        svc, obj1, _ = _make_graph_with_objects()
        engine = BoundedReasoningEngine(svc)
        engine.register_deterministic_rule(
            "check_obligation",
            lambda ctx: "Obligation is valid",
        )
        request = ReasoningRequest(
            tenant_id=TENANT,
            scope=ReasoningScope.SINGLE_OBJECT,
            target_object_ids=[obj1.id],
            context={"rule_name": "check_obligation"},
            policy=ReasoningPolicy(
                allowed_scopes=[ReasoningScope.SINGLE_OBJECT],
            ),
        )
        result = engine.reason(request)
        assert "valid" in result.conclusion.lower() or "Obligation" in result.conclusion

    def test_decision_hash_is_stable(self):
        svc, obj1, _ = _make_graph_with_objects()
        engine = BoundedReasoningEngine(svc)
        request = ReasoningRequest(
            tenant_id=TENANT,
            scope=ReasoningScope.SINGLE_OBJECT,
            target_object_ids=[obj1.id],
            policy=ReasoningPolicy(
                allowed_scopes=[ReasoningScope.SINGLE_OBJECT],
            ),
        )
        r1 = engine.reason(request)
        r2 = engine.reason(request)
        assert r1.decision_hash == r2.decision_hash


class TestHybridReasoning:
    def test_hybrid_falls_back_to_deterministic(self):
        svc, obj1, _ = _make_graph_with_objects()
        engine = BoundedReasoningEngine(svc, provider=StubReasoningProvider())
        request = ReasoningRequest(
            tenant_id=TENANT,
            scope=ReasoningScope.SINGLE_OBJECT,
            mode=ReasoningMode.HYBRID,
            target_object_ids=[obj1.id],
            policy=ReasoningPolicy(
                allowed_scopes=[ReasoningScope.SINGLE_OBJECT],
                allowed_modes=[
                    ReasoningMode.DETERMINISTIC_RULES,
                    ReasoningMode.MODEL_ASSISTED,
                    ReasoningMode.HYBRID,
                ],
                max_confidence_for_auto=0.95,
            ),
        )
        result = engine.reason(request)
        assert result.status == ReasoningStatus.COMPLETED
        # Should have 3 steps: gather, deterministic, model
        assert len(result.steps) == 3

    def test_cross_plane_reasoning(self):
        svc, obj1, obj2 = _make_graph_with_objects()
        engine = BoundedReasoningEngine(svc)
        request = ReasoningRequest(
            tenant_id=TENANT,
            scope=ReasoningScope.CROSS_PLANE,
            target_object_ids=[obj1.id, obj2.id],
            domain="test",
            policy=ReasoningPolicy(
                allowed_scopes=[ReasoningScope.CROSS_PLANE],
            ),
        )
        result = engine.reason(request)
        assert result.status == ReasoningStatus.COMPLETED
        assert len(result.objects_consulted) >= 2
