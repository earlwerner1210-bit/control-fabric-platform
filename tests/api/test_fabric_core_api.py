"""Tests for fabric core API routes."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.fabric_core import router, set_service
from app.core.control_object import ControlObjectCreate
from app.core.domain_integration import register_all_domain_packs
from app.core.fabric_service import ControlFabricService
from app.core.registry import FabricRegistry
from app.core.types import (
    ControlObjectType,
    EvidenceRef,
    PlaneType,
)

TENANT = uuid.uuid4()


@pytest.fixture
def client():
    registry = FabricRegistry()
    register_all_domain_packs(registry)
    svc = ControlFabricService(registry=registry)
    set_service(svc)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestObjectEndpoints:
    def test_create_object(self, client):
        resp = client.post(
            "/fabric/objects",
            json={
                "tenant_id": str(TENANT),
                "object_type": "obligation",
                "plane": "commercial",
                "domain": "test",
                "label": "Test Obligation",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "active"
        assert "id" in data

    def test_get_object(self, client):
        resp = client.post(
            "/fabric/objects",
            json={
                "tenant_id": str(TENANT),
                "object_type": "obligation",
                "plane": "commercial",
                "domain": "test",
                "label": "Fetch Me",
            },
        )
        oid = resp.json()["id"]
        resp2 = client.get(f"/fabric/objects/{oid}")
        assert resp2.status_code == 200
        assert resp2.json()["label"] == "Fetch Me"

    def test_get_missing_object(self, client):
        resp = client.get(f"/fabric/objects/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_list_objects(self, client):
        client.post(
            "/fabric/objects",
            json={
                "tenant_id": str(TENANT),
                "object_type": "obligation",
                "plane": "commercial",
                "domain": "test",
                "label": "Listed",
            },
        )
        resp = client.get(f"/fabric/objects?tenant_id={TENANT}")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_freeze_object(self, client):
        resp = client.post(
            "/fabric/objects",
            json={
                "tenant_id": str(TENANT),
                "object_type": "obligation",
                "plane": "commercial",
                "domain": "test",
                "label": "Freeze Me",
            },
        )
        oid = resp.json()["id"]
        resp2 = client.post(f"/fabric/objects/{oid}/freeze")
        assert resp2.status_code == 200
        assert resp2.json()["state"] == "frozen"


class TestLinkEndpoints:
    def test_create_link(self, client):
        r1 = client.post(
            "/fabric/objects",
            json={
                "tenant_id": str(TENANT),
                "object_type": "obligation",
                "plane": "commercial",
                "domain": "test",
                "label": "Source",
            },
        )
        r2 = client.post(
            "/fabric/objects",
            json={
                "tenant_id": str(TENANT),
                "object_type": "work_order",
                "plane": "field",
                "domain": "test",
                "label": "Target",
            },
        )
        resp = client.post(
            "/fabric/links",
            json={
                "tenant_id": str(TENANT),
                "source_id": r1.json()["id"],
                "target_id": r2.json()["id"],
                "link_type": "fulfills",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["is_cross_plane"] is True

    def test_get_links(self, client):
        r1 = client.post(
            "/fabric/objects",
            json={
                "tenant_id": str(TENANT),
                "object_type": "obligation",
                "plane": "commercial",
                "domain": "test",
                "label": "A",
            },
        )
        r2 = client.post(
            "/fabric/objects",
            json={
                "tenant_id": str(TENANT),
                "object_type": "obligation",
                "plane": "commercial",
                "domain": "test",
                "label": "B",
            },
        )
        client.post(
            "/fabric/links",
            json={
                "tenant_id": str(TENANT),
                "source_id": r1.json()["id"],
                "target_id": r2.json()["id"],
                "link_type": "derives_from",
            },
        )
        resp = client.get(f"/fabric/objects/{r1.json()['id']}/links")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestReconciliationEndpoint:
    def test_reconcile(self, client):
        client.post(
            "/fabric/objects",
            json={
                "tenant_id": str(TENANT),
                "object_type": "obligation",
                "plane": "commercial",
                "domain": "recon",
                "label": "Comm",
            },
        )
        client.post(
            "/fabric/objects",
            json={
                "tenant_id": str(TENANT),
                "object_type": "work_order",
                "plane": "field",
                "domain": "recon",
                "label": "Field",
            },
        )
        resp = client.post(
            "/fabric/reconcile",
            json={
                "tenant_id": str(TENANT),
                "source_plane": "commercial",
                "target_plane": "field",
                "domain": "recon",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "decision_hash" in data


class TestConsistencyEndpoint:
    def test_consistency_check(self, client):
        client.post(
            "/fabric/objects",
            json={
                "tenant_id": str(TENANT),
                "object_type": "obligation",
                "plane": "commercial",
                "domain": "test",
                "label": "Check Me",
            },
        )
        resp = client.get(f"/fabric/consistency/{TENANT}")
        assert resp.status_code == 200
        assert "is_consistent" in resp.json()
