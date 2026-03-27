"""Top-level fabric service — unified entry point composing all core engines."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.action.engine import ActionEngine
from app.core.action.types import ActionMode, ActionProposal, ActionType
from app.core.graph.service import GraphService
from app.core.reasoning.engine import BoundedReasoningEngine
from app.core.reasoning.types import ReasoningRequest, ReasoningResult
from app.core.reconciliation.engine import ReconciliationEngine
from app.core.reconciliation.types import ReconciliationResult
from app.core.registry import FabricRegistry
from app.core.types import ControlObjectId, PlaneType
from app.core.validation.chain import ValidationChain
from app.core.validation.types import ValidationChainResult


class ControlFabricService:
    """Unified service composing graph, reconciliation, reasoning, validation, and action."""

    def __init__(
        self,
        registry: FabricRegistry | None = None,
        graph_service: GraphService | None = None,
    ) -> None:
        self.registry = registry or FabricRegistry()
        self.graph = graph_service or GraphService(registry=self.registry)
        self.validation = ValidationChain(self.graph)
        self.reconciliation = ReconciliationEngine(self.graph, self.registry)
        self.reasoning = BoundedReasoningEngine(self.graph)
        self.action = ActionEngine(self.graph, self.validation, self.registry)

    def reconcile_planes(
        self,
        tenant_id: uuid.UUID,
        source_plane: PlaneType,
        target_plane: PlaneType,
        domain: str,
    ) -> ReconciliationResult:
        return self.reconciliation.reconcile_cross_plane(
            tenant_id, source_plane, target_plane, domain
        )

    def reason(self, request: ReasoningRequest) -> ReasoningResult:
        return self.reasoning.reason(request)

    def validate_for_action(
        self,
        tenant_id: uuid.UUID,
        target_object_ids: list[ControlObjectId],
        action_type: str = "",
        context: dict[str, Any] | None = None,
    ) -> ValidationChainResult:
        objects = [
            obj for oid in target_object_ids if (obj := self.graph.get_object(oid)) is not None
        ]
        return self.validation.validate(tenant_id, objects, action_type, context)

    def propose_action(
        self,
        tenant_id: uuid.UUID,
        action_type: ActionType,
        target_object_ids: list[ControlObjectId],
        mode: ActionMode = ActionMode.APPROVAL_GATED,
        parameters: dict[str, Any] | None = None,
        description: str = "",
    ) -> ActionProposal:
        return self.action.propose_action(
            tenant_id=tenant_id,
            action_type=action_type,
            target_object_ids=target_object_ids,
            mode=mode,
            parameters=parameters,
            description=description,
        )
