"""Connector management API — register, test, fetch, and monitor evidence sources."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.connectors.framework import ConnectorRegistry, SimulatedCICDConnector
from app.core.graph.store import ControlGraphStore
from app.core.ingress.pipeline import IngestPipeline
from app.core.registry.object_registry import ObjectRegistry

router = APIRouter(prefix="/connectors", tags=["connectors"])
_registry = ConnectorRegistry()
_obj_registry = ObjectRegistry()
_graph = ControlGraphStore()
_pipeline = IngestPipeline(registry=_obj_registry, graph=_graph)


class RegisterConnectorBody(BaseModel):
    connector_type: str
    connector_id: str
    config: dict


@router.post("/register")
def register_connector(body: RegisterConnectorBody) -> dict:
    """Register a new evidence source connector."""
    try:
        connector = _build_connector(body.connector_type, body.connector_id, body.config)
        _registry.register(connector)
        return {
            "registered": True,
            "connector_id": body.connector_id,
            "connector_type": body.connector_type,
            "source_system": connector.source_system,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/")
def list_connectors() -> dict:
    return {"count": _registry.connector_count, "health": _registry.health_status()}


@router.post("/{connector_id}/fetch")
def fetch_connector(connector_id: str, ingest: bool = False) -> dict:
    """Fetch evidence from a connector. Optionally ingest into the platform."""
    connector = _registry.get(connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector {connector_id} not found")
    result = connector.fetch()
    if ingest and result.success:
        ingest_results = _pipeline.ingest_batch(result.artefacts, "operations")
        return {
            "connector_id": connector_id,
            "fetched": result.artefact_count,
            "errors": result.errors,
            "ingested": sum(r.object_count for r in ingest_results),
        }
    return {
        "connector_id": connector_id,
        "fetched": result.artefact_count,
        "success": result.success,
        "errors": result.errors,
    }


@router.post("/{connector_id}/test")
def test_connector(connector_id: str) -> dict:
    """Test connector health without ingesting."""
    connector = _registry.get(connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector {connector_id} not found")
    result = connector.fetch()
    return {
        "connector_id": connector_id,
        "health": connector.health,
        "reachable": result.success,
        "sample_count": result.artefact_count,
        "errors": result.errors,
    }


@router.post("/fetch-all")
def fetch_all(ingest: bool = False) -> dict:
    """Fetch from all registered connectors."""
    results = _registry.fetch_all()
    total_artefacts = sum(r.artefact_count for r in results.values())
    ingested = 0
    if ingest:
        for result in results.values():
            if result.success:
                ir = _pipeline.ingest_batch(result.artefacts, "operations")
                ingested += sum(r.object_count for r in ir)
    return {
        "connectors_polled": len(results),
        "total_artefacts": total_artefacts,
        "ingested": ingested,
        "results": {
            cid: {
                "fetched": r.artefact_count,
                "success": r.success,
                "errors": r.errors,
            }
            for cid, r in results.items()
        },
    }


def _build_connector(connector_type: str, connector_id: str, config: dict):
    from app.core.connectors.azure_devops_connector import AzureDevOpsConnector
    from app.core.connectors.framework import ApiConnector
    from app.core.connectors.github_connector import GitHubActionsConnector
    from app.core.connectors.jira_connector import JiraConnector
    from app.core.connectors.servicenow_connector import ServiceNowConnector

    builders = {
        "github_actions": lambda: GitHubActionsConnector(
            connector_id=connector_id,
            owner=config["owner"],
            repo=config["repo"],
            token=config.get("token"),
            branch=config.get("branch", "main"),
        ),
        "jira": lambda: JiraConnector(
            connector_id=connector_id,
            base_url=config["base_url"],
            email=config.get("email"),
            api_token=config.get("api_token"),
            project_key=config.get("project_key", ""),
        ),
        "servicenow": lambda: ServiceNowConnector(
            connector_id=connector_id,
            instance=config["instance"],
            username=config.get("username"),
            password=config.get("password"),
        ),
        "azure_devops": lambda: AzureDevOpsConnector(
            connector_id=connector_id,
            organisation=config["organisation"],
            project=config["project"],
            pat=config.get("pat"),
        ),
        "api": lambda: ApiConnector(
            connector_id=connector_id,
            source_system=config.get("source_system", "api"),
            submitted_by="connector",
            endpoint_url=config["endpoint_url"],
            headers=config.get("headers", {}),
        ),
        "simulated_cicd": lambda: SimulatedCICDConnector(
            connector_id=connector_id,
        ),
    }
    builder = builders.get(connector_type)
    if not builder:
        raise ValueError(
            f"Unknown connector type: {connector_type}. Available: {list(builders.keys())}"
        )
    return builder()
