"""Tests for the Control Fabric Service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.control_fabric import (
    ControlLinkType,
    ControlObjectStatus,
    ControlPlane,
    FabricLinkCreate,
    FabricObjectCreate,
    FabricQueryFilter,
    FabricSliceRequest,
)
from app.services.control_fabric.service import ControlFabricService

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_obj(
    svc: ControlFabricService,
    label: str,
    plane: ControlPlane = ControlPlane.COMMERCIAL,
    domain: str = "contract_margin",
    control_type: str = "obligation",
    confidence: float = 1.0,
    tags: list[str] | None = None,
):
    return svc.register_object(
        TENANT,
        FabricObjectCreate(
            control_type=control_type,
            plane=plane,
            domain=domain,
            label=label,
            confidence=confidence,
            tags=tags or [],
        ),
    )


class TestRegistration:
    def test_register_and_get(self):
        svc = ControlFabricService()
        obj = _make_obj(svc, "MSA Obligation 1")
        assert obj.id is not None
        assert obj.label == "MSA Obligation 1"
        assert obj.plane == ControlPlane.COMMERCIAL
        assert obj.status == ControlObjectStatus.ACTIVE
        assert obj.version == 1

        fetched = svc.get_object(obj.id)
        assert fetched is not None
        assert fetched.id == obj.id

    def test_get_missing_returns_none(self):
        svc = ControlFabricService()
        assert svc.get_object(uuid.uuid4()) is None

    def test_update_status(self):
        svc = ControlFabricService()
        obj = _make_obj(svc, "Obj1")
        updated = svc.update_object_status(obj.id, ControlObjectStatus.SUPERSEDED)
        assert updated is not None
        assert updated.status == ControlObjectStatus.SUPERSEDED
        assert updated.version == 2

    def test_retire(self):
        svc = ControlFabricService()
        obj = _make_obj(svc, "Obj1")
        retired = svc.retire_object(obj.id)
        assert retired is not None
        assert retired.status == ControlObjectStatus.RETIRED


class TestLinking:
    def test_link_objects(self):
        svc = ControlFabricService()
        a = _make_obj(svc, "A")
        b = _make_obj(svc, "B")
        link = svc.link_objects(
            TENANT,
            FabricLinkCreate(
                source_id=a.id,
                target_id=b.id,
                link_type=ControlLinkType.DEPENDS_ON,
            ),
        )
        assert link.source_id == a.id
        assert link.target_id == b.id
        assert link.link_type == ControlLinkType.DEPENDS_ON

    def test_get_links_outgoing(self):
        svc = ControlFabricService()
        a = _make_obj(svc, "A")
        b = _make_obj(svc, "B")
        svc.link_objects(
            TENANT,
            FabricLinkCreate(source_id=a.id, target_id=b.id, link_type=ControlLinkType.SATISFIES),
        )
        links = svc.get_links_for_object(a.id, direction="outgoing")
        assert len(links) == 1
        assert links[0].target_id == b.id

    def test_get_contradictions(self):
        svc = ControlFabricService()
        a = _make_obj(svc, "A", plane=ControlPlane.COMMERCIAL)
        b = _make_obj(svc, "B", plane=ControlPlane.FIELD)
        svc.link_objects(
            TENANT,
            FabricLinkCreate(source_id=a.id, target_id=b.id, link_type=ControlLinkType.CONTRADICTS),
        )
        contradictions = svc.get_contradictions(TENANT)
        assert len(contradictions) == 1


class TestQuery:
    def test_query_by_plane(self):
        svc = ControlFabricService()
        _make_obj(svc, "Commercial1", plane=ControlPlane.COMMERCIAL)
        _make_obj(svc, "Field1", plane=ControlPlane.FIELD)
        _make_obj(svc, "Commercial2", plane=ControlPlane.COMMERCIAL)

        results, total = svc.query_objects(
            TENANT,
            FabricQueryFilter(planes=[ControlPlane.COMMERCIAL]),
        )
        assert total == 2
        assert all(o.plane == ControlPlane.COMMERCIAL for o in results)

    def test_query_by_domain(self):
        svc = ControlFabricService()
        _make_obj(svc, "CM1", domain="contract_margin")
        _make_obj(svc, "TO1", domain="telco_ops")

        results, total = svc.query_objects(
            TENANT,
            FabricQueryFilter(domains=["telco_ops"]),
        )
        assert total == 1
        assert results[0].domain == "telco_ops"

    def test_query_by_confidence(self):
        svc = ControlFabricService()
        _make_obj(svc, "High", confidence=0.95)
        _make_obj(svc, "Low", confidence=0.3)

        results, total = svc.query_objects(
            TENANT,
            FabricQueryFilter(min_confidence=0.8),
        )
        assert total == 1
        assert results[0].label == "High"

    def test_query_by_tags(self):
        svc = ControlFabricService()
        _make_obj(svc, "Tagged", tags=["billing", "urgent"])
        _make_obj(svc, "NotTagged")

        results, total = svc.query_objects(
            TENANT,
            FabricQueryFilter(tags=["billing"]),
        )
        assert total == 1
        assert results[0].label == "Tagged"

    def test_get_objects_by_plane(self):
        svc = ControlFabricService()
        _make_obj(svc, "Svc1", plane=ControlPlane.SERVICE)
        _make_obj(svc, "Com1", plane=ControlPlane.COMMERCIAL)

        results = svc.get_objects_by_plane(TENANT, ControlPlane.SERVICE)
        assert len(results) == 1
        assert results[0].label == "Svc1"


class TestSlice:
    def test_basic_slice(self):
        svc = ControlFabricService()
        a = _make_obj(svc, "A")
        b = _make_obj(svc, "B")
        c = _make_obj(svc, "C")
        svc.link_objects(
            TENANT,
            FabricLinkCreate(source_id=a.id, target_id=b.id, link_type=ControlLinkType.DEPENDS_ON),
        )
        svc.link_objects(
            TENANT,
            FabricLinkCreate(source_id=b.id, target_id=c.id, link_type=ControlLinkType.TRIGGERS),
        )

        slice_result = svc.build_slice(
            TENANT,
            FabricSliceRequest(root_ids=[a.id], max_depth=3),
        )
        assert slice_result.total_objects == 3
        assert slice_result.total_links >= 2

    def test_slice_with_plane_filter(self):
        svc = ControlFabricService()
        a = _make_obj(svc, "A", plane=ControlPlane.COMMERCIAL)
        b = _make_obj(svc, "B", plane=ControlPlane.FIELD)
        c = _make_obj(svc, "C", plane=ControlPlane.COMMERCIAL)
        svc.link_objects(
            TENANT,
            FabricLinkCreate(source_id=a.id, target_id=b.id, link_type=ControlLinkType.DEPENDS_ON),
        )
        svc.link_objects(
            TENANT,
            FabricLinkCreate(source_id=a.id, target_id=c.id, link_type=ControlLinkType.DEPENDS_ON),
        )

        slice_result = svc.build_slice(
            TENANT,
            FabricSliceRequest(
                root_ids=[a.id],
                planes=[ControlPlane.COMMERCIAL],
                max_depth=3,
            ),
        )
        assert all(o.plane == ControlPlane.COMMERCIAL for o in slice_result.objects)

    def test_slice_excludes_retired(self):
        svc = ControlFabricService()
        a = _make_obj(svc, "A")
        b = _make_obj(svc, "B")
        svc.link_objects(
            TENANT,
            FabricLinkCreate(source_id=a.id, target_id=b.id, link_type=ControlLinkType.DEPENDS_ON),
        )
        svc.retire_object(b.id)

        slice_result = svc.build_slice(
            TENANT,
            FabricSliceRequest(root_ids=[a.id], max_depth=3, include_retired=False),
        )
        assert slice_result.total_objects == 1


class TestStats:
    def test_stats(self):
        svc = ControlFabricService()
        _make_obj(svc, "A", plane=ControlPlane.COMMERCIAL)
        _make_obj(svc, "B", plane=ControlPlane.FIELD)
        a = _make_obj(svc, "C", plane=ControlPlane.COMMERCIAL)
        b = _make_obj(svc, "D", plane=ControlPlane.SERVICE)
        svc.link_objects(
            TENANT,
            FabricLinkCreate(source_id=a.id, target_id=b.id, link_type=ControlLinkType.TRIGGERS),
        )

        stats = svc.get_stats(TENANT)
        assert stats.total_objects == 4
        assert stats.total_links == 1
        assert stats.objects_by_plane["commercial"] == 2
        assert stats.objects_by_plane["field"] == 1
