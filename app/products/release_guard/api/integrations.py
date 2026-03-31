"""Integration management endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from app.products.release_guard.domain.enums import IntegrationProvider
from app.products.release_guard.services.integration_service import integration_service

router = APIRouter(prefix="/integrations")


class ConnectBody(BaseModel):
    workspace_id: str
    config: dict = {}


@router.get("/{workspace_id}")
def list_integrations(workspace_id: str) -> dict:
    integrations = integration_service.list_for_workspace(workspace_id)
    return {"integrations": [asdict(i) for i in integrations]}


@router.post("/{provider}/connect")
def connect(provider: IntegrationProvider, body: ConnectBody) -> dict:
    integration = integration_service.connect(body.workspace_id, provider, body.config, "api-user")
    return asdict(integration)


@router.post("/{provider}/test")
def test(provider: IntegrationProvider, workspace_id: str) -> dict:
    return integration_service.test(workspace_id, provider)


@router.delete("/{provider}")
def disconnect(provider: IntegrationProvider, workspace_id: str) -> dict:
    integration_service.disconnect(workspace_id, provider)
    return {"disconnected": True, "provider": provider.value}
