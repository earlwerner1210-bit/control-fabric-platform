"""Tests for the Control Graph Service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.control_fabric import (
    ControlLinkType,
    ControlPlane,
    FabricLinkCreate,
    FabricObjectCreate,
)
from app.schemas.control_graph import (
    GraphSlicePolicy,
    GraphSliceRequest,
    GraphSnapshotCreate,
    GraphSnapshotStatus,
)
from app.services.control_fabric.service import ControlFabricService
from app.services.control_graph.service import ControlGraphService

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _setup():
    fabric = ControlFabricService()
    graph = ControlGraphService(fabric)
    return fabric, graph


def _add_obj(fabric, label, plane=ControlPlane.COMMERCIAL, domain="contract_margin"):
    return fabric.register_object(
        TENANT,
        FabricObjectCreate(control_type="obligation", plane=plane, domain=domain, label=label),
    )


def _link(fabric, src, tgt, lt=ControlLinkType.DEPENDS_ON):
    return fabric.link_objects(
        TENANT,
        FabricLinkCreate(source_id=src.id, target_id=tgt.id, link_type=lt),
    )


class TestSnapshot:
    def test_create_snapshot(self):
        fabric, graph = _setup()
        _add_obj(fabric, "A")
        _add_obj(fabric, "B")

        snap = graph.create_snapshot(GraphSnapshotCreate(tenant_id=TENANT, label="test-snap"))
        assert snap.status == GraphSnapshotStatus.READY
        assert snap.node_count == 2
        assert snap.label == "test-snap"

    def test_get_snapshot(self):
        fabric, graph = _setup()
        _add_obj(fabric, "A")
        snap = graph.create_snapshot(GraphSnapshotCreate(tenant_id=TENANT))
        fetched = graph.get_snapshot(snap.id)
        assert fetched is not None
        assert fetched.id == snap.id

    def test_list_snapshots(self):
        fabric, graph = _setup()
        graph.create_snapshot(GraphSnapshotCreate(tenant_id=TENANT, label="s1"))
        graph.create_snapshot(GraphSnapshotCreate(tenant_id=TENANT, label="s2"))
        snaps = graph.list_snapshots(TENANT)
        assert len(snaps) == 2

    def test_snapshot_with_edges(self):
        fabric, graph = _setup()
        a = _add_obj(fabric, "A")
        b = _add_obj(fabric, "B")
        _link(fabric, a, b)

        snap = graph.create_snapshot(GraphSnapshotCreate(tenant_id=TENANT))
        assert snap.node_count == 2
        assert snap.edge_count == 1


class TestSlice:
    def test_basic_slice(self):
        fabric, graph = _setup()
        a = _add_obj(fabric, "A")
        b = _add_obj(fabric, "B")
        c = _add_obj(fabric, "C")
        _link(fabric, a, b)
        _link(fabric, b, c)

        result = graph.slice_graph(
            TENANT,
            GraphSliceRequest(root_ids=[a.id], max_depth=3),
        )
        assert len(result.nodes) == 3
        assert len(result.edges) >= 2

    def test_slice_depth_limit(self):
        fabric, graph = _setup()
        a = _add_obj(fabric, "A")
        b = _add_obj(fabric, "B")
        c = _add_obj(fabric, "C")
        _link(fabric, a, b)
        _link(fabric, b, c)

        result = graph.slice_graph(
            TENANT,
            GraphSliceRequest(root_ids=[a.id], max_depth=1),
        )
        assert len(result.nodes) == 2  # A and B only

    def test_slice_plane_filter(self):
        fabric, graph = _setup()
        a = _add_obj(fabric, "A", plane=ControlPlane.COMMERCIAL)
        b = _add_obj(fabric, "B", plane=ControlPlane.FIELD)
        c = _add_obj(fabric, "C", plane=ControlPlane.COMMERCIAL)
        _link(fabric, a, b)
        _link(fabric, a, c)

        result = graph.slice_graph(
            TENANT,
            GraphSliceRequest(
                root_ids=[a.id],
                max_depth=3,
                allowed_planes=[ControlPlane.COMMERCIAL],
            ),
        )
        assert all(n.plane == ControlPlane.COMMERCIAL for n in result.nodes)

    def test_slice_truncation(self):
        fabric, graph = _setup()
        root = _add_obj(fabric, "Root")
        for i in range(10):
            child = _add_obj(fabric, f"Child{i}")
            _link(fabric, root, child)

        result = graph.slice_graph(
            TENANT,
            GraphSliceRequest(root_ids=[root.id], max_depth=1, max_nodes=5),
        )
        assert result.truncated or len(result.nodes) <= 5

    def test_get_slice(self):
        fabric, graph = _setup()
        a = _add_obj(fabric, "A")
        result = graph.slice_graph(
            TENANT,
            GraphSliceRequest(root_ids=[a.id], max_depth=1),
        )
        fetched = graph.get_slice(result.slice_id)
        assert fetched is not None
        assert fetched.slice_id == result.slice_id


class TestTraversal:
    def test_find_path(self):
        fabric, graph = _setup()
        a = _add_obj(fabric, "A")
        b = _add_obj(fabric, "B")
        c = _add_obj(fabric, "C")
        _link(fabric, a, b)
        _link(fabric, b, c)

        path = graph.find_path(TENANT, a.id, c.id)
        assert path is not None
        assert path.path == [a.id, b.id, c.id]
        assert len(path.link_types_traversed) == 2

    def test_no_path(self):
        fabric, graph = _setup()
        a = _add_obj(fabric, "A")
        b = _add_obj(fabric, "B")
        # No link between them
        path = graph.find_path(TENANT, a.id, b.id)
        assert path is None

    def test_find_path_missing_node(self):
        fabric, graph = _setup()
        result = graph.find_path(TENANT, uuid.uuid4(), uuid.uuid4())
        assert result is None


class TestAnalytics:
    def test_analytics(self):
        fabric, graph = _setup()
        a = _add_obj(fabric, "A", plane=ControlPlane.COMMERCIAL)
        b = _add_obj(fabric, "B", plane=ControlPlane.FIELD)
        c = _add_obj(fabric, "C", plane=ControlPlane.COMMERCIAL)
        _link(fabric, a, b)
        _link(fabric, a, c)
        _link(fabric, b, c, ControlLinkType.CONTRADICTS)

        analytics = graph.get_analytics(TENANT)
        assert analytics.node_count == 3
        assert analytics.edge_count == 3
        assert analytics.cross_plane_edges >= 1
        assert analytics.contradiction_count == 1
        assert analytics.by_plane["commercial"] == 2
