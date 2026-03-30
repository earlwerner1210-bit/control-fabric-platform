from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.core.graph.domain_types import (
    RELATIONSHIP_ENFORCEMENT_WEIGHT,
    VALID_STATE_TRANSITIONS,
    ControlEdge,
    ControlObject,
    ControlObjectProvenance,
    ControlObjectState,
    ControlObjectType,
    RelationshipType,
)
from app.core.graph.store import ControlGraphStore, GraphIntegrityError
from app.core.reconciliation.cross_plane_engine import (
    CrossPlaneReconciliationEngine,
    ReconciliationCaseSeverity,
    ReconciliationCaseType,
    build_core_reconciliation_rules,
)


def make_provenance(source: str = "test", content: str = "test") -> ControlObjectProvenance:
    return ControlObjectProvenance.create(
        source_system=source, source_content=content, ingested_by="test-user"
    )


def make_object(
    name: str,
    object_type: ControlObjectType = ControlObjectType.RISK_CONTROL,
    plane: str = "risk",
    state: ControlObjectState = ControlObjectState.ACTIVE,
) -> ControlObject:
    obj = ControlObject(
        object_type=object_type,
        name=name,
        schema_namespace="core",
        provenance=make_provenance(content=name),
        operational_plane=plane,
    )
    if state != ControlObjectState.DRAFT:
        obj = obj.transition_to(state)
    return obj


def make_edge(
    source: ControlObject,
    target: ControlObject,
    rel_type: RelationshipType = RelationshipType.MITIGATES,
) -> ControlEdge:
    return ControlEdge(
        source_object_id=source.object_id,
        target_object_id=target.object_id,
        relationship_type=rel_type,
        asserted_by="test-user",
    )


@pytest.fixture
def empty_graph() -> ControlGraphStore:
    return ControlGraphStore()


@pytest.fixture
def populated_graph() -> ControlGraphStore:
    graph = ControlGraphStore()
    vuln = make_object("vuln-001", ControlObjectType.VULNERABILITY, "risk")
    risk_ctrl = make_object("risk-ctrl-001", ControlObjectType.RISK_CONTROL, "risk")
    tech_ctrl = make_object("tech-ctrl-001", ControlObjectType.TECHNICAL_CONTROL, "security")
    comp_req = make_object(
        "compliance-req-001", ControlObjectType.COMPLIANCE_REQUIREMENT, "compliance"
    )
    mandate = make_object("mandate-001", ControlObjectType.REGULATORY_MANDATE, "compliance")
    for obj in [vuln, risk_ctrl, tech_ctrl, comp_req, mandate]:
        graph.add_object(obj)
    graph.add_edge(make_edge(risk_ctrl, vuln, RelationshipType.MITIGATES))
    graph.add_edge(make_edge(tech_ctrl, comp_req, RelationshipType.SATISFIES))
    graph.add_edge(make_edge(comp_req, mandate, RelationshipType.SATISFIES))
    return graph


class TestControlObject:
    def test_created_with_draft_state(self) -> None:
        obj = ControlObject(
            object_type=ControlObjectType.RISK_CONTROL,
            name="Test",
            schema_namespace="core",
            provenance=make_provenance(),
            operational_plane="risk",
        )
        assert obj.state == ControlObjectState.DRAFT
        assert obj.version == 1
        assert len(obj.object_hash) == 64

    def test_valid_transition_increments_version(self) -> None:
        obj = make_object("test", state=ControlObjectState.DRAFT)
        activated = obj.transition_to(ControlObjectState.ACTIVE)
        assert activated.state == ControlObjectState.ACTIVE
        assert activated.version == obj.version + 1

    def test_invalid_transition_raises(self) -> None:
        obj = make_object("test", state=ControlObjectState.ACTIVE)
        with pytest.raises(ValueError, match="Invalid transition"):
            obj.transition_to(ControlObjectState.DRAFT)

    def test_retired_is_terminal(self) -> None:
        active = make_object("test", state=ControlObjectState.ACTIVE)
        deprecated = active.transition_to(ControlObjectState.DEPRECATED)
        retired = deprecated.transition_to(ControlObjectState.RETIRED)
        assert retired.is_terminal()
        assert VALID_STATE_TRANSITIONS[ControlObjectState.RETIRED] == set()

    def test_provenance_has_cryptographic_hash(self) -> None:
        prov = ControlObjectProvenance.create(
            source_system="gdpr", source_content="GDPR Art 25", ingested_by="officer"
        )
        assert len(prov.source_hash) == 64

    def test_different_content_different_hash(self) -> None:
        p1 = ControlObjectProvenance.create("sys", "content-a", "user")
        p2 = ControlObjectProvenance.create("sys", "content-b", "user")
        assert p1.source_hash != p2.source_hash


class TestControlEdge:
    def test_enforcement_weight_from_type(self) -> None:
        edge = ControlEdge(
            source_object_id="src",
            target_object_id="tgt",
            relationship_type=RelationshipType.VIOLATES,
            asserted_by="test",
        )
        assert edge.enforcement_weight == 100

    def test_violates_higher_than_references(self) -> None:
        assert (
            RELATIONSHIP_ENFORCEMENT_WEIGHT[RelationshipType.VIOLATES]
            > RELATIONSHIP_ENFORCEMENT_WEIGHT[RelationshipType.REFERENCES]
        )

    def test_edge_hash_is_sha256(self) -> None:
        edge = ControlEdge(
            source_object_id="src",
            target_object_id="tgt",
            relationship_type=RelationshipType.MITIGATES,
            asserted_by="test",
        )
        assert len(edge.edge_hash) == 64

    def test_validity_window(self) -> None:
        past = datetime(2020, 1, 1, tzinfo=UTC)
        future = datetime(2030, 1, 1, tzinfo=UTC)
        edge = ControlEdge(
            source_object_id="src",
            target_object_id="tgt",
            relationship_type=RelationshipType.MITIGATES,
            asserted_by="test",
            valid_from=past,
            valid_until=future,
        )
        assert edge.is_valid_at(datetime.now(UTC)) is True

    def test_expired_edge_invalid(self) -> None:
        edge = ControlEdge(
            source_object_id="src",
            target_object_id="tgt",
            relationship_type=RelationshipType.MITIGATES,
            asserted_by="test",
            valid_from=datetime(2020, 1, 1, tzinfo=UTC),
            valid_until=datetime(2021, 1, 1, tzinfo=UTC),
        )
        assert edge.is_valid_at(datetime.now(UTC)) is False


class TestControlGraphStore:
    def test_add_and_retrieve(self, empty_graph: ControlGraphStore) -> None:
        obj = make_object("ctrl-001")
        empty_graph.add_object(obj)
        assert empty_graph.get_object(obj.object_id) is not None

    def test_duplicate_raises(self, empty_graph: ControlGraphStore) -> None:
        obj = make_object("ctrl-001")
        empty_graph.add_object(obj)
        with pytest.raises(GraphIntegrityError):
            empty_graph.add_object(obj)

    def test_edge_requires_valid_source(self, empty_graph: ControlGraphStore) -> None:
        target = make_object("target")
        empty_graph.add_object(target)
        edge = ControlEdge(
            source_object_id="ghost",
            target_object_id=target.object_id,
            relationship_type=RelationshipType.MITIGATES,
            asserted_by="test",
        )
        with pytest.raises(GraphIntegrityError):
            empty_graph.add_edge(edge)

    def test_edge_requires_valid_target(self, empty_graph: ControlGraphStore) -> None:
        source = make_object("source")
        empty_graph.add_object(source)
        edge = ControlEdge(
            source_object_id=source.object_id,
            target_object_id="ghost",
            relationship_type=RelationshipType.MITIGATES,
            asserted_by="test",
        )
        with pytest.raises(GraphIntegrityError):
            empty_graph.add_edge(edge)

    def test_no_self_referential_edges(self, empty_graph: ControlGraphStore) -> None:
        obj = make_object("self")
        empty_graph.add_object(obj)
        edge = ControlEdge(
            source_object_id=obj.object_id,
            target_object_id=obj.object_id,
            relationship_type=RelationshipType.MITIGATES,
            asserted_by="test",
        )
        with pytest.raises(GraphIntegrityError):
            empty_graph.add_edge(edge)

    def test_traversal_discovers_downstream(self, populated_graph: ControlGraphStore) -> None:
        risk_ctrl = populated_graph.get_objects_by_type(ControlObjectType.RISK_CONTROL.value)[0]
        result = populated_graph.traverse(risk_ctrl.object_id, direction="outbound", max_depth=3)
        assert len(result.discovered_objects) > 0

    def test_find_path_between_objects(self, populated_graph: ControlGraphStore) -> None:
        tech_ctrl = populated_graph.get_objects_by_type(ControlObjectType.TECHNICAL_CONTROL.value)[
            0
        ]
        mandate = populated_graph.get_objects_by_type(ControlObjectType.REGULATORY_MANDATE.value)[0]
        path = populated_graph.find_path_between(tech_ctrl.object_id, mandate.object_id)
        assert path is not None
        assert path.depth >= 2

    def test_impact_analysis(self, populated_graph: ControlGraphStore) -> None:
        comp_req = populated_graph.get_objects_by_type(
            ControlObjectType.COMPLIANCE_REQUIREMENT.value
        )[0]
        impact = populated_graph.get_impact_analysis(comp_req.object_id)
        assert "downstream_objects" in impact
        assert "upstream_objects" in impact


class TestReconciliationEngine:
    def test_detects_gap(self, empty_graph: ControlGraphStore) -> None:
        risk_ctrl = make_object("unlinked", ControlObjectType.RISK_CONTROL, "risk")
        empty_graph.add_object(risk_ctrl)
        engine = CrossPlaneReconciliationEngine(graph=empty_graph)
        cases = engine.run_full_reconciliation()
        gap_cases = [c for c in cases if c.case_type == ReconciliationCaseType.GAP]
        assert any(risk_ctrl.object_id in c.affected_object_ids for c in gap_cases)

    def test_no_gap_when_link_exists(self, populated_graph: ControlGraphStore) -> None:
        engine = CrossPlaneReconciliationEngine(graph=populated_graph)
        cases = engine.run_full_reconciliation()
        risk_ctrl_ids = {
            obj.object_id
            for obj in populated_graph.get_objects_by_type(ControlObjectType.RISK_CONTROL.value)
        }
        rule_001_gaps = [
            c
            for c in cases
            if c.case_type == ReconciliationCaseType.GAP
            and c.violated_rule_id == "CORE-001"
            and any(oid in risk_ctrl_ids for oid in c.affected_object_ids)
        ]
        assert len(rule_001_gaps) == 0

    def test_detects_conflict(self, empty_graph: ControlGraphStore) -> None:
        a = make_object("policy-a", ControlObjectType.OPERATIONAL_POLICY, "operations")
        b = make_object("policy-b", ControlObjectType.OPERATIONAL_POLICY, "compliance")
        empty_graph.add_object(a)
        empty_graph.add_object(b)
        empty_graph.add_edge(
            ControlEdge(
                source_object_id=a.object_id,
                target_object_id=b.object_id,
                relationship_type=RelationshipType.VIOLATES,
                asserted_by="test",
            )
        )
        engine = CrossPlaneReconciliationEngine(graph=empty_graph)
        cases = engine.run_full_reconciliation()
        assert any(c.case_type == ReconciliationCaseType.CONFLICT for c in cases)

    def test_detects_orphan(self, empty_graph: ControlGraphStore) -> None:
        orphan = make_object("lonely", ControlObjectType.SECURITY_CONTROL, "security")
        empty_graph.add_object(orphan)
        engine = CrossPlaneReconciliationEngine(graph=empty_graph)
        cases = engine.run_full_reconciliation()
        assert any(
            c.case_type == ReconciliationCaseType.ORPHAN
            and orphan.object_id in c.affected_object_ids
            for c in cases
        )

    def test_cases_cannot_be_silently_ignored(self, empty_graph: ControlGraphStore) -> None:
        empty_graph.add_object(make_object("unlinked", ControlObjectType.RISK_CONTROL, "risk"))
        engine = CrossPlaneReconciliationEngine(graph=empty_graph)
        engine.run_full_reconciliation()
        assert engine.total_cases > 0

    def test_remediation_suggestions_present(self, empty_graph: ControlGraphStore) -> None:
        empty_graph.add_object(make_object("unlinked", ControlObjectType.RISK_CONTROL, "risk"))
        engine = CrossPlaneReconciliationEngine(graph=empty_graph)
        cases = engine.run_full_reconciliation()
        assert all(len(c.remediation_suggestions) > 0 for c in cases)

    def test_cross_plane_path(self, populated_graph: ControlGraphStore) -> None:
        tech_ctrl = populated_graph.get_objects_by_type(ControlObjectType.TECHNICAL_CONTROL.value)[
            0
        ]
        mandate = populated_graph.get_objects_by_type(ControlObjectType.REGULATORY_MANDATE.value)[0]
        path = populated_graph.find_path_between(tech_ctrl.object_id, mandate.object_id)
        assert path is not None
        assert path.depth >= 2
