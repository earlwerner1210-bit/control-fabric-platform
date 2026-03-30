from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.graph.store import ControlGraphStore
from app.core.ingress.domain_types import ArtefactFormat, RawArtefact
from app.core.ingress.pipeline import IngestPipeline
from app.core.registry.object_registry import ObjectRegistry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingress", tags=["ingress"])

_registry = ObjectRegistry()
_graph = ControlGraphStore()
_pipeline = IngestPipeline(registry=_registry, graph=_graph)


class IngestRequest(BaseModel):
    source_system: str
    format: ArtefactFormat = ArtefactFormat.JSON
    content: str
    operational_plane: str
    submitted_by: str = "api-user"
    metadata: dict = Field(default_factory=dict)


class IngestResponse(BaseModel):
    artefact_id: str
    success: bool
    object_count: int
    object_ids: list[str]
    errors: list[str]


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest a raw artefact into the control fabric",
)
def ingest(request: IngestRequest) -> IngestResponse:
    """
    Patent Claim (Theme 1): Converts raw enterprise artefacts into
    typed control objects with cryptographic provenance.
    """
    artefact = RawArtefact(
        source_system=request.source_system,
        format=request.format,
        raw_content=request.content,
        submitted_by=request.submitted_by,
        metadata=request.metadata,
    )
    result = _pipeline.ingest(artefact, request.operational_plane, request.submitted_by)
    return IngestResponse(
        artefact_id=result.artefact_id,
        success=result.success,
        object_count=result.object_count,
        object_ids=[obj.object_id for obj in result.ingested_objects],
        errors=result.errors,
    )


@router.get("/objects/{object_id}", summary="Retrieve a control object by ID")
def get_object(object_id: str) -> dict:
    obj = _registry.get(object_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object {object_id} not found",
        )
    return obj.model_dump(mode="json")


@router.get(
    "/objects/{object_id}/history",
    summary="Retrieve version history for an object",
)
def get_history(object_id: str) -> dict:
    """Patent Claim (Theme 1): Immutable version history from moment of ingestion."""
    history = _registry.get_version_history(object_id)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No history for {object_id}",
        )
    return {
        "object_id": object_id,
        "version_count": len(history),
        "history": [r.model_dump(mode="json") for r in history],
    }


@router.get("/stats", summary="Registry and graph statistics")
def get_stats() -> dict:
    return {
        "registry_object_count": _registry.object_count,
        "graph_node_count": _graph.node_count,
        "graph_edge_count": _graph.edge_count,
        "active_objects": len(_registry.get_active()),
    }
