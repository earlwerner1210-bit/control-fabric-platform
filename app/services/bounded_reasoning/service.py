"""Bounded Reasoning Service — graph-slice-isolated inference contexts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.bounded_reasoning import (
    BoundedContext,
    BoundedContextEvidence,
    BoundedContextObject,
    BoundedContextRequest,
    BoundedReasoningRequest,
    BoundedReasoningResponse,
    ReasoningScope,
    ReasoningStatus,
    ReasoningSummary,
)
from app.schemas.control_graph import GraphSliceRequest
from app.services.control_graph.service import ControlGraphService
from app.services.evidence import EvidenceService


class BoundedReasoningService:
    """Builds bounded contexts from graph slices and evidence, runs inference."""

    def __init__(
        self,
        graph_service: ControlGraphService,
        evidence_service: EvidenceService | None = None,
        inference_fn: Any = None,
    ) -> None:
        self._graph = graph_service
        self._evidence = evidence_service
        self._inference_fn = inference_fn
        self._sessions: dict[uuid.UUID, dict[str, Any]] = {}

    def build_context(
        self,
        tenant_id: uuid.UUID,
        request: BoundedContextRequest,
    ) -> BoundedContext:
        root_ids = list(request.root_object_ids)

        slice_result = self._graph.slice_graph(
            tenant_id,
            GraphSliceRequest(
                root_ids=root_ids,
                max_depth=request.max_depth,
                policy=request.slice_policy,
                allowed_planes=request.allowed_planes,
                allowed_link_types=[],
                max_nodes=request.max_context_objects,
            ),
        )

        context_objects = [
            BoundedContextObject(
                object_id=n.object_id,
                control_type=n.control_type,
                plane=n.plane.value if hasattr(n.plane, "value") else str(n.plane),
                domain=n.domain,
                label=n.label,
                confidence=n.confidence,
                depth=n.depth,
            )
            for n in slice_result.nodes
        ]

        evidence_items: list[BoundedContextEvidence] = []
        if request.include_evidence and self._evidence and request.pilot_case_id:
            bundle = self._evidence.get_bundle(request.pilot_case_id)
            if bundle:
                for item in bundle.items:
                    evidence_items.append(
                        BoundedContextEvidence(
                            evidence_type=item.evidence_type,
                            source_id=item.source_id,
                            source_label=item.source_label
                            if hasattr(item, "source_label")
                            else None,
                            confidence=item.confidence if hasattr(item, "confidence") else None,
                        )
                    )

        planes = list({o.plane for o in context_objects})
        domains = list({o.domain for o in context_objects})

        return BoundedContext(
            context_id=uuid.uuid4(),
            objects=context_objects,
            evidence=evidence_items,
            total_objects=len(context_objects),
            total_evidence=len(evidence_items),
            scope=request.scope,
            depth_reached=slice_result.depth_reached,
            planes_included=planes,
            domains_included=domains,
        )

    def reason(
        self,
        tenant_id: uuid.UUID,
        request: BoundedReasoningRequest,
    ) -> BoundedReasoningResponse:
        session_id = uuid.uuid4()
        start = datetime.now(UTC)

        context = self.build_context(tenant_id, request.context)

        answer = None
        confidence = None
        reasoning_trace: list[str] = []
        input_tokens = None
        output_tokens = None
        status = ReasoningStatus.COMPLETED

        if self._inference_fn:
            try:
                result = self._inference_fn(
                    context=context,
                    question=request.question,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    model_id=request.model_id,
                )
                answer = result.get("answer")
                confidence = result.get("confidence")
                reasoning_trace = result.get("reasoning_trace", [])
                input_tokens = result.get("input_tokens")
                output_tokens = result.get("output_tokens")
            except Exception as e:
                status = ReasoningStatus.FAILED
                reasoning_trace = [f"Inference error: {e!s}"]
        else:
            reasoning_trace = [
                f"Context built with {context.total_objects} objects, "
                f"{context.total_evidence} evidence items",
                f"Question: {request.question}",
                "No inference function configured — returning context only",
            ]
            answer = (
                f"Bounded context assembled: {context.total_objects} objects across "
                f"{', '.join(context.planes_included)} planes"
            )
            confidence = 0.0

        end = datetime.now(UTC)
        duration_ms = (end - start).total_seconds() * 1000

        response = BoundedReasoningResponse(
            id=session_id,
            pilot_case_id=request.context.pilot_case_id,
            status=status,
            scope=request.context.scope,
            context=context,
            question=request.question,
            answer=answer,
            confidence=confidence,
            reasoning_trace=reasoning_trace,
            objects_consulted=context.total_objects,
            evidence_consulted=context.total_evidence,
            model_id=request.model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            metadata={},
            created_at=start,
        )

        self._sessions[session_id] = {
            "response": response,
            "tenant_id": tenant_id,
        }

        return response

    def get_session(self, session_id: uuid.UUID) -> BoundedReasoningResponse | None:
        entry = self._sessions.get(session_id)
        return entry["response"] if entry else None

    def get_summary(self, tenant_id: uuid.UUID) -> ReasoningSummary:
        sessions = [s["response"] for s in self._sessions.values() if s["tenant_id"] == tenant_id]

        completed = sum(1 for s in sessions if s.status == ReasoningStatus.COMPLETED)
        failed = sum(1 for s in sessions if s.status == ReasoningStatus.FAILED)
        by_scope: dict[str, int] = {}
        total_objects = 0
        total_confidence = 0.0
        total_duration = 0.0
        conf_count = 0

        for s in sessions:
            scope = s.scope.value if hasattr(s.scope, "value") else str(s.scope)
            by_scope[scope] = by_scope.get(scope, 0) + 1
            total_objects += s.objects_consulted
            if s.confidence is not None:
                total_confidence += s.confidence
                conf_count += 1
            if s.duration_ms is not None:
                total_duration += s.duration_ms

        n = len(sessions)
        return ReasoningSummary(
            total_sessions=n,
            completed=completed,
            failed=failed,
            avg_objects_consulted=total_objects / n if n > 0 else 0.0,
            avg_confidence=total_confidence / conf_count if conf_count > 0 else 0.0,
            avg_duration_ms=total_duration / n if n > 0 else 0.0,
            by_scope=by_scope,
        )
