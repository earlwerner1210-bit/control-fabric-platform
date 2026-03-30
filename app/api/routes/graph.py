from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.graph.domain_types import ControlEdge, RelationshipType
from app.core.graph.store import ControlGraphStore, GraphIntegrityError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/graph", tags=["graph"])

_graph = ControlGraphStore()


class AddEdgeRequest(BaseModel):
    source_object_id: str
    target_object_id: str
    relationship_type: RelationshipType
    asserted_by: str
    evidence_references: list[str] = []
    context: dict = {}


@router.post("/edges", summary="Add a typed relationship edge")
def add_edge(request: AddEdgeRequest) -> dict:
    """Patent Claim (Theme 2): Typed semantic relationship with enforcement weight."""
    try:
        edge = ControlEdge(
            source_object_id=request.source_object_id,
            target_object_id=request.target_object_id,
            relationship_type=request.relationship_type,
            asserted_by=request.asserted_by,
            evidence_references=request.evidence_references,
            context=request.context,
        )
        _graph.add_edge(edge)
        return {
            "edge_id": edge.edge_id,
            "enforcement_weight": edge.enforcement_weight,
            "edge_hash": edge.edge_hash,
        }
    except GraphIntegrityError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/traverse/{object_id}", summary="Traverse the control graph from an object")
def traverse(object_id: str, direction: str = "outbound", max_depth: int = 3) -> dict:
    """Patent Claim (Theme 2): BFS traversal for impact analysis."""
    try:
        result = _graph.traverse(object_id, direction=direction, max_depth=max_depth)
        return {
            "query_object_id": object_id,
            "discovered_objects": result.discovered_objects,
            "discovered_edges": result.discovered_edges,
            "depth_reached": result.traversal_depth_reached,
            "path_count": len(result.paths),
        }
    except GraphIntegrityError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/impact/{object_id}", summary="Analyse cascading impact of a change")
def impact_analysis(object_id: str, max_depth: int = 3) -> dict:
    """Patent Claim (Theme 2): Traces how a change cascades through governance topology."""
    try:
        return _graph.get_impact_analysis(object_id, max_depth=max_depth)
    except GraphIntegrityError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/path", summary="Find path between two control objects")
def find_path(source_id: str, target_id: str, max_depth: int = 5) -> dict:
    path = _graph.find_path_between(source_id, target_id, max_depth=max_depth)
    if not path:
        return {"found": False, "source_id": source_id, "target_id": target_id}
    return {
        "found": True,
        "depth": path.depth,
        "nodes": path.nodes,
        "edges": path.edges,
        "total_enforcement_weight": path.total_enforcement_weight,
    }


@router.get("/stats", summary="Graph statistics")
def get_stats() -> dict:
    return {
        "node_count": _graph.node_count,
        "edge_count": _graph.edge_count,
        "active_objects": len(_graph.get_active_objects()),
    }
