"""Tests for control graph — linking, policy, consistency, queries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.control_link import ControlLinkCreate, build_control_link
from app.core.control_object import ControlObjectCreate
from app.core.errors import InvalidLinkError
from app.core.graph.consistency import GraphConsistencyChecker
from app.core.graph.policy import GraphPolicyEngine
from app.core.graph.service import GraphService
from app.core.types import (
    AuditContext,
    ControlLinkType,
    ControlObjectId,
    ControlObjectType,
    ControlState,
    PlaneType,
)

TENANT = uuid.uuid4()
AUDIT = AuditContext(actor="test", action="test", timestamp=datetime.now(UTC))


def _obj_create(
    label: str = "Test",
    plane: PlaneType = PlaneType.COMMERCIAL,
    obj_type: ControlObjectType = ControlObjectType.OBLIGATION,
    domain: str = "test",
    **kwargs,
) -> ControlObjectCreate:
    return ControlObjectCreate(
        object_type=obj_type, plane=plane, domain=domain, label=label, **kwargs
    )


class TestGraphLinking:
    def test_create_link_between_objects(self):
        svc = GraphService()
        src = svc.create_object(TENANT, _obj_create("Source"))
        tgt = svc.create_object(TENANT, _obj_create("Target"))
        link = svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=src.id, target_id=tgt.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        assert link.source_id == src.id
        assert link.target_id == tgt.id
        assert link.link_type == ControlLinkType.DERIVES_FROM

    def test_cross_plane_link(self):
        svc = GraphService()
        src = svc.create_object(TENANT, _obj_create("Comm", PlaneType.COMMERCIAL))
        tgt = svc.create_object(TENANT, _obj_create("Field", PlaneType.FIELD))
        link = svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=src.id, target_id=tgt.id, link_type=ControlLinkType.FULFILLS
            ),
        )
        assert link.is_cross_plane
        assert link.source_plane == PlaneType.COMMERCIAL
        assert link.target_plane == PlaneType.FIELD

    def test_link_to_missing_source_raises(self):
        svc = GraphService()
        tgt = svc.create_object(TENANT, _obj_create("Target"))
        with pytest.raises(InvalidLinkError, match="Source"):
            svc.create_link(
                TENANT,
                ControlLinkCreate(
                    source_id=uuid.uuid4(),
                    target_id=tgt.id,
                    link_type=ControlLinkType.DERIVES_FROM,
                ),
            )

    def test_link_to_missing_target_raises(self):
        svc = GraphService()
        src = svc.create_object(TENANT, _obj_create("Source"))
        with pytest.raises(InvalidLinkError, match="Target"):
            svc.create_link(
                TENANT,
                ControlLinkCreate(
                    source_id=src.id,
                    target_id=uuid.uuid4(),
                    link_type=ControlLinkType.DERIVES_FROM,
                ),
            )

    def test_self_link_rejected(self):
        svc = GraphService()
        obj = svc.create_object(TENANT, _obj_create("Self"))
        with pytest.raises(InvalidLinkError, match="Self-links"):
            svc.create_link(
                TENANT,
                ControlLinkCreate(
                    source_id=obj.id,
                    target_id=obj.id,
                    link_type=ControlLinkType.DERIVES_FROM,
                ),
            )

    def test_get_neighbours(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _obj_create("A"))
        b = svc.create_object(TENANT, _obj_create("B"))
        c = svc.create_object(TENANT, _obj_create("C"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        svc.create_link(
            TENANT,
            ControlLinkCreate(source_id=a.id, target_id=c.id, link_type=ControlLinkType.EVIDENCES),
        )
        neighbours = svc.get_neighbours(a.id)
        assert len(neighbours) == 2

    def test_get_links_for_object_outgoing(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _obj_create("A"))
        b = svc.create_object(TENANT, _obj_create("B"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        links = svc.get_links_for_object(a.id, direction="outgoing")
        assert len(links) == 1
        assert links[0].source_id == a.id

    def test_get_links_filtered_by_type(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _obj_create("A"))
        b = svc.create_object(TENANT, _obj_create("B"))
        c = svc.create_object(TENANT, _obj_create("C"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        svc.create_link(
            TENANT,
            ControlLinkCreate(source_id=a.id, target_id=c.id, link_type=ControlLinkType.EVIDENCES),
        )
        links = svc.get_links_for_object(a.id, link_type=ControlLinkType.DERIVES_FROM)
        assert len(links) == 1


class TestGraphPolicy:
    def test_supercedes_requires_same_type(self):
        svc = GraphService()
        src = svc.create_object(TENANT, _obj_create("Src", obj_type=ControlObjectType.OBLIGATION))
        tgt = svc.create_object(TENANT, _obj_create("Tgt", obj_type=ControlObjectType.RATE_CARD))
        with pytest.raises(InvalidLinkError, match="same object type"):
            svc.create_link(
                TENANT,
                ControlLinkCreate(
                    source_id=src.id, target_id=tgt.id, link_type=ControlLinkType.SUPERCEDES
                ),
            )

    def test_supercedes_requires_same_plane(self):
        svc = GraphService()
        src = svc.create_object(TENANT, _obj_create("Src", PlaneType.COMMERCIAL))
        tgt = svc.create_object(TENANT, _obj_create("Tgt", PlaneType.FIELD))
        with pytest.raises(InvalidLinkError, match="same plane"):
            svc.create_link(
                TENANT,
                ControlLinkCreate(
                    source_id=src.id, target_id=tgt.id, link_type=ControlLinkType.SUPERCEDES
                ),
            )

    def test_bills_for_requires_commercial_source(self):
        svc = GraphService()
        src = svc.create_object(
            TENANT, _obj_create("Src", PlaneType.FIELD, ControlObjectType.BILLABLE_EVENT)
        )
        tgt = svc.create_object(TENANT, _obj_create("Tgt", PlaneType.COMMERCIAL))
        with pytest.raises(InvalidLinkError, match="commercial"):
            svc.create_link(
                TENANT,
                ControlLinkCreate(
                    source_id=src.id, target_id=tgt.id, link_type=ControlLinkType.BILLS_FOR
                ),
            )

    def test_validate_link_returns_violations(self):
        engine = GraphPolicyEngine()
        from app.core.control_object import build_control_object

        src = build_control_object(TENANT, _obj_create("Src", PlaneType.FIELD))
        src.activate(AUDIT)
        tgt = build_control_object(TENANT, _obj_create("Tgt", PlaneType.COMMERCIAL))
        tgt.activate(AUDIT)
        violations = engine.validate_link(
            ControlLinkCreate(
                source_id=src.id, target_id=tgt.id, link_type=ControlLinkType.BILLS_FOR
            ),
            src,
            tgt,
        )
        assert any("commercial" in v.lower() for v in violations)


class TestGraphQueries:
    def test_find_path(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _obj_create("A"))
        b = svc.create_object(TENANT, _obj_create("B"))
        c = svc.create_object(TENANT, _obj_create("C"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=b.id, target_id=c.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        path = svc.find_path(a.id, c.id)
        assert path is not None
        assert path[0] == a.id
        assert path[-1] == c.id

    def test_find_path_not_found(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _obj_create("A"))
        b = svc.create_object(TENANT, _obj_create("B"))
        path = svc.find_path(a.id, b.id)
        assert path is None

    def test_graph_slice(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _obj_create("A"))
        b = svc.create_object(TENANT, _obj_create("B"))
        c = svc.create_object(TENANT, _obj_create("C"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=b.id, target_id=c.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        objects, links = svc.get_graph_slice([a.id], max_depth=2)
        assert len(objects) == 3
        assert len(links) >= 2

    def test_graph_slice_respects_depth(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _obj_create("A"))
        b = svc.create_object(TENANT, _obj_create("B"))
        c = svc.create_object(TENANT, _obj_create("C"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=b.id, target_id=c.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        objects, links = svc.get_graph_slice([a.id], max_depth=1)
        assert len(objects) == 2  # a and b only

    def test_get_contradictions(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _obj_create("A"))
        b = svc.create_object(TENANT, _obj_create("B"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.CONTRADICTS
            ),
        )
        contradictions = svc.get_contradictions(TENANT)
        assert len(contradictions) == 1

    def test_supersede_object_via_service(self):
        svc = GraphService()
        orig = svc.create_object(TENANT, _obj_create("V1"))
        new = svc.supersede_object(orig.id, _obj_create(label="V2"))
        assert new is not None
        assert new.version == 2
        assert svc.get_object(orig.id).state == ControlState.SUPERSEDED


class TestConsistencyChecker:
    def test_clean_graph_is_consistent(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _obj_create("A"))
        b = svc.create_object(TENANT, _obj_create("B"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        report = svc.check_consistency(TENANT)
        assert report.is_consistent

    def test_orphaned_object_flagged(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _obj_create("A"))
        b = svc.create_object(TENANT, _obj_create("B"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        svc.create_object(TENANT, _obj_create("Orphan"))
        report = svc.check_consistency(TENANT)
        orphaned = [i for i in report.issues if i.issue_type == "orphaned_object"]
        assert len(orphaned) >= 1

    def test_contradiction_flagged(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _obj_create("A"))
        b = svc.create_object(TENANT, _obj_create("B"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.CONTRADICTS
            ),
        )
        report = svc.check_consistency(TENANT)
        contradictions = [i for i in report.issues if i.issue_type == "contradiction_detected"]
        assert len(contradictions) == 1
