"""Tests for the Bounded Reasoning Service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.bounded_reasoning import (
    BoundedContextRequest,
    BoundedReasoningRequest,
    ReasoningScope,
    ReasoningStatus,
)
from app.schemas.control_fabric import (
    ControlLinkType,
    ControlPlane,
    FabricLinkCreate,
    FabricObjectCreate,
)
from app.schemas.control_graph import GraphSlicePolicy
from app.services.bounded_reasoning.service import BoundedReasoningService
from app.services.control_fabric.service import ControlFabricService
from app.services.control_graph.service import ControlGraphService

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
CASE = uuid.UUID("00000000-0000-0000-0000-000000000099")


def _setup():
    fabric = ControlFabricService()
    graph = ControlGraphService(fabric)
    reasoning = BoundedReasoningService(graph)
    return fabric, graph, reasoning


def _add_obj(fabric, label, plane=ControlPlane.COMMERCIAL, domain="contract_margin"):
    return fabric.register_object(
        TENANT,
        FabricObjectCreate(
            control_type="obligation",
            plane=plane,
            domain=domain,
            label=label,
            confidence=0.9,
        ),
    )


class TestContextBuilding:
    def test_build_context(self):
        fabric, graph, reasoning = _setup()
        a = _add_obj(fabric, "MSA Clause 1")
        b = _add_obj(fabric, "Billing Event")
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=a.id,
                target_id=b.id,
                link_type=ControlLinkType.TRIGGERS,
            ),
        )

        ctx = reasoning.build_context(
            TENANT,
            BoundedContextRequest(
                root_object_ids=[a.id],
                scope=ReasoningScope.CASE_BOUNDED,
                max_depth=2,
            ),
        )
        assert ctx.total_objects == 2
        assert len(ctx.objects) == 2
        assert ctx.scope == ReasoningScope.CASE_BOUNDED

    def test_empty_context(self):
        fabric, graph, reasoning = _setup()
        ctx = reasoning.build_context(
            TENANT,
            BoundedContextRequest(
                root_object_ids=[uuid.uuid4()],
                scope=ReasoningScope.CASE_BOUNDED,
            ),
        )
        assert ctx.total_objects == 0


class TestReasoning:
    def test_reason_without_inference(self):
        fabric, graph, reasoning = _setup()
        obj = _add_obj(fabric, "Test Object")

        result = reasoning.reason(
            TENANT,
            BoundedReasoningRequest(
                context=BoundedContextRequest(
                    root_object_ids=[obj.id],
                    scope=ReasoningScope.CASE_BOUNDED,
                ),
                question="Is this billable?",
            ),
        )
        assert result.status == ReasoningStatus.COMPLETED
        assert result.answer is not None
        assert result.objects_consulted == 1
        assert result.question == "Is this billable?"

    def test_reason_with_inference(self):
        fabric, graph, _ = _setup()
        obj = _add_obj(fabric, "Test Object")

        def mock_inference(**kwargs):
            return {
                "answer": "Yes, billable",
                "confidence": 0.92,
                "reasoning_trace": ["Step 1", "Step 2"],
                "input_tokens": 100,
                "output_tokens": 50,
            }

        reasoning = BoundedReasoningService(graph, inference_fn=mock_inference)
        result = reasoning.reason(
            TENANT,
            BoundedReasoningRequest(
                context=BoundedContextRequest(
                    root_object_ids=[obj.id],
                    scope=ReasoningScope.CASE_BOUNDED,
                ),
                question="Is this billable?",
                model_id="claude-3-opus",
            ),
        )
        assert result.answer == "Yes, billable"
        assert result.confidence == 0.92
        assert len(result.reasoning_trace) == 2

    def test_reason_with_failed_inference(self):
        fabric, graph, _ = _setup()
        obj = _add_obj(fabric, "Test Object")

        def failing_inference(**kwargs):
            raise RuntimeError("API timeout")

        reasoning = BoundedReasoningService(graph, inference_fn=failing_inference)
        result = reasoning.reason(
            TENANT,
            BoundedReasoningRequest(
                context=BoundedContextRequest(
                    root_object_ids=[obj.id],
                    scope=ReasoningScope.CASE_BOUNDED,
                ),
                question="Is this billable?",
            ),
        )
        assert result.status == ReasoningStatus.FAILED

    def test_get_session(self):
        fabric, graph, reasoning = _setup()
        obj = _add_obj(fabric, "Test Object")

        result = reasoning.reason(
            TENANT,
            BoundedReasoningRequest(
                context=BoundedContextRequest(
                    root_object_ids=[obj.id],
                    scope=ReasoningScope.CASE_BOUNDED,
                ),
                question="Test",
            ),
        )
        fetched = reasoning.get_session(result.id)
        assert fetched is not None
        assert fetched.id == result.id


class TestCrossPlaneReasoning:
    def test_multi_plane_context(self):
        fabric, graph, reasoning = _setup()
        a = _add_obj(fabric, "Commercial Obj", plane=ControlPlane.COMMERCIAL)
        b = _add_obj(fabric, "Field Obj", plane=ControlPlane.FIELD)
        c = _add_obj(fabric, "Service Obj", plane=ControlPlane.SERVICE)
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(source_id=a.id, target_id=b.id, link_type=ControlLinkType.DEPENDS_ON),
        )
        fabric.link_objects(
            TENANT,
            FabricLinkCreate(source_id=b.id, target_id=c.id, link_type=ControlLinkType.TRIGGERS),
        )

        result = reasoning.reason(
            TENANT,
            BoundedReasoningRequest(
                context=BoundedContextRequest(
                    root_object_ids=[a.id],
                    scope=ReasoningScope.FULL_GRAPH,
                    max_depth=3,
                ),
                question="What is the cross-plane impact?",
            ),
        )
        assert result.objects_consulted == 3
        assert len(result.context.planes_included) >= 2


class TestSummary:
    def test_summary(self):
        fabric, graph, reasoning = _setup()
        obj = _add_obj(fabric, "Test")

        for _ in range(3):
            reasoning.reason(
                TENANT,
                BoundedReasoningRequest(
                    context=BoundedContextRequest(
                        root_object_ids=[obj.id],
                        scope=ReasoningScope.CASE_BOUNDED,
                    ),
                    question="Test",
                ),
            )

        summary = reasoning.get_summary(TENANT)
        assert summary.total_sessions == 3
        assert summary.completed == 3
        assert summary.failed == 0
