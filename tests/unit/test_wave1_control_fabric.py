"""Wave 1 Control Fabric Core tests.

Comprehensive deterministic tests for:
- Object creation success/failure
- Lifecycle transitions
- Supersede/version lineage
- Invalid payload rejection via registry validators
- Registry registration and duplicate prevention
- Link creation success/failure
- Invalid link policy rejection
- Neighbour/path/slice queries
- Contradiction detection
- Missing-link detection
- Graph consistency evaluation
- Audit hook emission
- Domain pack registration integration
- Typed graph path and slice
- Correlation keys and external refs
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.audit import FabricAuditEventType, FabricAuditHook
from app.core.control_link import ControlLinkCreate
from app.core.control_object import (
    ControlObject,
    ControlObjectCreate,
    build_control_object,
    supersede_object,
)
from app.core.domain_integration import (
    register_all_domain_packs,
    register_contract_margin,
    register_telco_ops,
    register_utilities_field,
)
from app.core.errors import (
    ControlObjectFrozenError,
    ControlObjectStateError,
    DuplicateRegistrationError,
    InvalidControlObjectError,
    InvalidLinkError,
    UnknownObjectKindError,
)
from app.core.graph.consistency import GraphConsistencyChecker
from app.core.graph.service import GraphService
from app.core.registry import FabricRegistry, ObjectKindSpec
from app.core.types import (
    AuditContext,
    ControlGraphSlice,
    ControlLinkType,
    ControlObjectCorrelationKeys,
    ControlObjectExternalRefs,
    ControlObjectId,
    ControlObjectLineage,
    ControlObjectType,
    ControlObjectVersionInfo,
    ControlState,
    EvidenceRef,
    FabricVersion,
    GraphConsistencyStatus,
    GraphPath,
    GraphTraversalPolicy,
    PlaneType,
)

TENANT = uuid.uuid4()
AUDIT = AuditContext(actor="test", action="test", timestamp=datetime.now(UTC))


def _create(
    label: str = "Test",
    plane: PlaneType = PlaneType.COMMERCIAL,
    domain: str = "test",
    obj_type: ControlObjectType = ControlObjectType.OBLIGATION,
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> ControlObjectCreate:
    return ControlObjectCreate(
        object_type=obj_type,
        plane=plane,
        domain=domain,
        label=label,
        payload=payload or {},
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════
# A. CONTROL OBJECT FABRIC
# ═══════════════════════════════════════════════════════════════


class TestObjectCreation:
    def test_factory_produces_draft(self):
        obj = build_control_object(TENANT, _create())
        assert obj.state == ControlState.DRAFT
        assert obj.version == FabricVersion(1)
        assert obj.tenant_id == TENANT

    def test_empty_label_rejected(self):
        with pytest.raises(InvalidControlObjectError, match="label"):
            build_control_object(TENANT, _create(label="  "))

    def test_empty_domain_rejected(self):
        with pytest.raises(InvalidControlObjectError, match="domain"):
            build_control_object(TENANT, _create(domain=""))

    def test_confidence_out_of_range(self):
        with pytest.raises(InvalidControlObjectError, match="Confidence"):
            build_control_object(TENANT, _create(confidence=-0.1))

    def test_unique_ids(self):
        a = build_control_object(TENANT, _create())
        b = build_control_object(TENANT, _create())
        assert a.id != b.id

    def test_provenance_is_set(self):
        obj = build_control_object(TENANT, _create())
        assert obj.provenance.created_by == "system"

    def test_schema_version_default(self):
        obj = build_control_object(TENANT, _create())
        assert obj.schema_version == "1.0"

    def test_timestamps_set(self):
        obj = build_control_object(TENANT, _create())
        assert obj.created_at is not None
        assert obj.updated_at is not None

    def test_audit_trail_on_creation(self):
        obj = build_control_object(TENANT, _create())
        assert len(obj.audit_trail) == 1
        assert obj.audit_trail[0].action == "created"


class TestLifecycleTransitions:
    def test_draft_to_active(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        assert obj.state == ControlState.ACTIVE

    def test_active_to_enriched(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.enrich({"x": 1}, AUDIT)
        assert obj.state == ControlState.ENRICHED

    def test_active_to_frozen(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        assert obj.state == ControlState.FROZEN

    def test_frozen_to_reconciled(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        obj.mark_reconciled(AUDIT)
        assert obj.state == ControlState.RECONCILED

    def test_frozen_to_disputed(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        obj.mark_disputed(AUDIT)
        assert obj.state == ControlState.DISPUTED

    def test_reconciled_to_actioned(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        obj.mark_reconciled(AUDIT)
        obj.mark_actioned(AUDIT)
        assert obj.state == ControlState.ACTIONED

    def test_active_to_superseded(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.supersede(ControlObjectId(uuid.uuid4()), AUDIT)
        assert obj.state == ControlState.SUPERSEDED

    def test_active_to_deprecated(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.deprecate(AUDIT)
        assert obj.state == ControlState.DEPRECATED

    def test_invalid_transition_raises(self):
        obj = build_control_object(TENANT, _create())
        with pytest.raises(ControlObjectStateError):
            obj.freeze(AUDIT)  # draft → frozen invalid

    def test_superseded_is_terminal(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.supersede(ControlObjectId(uuid.uuid4()), AUDIT)
        with pytest.raises(ControlObjectStateError):
            obj.activate(AUDIT)

    def test_deprecated_is_terminal(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.deprecate(AUDIT)
        with pytest.raises(ControlObjectStateError):
            obj.activate(AUDIT)

    def test_frozen_rejects_enrich(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        with pytest.raises(ControlObjectFrozenError):
            obj.enrich({"x": 1}, AUDIT)

    def test_frozen_rejects_evidence(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        with pytest.raises(ControlObjectFrozenError):
            obj.attach_evidence(EvidenceRef(evidence_type="doc", source_label="x"))

    def test_disputed_to_active(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.freeze(AUDIT)
        obj.mark_disputed(AUDIT)
        obj.activate(AUDIT)
        assert obj.state == ControlState.ACTIVE

    def test_full_lifecycle_audit_trail(self):
        obj = build_control_object(TENANT, _create())
        obj.activate(AUDIT)
        obj.enrich({"x": 1}, AUDIT)
        obj.freeze(AUDIT)
        obj.mark_reconciled(AUDIT)
        obj.mark_actioned(AUDIT)
        assert len(obj.audit_trail) >= 6


class TestSupersedeVersionLineage:
    def test_supersede_creates_new_version(self):
        original = build_control_object(TENANT, _create(label="V1"))
        original.activate(AUDIT)
        new_obj = supersede_object(original, _create(label="V2"), "test")
        assert new_obj.version == FabricVersion(2)
        assert new_obj.derived_from == [original.id]
        assert original.state == ControlState.SUPERSEDED
        assert original.superseded_by == new_obj.id

    def test_supersede_preserves_tenant(self):
        original = build_control_object(TENANT, _create())
        original.activate(AUDIT)
        new_obj = supersede_object(original, _create(label="V2"), "test")
        assert new_obj.tenant_id == TENANT

    def test_graph_service_supersede_lineage(self):
        svc = GraphService()
        orig = svc.create_object(TENANT, _create("V1"))
        v2 = svc.supersede_object(orig.id, _create("V2"))
        assert v2 is not None
        lineage = svc.get_lineage(v2.id)
        assert lineage is not None
        assert orig.id in lineage.supersedes
        assert lineage.depth >= 1

    def test_lineage_chain(self):
        svc = GraphService()
        v1 = svc.create_object(TENANT, _create("V1"))
        v2 = svc.supersede_object(v1.id, _create("V2"))
        v3 = svc.supersede_object(v2.id, _create("V3"))
        lineage = svc.get_lineage(v3.id)
        assert lineage is not None
        assert lineage.depth >= 1


# ═══════════════════════════════════════════════════════════════
# B. REGISTRY, PAYLOAD VALIDATION, DOMAIN PACKS
# ═══════════════════════════════════════════════════════════════


class TestRegistryPayloadValidation:
    def test_required_fields_enforced(self):
        reg = FabricRegistry()
        reg.register_object_kind(
            ObjectKindSpec(
                kind_name="test_kind",
                object_type=ControlObjectType.OBLIGATION,
                allowed_planes=[PlaneType.COMMERCIAL],
                domain="test",
                required_payload_fields=["amount", "currency"],
            )
        )
        errors = reg.validate_payload("test_kind", {"amount": 100})
        assert any("currency" in e for e in errors)

    def test_valid_payload_passes(self):
        reg = FabricRegistry()
        reg.register_object_kind(
            ObjectKindSpec(
                kind_name="test_kind",
                object_type=ControlObjectType.OBLIGATION,
                allowed_planes=[PlaneType.COMMERCIAL],
                domain="test",
                required_payload_fields=["amount"],
            )
        )
        errors = reg.validate_payload("test_kind", {"amount": 100})
        assert errors == []

    def test_custom_payload_validator(self):
        reg = FabricRegistry()
        reg.register_object_kind(
            ObjectKindSpec(
                kind_name="rate_kind",
                object_type=ControlObjectType.RATE_CARD,
                allowed_planes=[PlaneType.COMMERCIAL],
                domain="test",
                required_payload_fields=["rate"],
            )
        )

        def validate_rate(payload: dict[str, Any]) -> list[str]:
            rate = payload.get("rate")
            if rate is not None and rate < 0:
                return ["Rate must be non-negative"]
            return []

        reg.register_payload_validator("rate_kind", validate_rate)

        errors = reg.validate_payload("rate_kind", {"rate": -5})
        assert len(errors) == 1
        assert "non-negative" in errors[0]

        errors = reg.validate_payload("rate_kind", {"rate": 100})
        assert errors == []

    def test_duplicate_registration_raises(self):
        reg = FabricRegistry()
        spec = ObjectKindSpec(
            kind_name="dup",
            object_type=ControlObjectType.OBLIGATION,
            allowed_planes=[PlaneType.COMMERCIAL],
            domain="test",
        )
        reg.register_object_kind(spec)
        with pytest.raises(DuplicateRegistrationError):
            reg.register_object_kind(spec)

    def test_unknown_kind_raises(self):
        reg = FabricRegistry()
        with pytest.raises(UnknownObjectKindError):
            reg.get_object_kind("nonexistent")

    def test_fabric_policy_hooks(self):
        reg = FabricRegistry()
        calls: list[str] = []
        reg.register_fabric_policy_hook("my_kind", lambda evt: calls.append(evt))
        hooks = reg.get_fabric_policy_hooks("my_kind")
        assert len(hooks) == 1
        hooks[0]("test_event")
        assert calls == ["test_event"]

    def test_no_hooks_for_unknown_kind(self):
        reg = FabricRegistry()
        assert reg.get_fabric_policy_hooks("unknown") == []


class TestDomainPackRegistration:
    def test_contract_margin_registers(self):
        reg = FabricRegistry()
        register_contract_margin(reg)
        assert reg.has_object_kind("extracted_clause")
        assert reg.has_object_kind("rate_card_entry")
        assert reg.has_object_kind("billable_event")
        assert reg.has_object_kind("leakage_trigger")
        assert reg.has_object_kind("margin_diagnosis")

    def test_telco_ops_registers(self):
        reg = FabricRegistry()
        register_telco_ops(reg)
        assert reg.has_object_kind("incident_state")
        assert reg.has_object_kind("escalation_rule")
        assert reg.has_object_kind("service_state")

    def test_utilities_field_registers(self):
        reg = FabricRegistry()
        register_utilities_field(reg)
        assert reg.has_object_kind("work_order")
        assert reg.has_object_kind("readiness_check")
        assert reg.has_object_kind("completion_certificate")

    def test_all_packs_register_without_conflict(self):
        reg = FabricRegistry()
        register_all_domain_packs(reg)
        all_kinds = reg.list_object_kinds()
        assert len(all_kinds) >= 11
        domains = {k.domain for k in all_kinds}
        assert "contract_margin" in domains
        assert "telco_ops" in domains
        assert "utilities_field" in domains

    def test_registration_emits_audit(self):
        reg = FabricRegistry()
        audit = FabricAuditHook()
        register_all_domain_packs(reg, audit_hook=audit)
        events = audit.get_events_by_type(FabricAuditEventType.DOMAIN_PACK_REGISTERED)
        assert len(events) == 3
        domains = {e.domain for e in events}
        assert domains == {"contract_margin", "telco_ops", "utilities_field"}

    def test_contract_margin_payload_validation(self):
        reg = FabricRegistry()
        register_contract_margin(reg)
        errors = reg.validate_payload("rate_card_entry", {"rate": 100})
        assert any("unit" in e for e in errors)
        errors = reg.validate_payload("rate_card_entry", {"rate": 100, "unit": "per_hour"})
        assert errors == []

    def test_cross_domain_link_policies(self):
        reg = FabricRegistry()
        register_all_domain_packs(reg)
        policies = reg.get_link_policies(source_kind="work_order", target_kind="incident_state")
        assert len(policies) == 1
        assert policies[0].required_cross_plane


# ═══════════════════════════════════════════════════════════════
# C. CONTROL LINK / CONTROL GRAPH
# ═══════════════════════════════════════════════════════════════


class TestLinkCreation:
    def test_create_link(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A"))
        b = svc.create_object(TENANT, _create("B"))
        link = svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id,
                target_id=b.id,
                link_type=ControlLinkType.DERIVES_FROM,
            ),
        )
        assert link.source_id == a.id
        assert link.link_type == ControlLinkType.DERIVES_FROM

    def test_cross_plane_link(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("Comm", PlaneType.COMMERCIAL))
        b = svc.create_object(TENANT, _create("Field", PlaneType.FIELD))
        link = svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id,
                target_id=b.id,
                link_type=ControlLinkType.FULFILLS,
            ),
        )
        assert link.is_cross_plane

    def test_self_link_rejected(self):
        svc = GraphService()
        obj = svc.create_object(TENANT, _create("Self"))
        with pytest.raises(InvalidLinkError, match="Self-links"):
            svc.create_link(
                TENANT,
                ControlLinkCreate(
                    source_id=obj.id,
                    target_id=obj.id,
                    link_type=ControlLinkType.DERIVES_FROM,
                ),
            )

    def test_missing_source_rejected(self):
        svc = GraphService()
        b = svc.create_object(TENANT, _create("B"))
        with pytest.raises(InvalidLinkError, match="Source"):
            svc.create_link(
                TENANT,
                ControlLinkCreate(
                    source_id=uuid.uuid4(),
                    target_id=b.id,
                    link_type=ControlLinkType.DERIVES_FROM,
                ),
            )

    def test_missing_target_rejected(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A"))
        with pytest.raises(InvalidLinkError, match="Target"):
            svc.create_link(
                TENANT,
                ControlLinkCreate(
                    source_id=a.id,
                    target_id=uuid.uuid4(),
                    link_type=ControlLinkType.DERIVES_FROM,
                ),
            )


class TestLinkPolicyRejection:
    def test_supercedes_requires_same_type(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A", obj_type=ControlObjectType.OBLIGATION))
        b = svc.create_object(TENANT, _create("B", obj_type=ControlObjectType.RATE_CARD))
        with pytest.raises(InvalidLinkError, match="same object type"):
            svc.create_link(
                TENANT,
                ControlLinkCreate(
                    source_id=a.id,
                    target_id=b.id,
                    link_type=ControlLinkType.SUPERCEDES,
                ),
            )

    def test_supercedes_requires_same_plane(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A", PlaneType.COMMERCIAL))
        b = svc.create_object(TENANT, _create("B", PlaneType.FIELD))
        with pytest.raises(InvalidLinkError, match="same plane"):
            svc.create_link(
                TENANT,
                ControlLinkCreate(
                    source_id=a.id,
                    target_id=b.id,
                    link_type=ControlLinkType.SUPERCEDES,
                ),
            )

    def test_bills_for_requires_commercial(self):
        svc = GraphService()
        a = svc.create_object(
            TENANT, _create("A", PlaneType.FIELD, obj_type=ControlObjectType.BILLABLE_EVENT)
        )
        b = svc.create_object(TENANT, _create("B", PlaneType.COMMERCIAL))
        with pytest.raises(InvalidLinkError, match="commercial"):
            svc.create_link(
                TENANT,
                ControlLinkCreate(
                    source_id=a.id,
                    target_id=b.id,
                    link_type=ControlLinkType.BILLS_FOR,
                ),
            )


class TestGraphQueries:
    def test_get_neighbours(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A"))
        b = svc.create_object(TENANT, _create("B"))
        c = svc.create_object(TENANT, _create("C"))
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

    def test_find_path(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A"))
        b = svc.create_object(TENANT, _create("B"))
        c = svc.create_object(TENANT, _create("C"))
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
        a = svc.create_object(TENANT, _create("A"))
        b = svc.create_object(TENANT, _create("B"))
        assert svc.find_path(a.id, b.id) is None

    def test_typed_path(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A", PlaneType.COMMERCIAL))
        b = svc.create_object(TENANT, _create("B", PlaneType.FIELD))
        svc.create_link(
            TENANT,
            ControlLinkCreate(source_id=a.id, target_id=b.id, link_type=ControlLinkType.FULFILLS),
        )
        typed_path = svc.find_typed_path(a.id, b.id)
        assert typed_path is not None
        assert isinstance(typed_path, GraphPath)
        assert typed_path.crosses_planes
        assert PlaneType.COMMERCIAL in typed_path.planes_traversed
        assert PlaneType.FIELD in typed_path.planes_traversed
        assert typed_path.length == 2

    def test_graph_slice(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A"))
        b = svc.create_object(TENANT, _create("B"))
        c = svc.create_object(TENANT, _create("C"))
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

    def test_typed_graph_slice(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A", PlaneType.COMMERCIAL))
        b = svc.create_object(TENANT, _create("B", PlaneType.FIELD))
        svc.create_link(
            TENANT,
            ControlLinkCreate(source_id=a.id, target_id=b.id, link_type=ControlLinkType.FULFILLS),
        )
        policy = GraphTraversalPolicy(max_depth=3)
        graph_slice = svc.get_typed_graph_slice([a.id], policy)
        assert isinstance(graph_slice, ControlGraphSlice)
        assert graph_slice.total_objects == 2
        assert graph_slice.is_cross_plane
        assert not graph_slice.is_empty

    def test_graph_slice_respects_depth(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A"))
        b = svc.create_object(TENANT, _create("B"))
        c = svc.create_object(TENANT, _create("C"))
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
        objects, _ = svc.get_graph_slice([a.id], max_depth=1)
        assert len(objects) == 2  # only a and b


class TestContradictionDetection:
    def test_detect_contradictions(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A"))
        b = svc.create_object(TENANT, _create("B"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.CONTRADICTS
            ),
        )
        contradictions = svc.get_contradictions(TENANT)
        assert len(contradictions) == 1
        assert contradictions[0].link_type == ControlLinkType.CONTRADICTS

    def test_no_contradictions_when_clean(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A"))
        b = svc.create_object(TENANT, _create("B"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        assert svc.get_contradictions(TENANT) == []


class TestMissingLinkDetection:
    def test_detect_missing_bills_for(self):
        svc = GraphService()
        svc.create_object(TENANT, _create("BillEvent", obj_type=ControlObjectType.BILLABLE_EVENT))
        missing = svc.get_missing_expected_links(TENANT)
        assert len(missing) >= 1
        assert any(lt == ControlLinkType.BILLS_FOR for _, lt in missing)

    def test_detect_missing_fulfills_for_work_order(self):
        svc = GraphService()
        svc.create_object(
            TENANT, _create("WO", PlaneType.FIELD, obj_type=ControlObjectType.WORK_ORDER)
        )
        missing = svc.get_missing_expected_links(TENANT)
        assert any(lt == ControlLinkType.FULFILLS for _, lt in missing)

    def test_no_missing_when_satisfied(self):
        svc = GraphService()
        be = svc.create_object(
            TENANT,
            _create("BE", PlaneType.COMMERCIAL, obj_type=ControlObjectType.BILLABLE_EVENT),
        )
        rc = svc.create_object(
            TENANT,
            _create("RC", PlaneType.COMMERCIAL, obj_type=ControlObjectType.RATE_CARD),
        )
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=be.id, target_id=rc.id, link_type=ControlLinkType.BILLS_FOR
            ),
        )
        missing = svc.get_missing_expected_links(TENANT)
        assert not any(oid == be.id for oid, _ in missing)


class TestGraphConsistency:
    def test_clean_graph_consistent(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A"))
        b = svc.create_object(TENANT, _create("B"))
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
        a = svc.create_object(TENANT, _create("A"))
        b = svc.create_object(TENANT, _create("B"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        svc.create_object(TENANT, _create("Orphan"))
        report = svc.check_consistency(TENANT)
        orphaned = [i for i in report.issues if i.issue_type == "orphaned_object"]
        assert len(orphaned) >= 1

    def test_contradiction_flagged(self):
        svc = GraphService()
        a = svc.create_object(TENANT, _create("A"))
        b = svc.create_object(TENANT, _create("B"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.CONTRADICTS
            ),
        )
        report = svc.check_consistency(TENANT)
        contradictions = [i for i in report.issues if i.issue_type == "contradiction_detected"]
        assert len(contradictions) == 1

    def test_stale_reference_flagged(self):
        svc = GraphService()
        v1 = svc.create_object(TENANT, _create("V1"))
        v2 = svc.supersede_object(v1.id, _create("V2"))
        other = svc.create_object(TENANT, _create("Other"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=other.id,
                target_id=v1.id,
                link_type=ControlLinkType.DERIVES_FROM,
            ),
        )
        report = svc.check_consistency(TENANT)
        stale = [i for i in report.issues if i.issue_type == "stale_reference"]
        assert len(stale) >= 1


# ═══════════════════════════════════════════════════════════════
# D. AUDIT HOOK EMISSION
# ═══════════════════════════════════════════════════════════════


class TestAuditHookEmission:
    def test_create_emits_audit(self):
        audit = FabricAuditHook()
        svc = GraphService(audit_hook=audit)
        svc.create_object(TENANT, _create("Test"))
        created = audit.get_events_by_type(FabricAuditEventType.CONTROL_OBJECT_CREATED)
        assert len(created) == 1
        assert created[0].plane == PlaneType.COMMERCIAL

    def test_activate_emits_audit(self):
        audit = FabricAuditHook()
        svc = GraphService(audit_hook=audit)
        svc.create_object(TENANT, _create("Test"))
        activated = audit.get_events_by_type(FabricAuditEventType.CONTROL_OBJECT_ACTIVATED)
        assert len(activated) == 1

    def test_freeze_emits_audit(self):
        audit = FabricAuditHook()
        svc = GraphService(audit_hook=audit)
        obj = svc.create_object(TENANT, _create("Test"))
        svc.freeze_object(obj.id)
        frozen = audit.get_events_by_type(FabricAuditEventType.CONTROL_OBJECT_FROZEN)
        assert len(frozen) == 1

    def test_supersede_emits_audit(self):
        audit = FabricAuditHook()
        svc = GraphService(audit_hook=audit)
        obj = svc.create_object(TENANT, _create("V1"))
        svc.supersede_object(obj.id, _create("V2"))
        superseded = audit.get_events_by_type(FabricAuditEventType.CONTROL_OBJECT_SUPERSEDED)
        assert len(superseded) == 1

    def test_deprecate_emits_audit(self):
        audit = FabricAuditHook()
        svc = GraphService(audit_hook=audit)
        obj = svc.create_object(TENANT, _create("Test"))
        svc.deprecate_object(obj.id)
        deprecated = audit.get_events_by_type(FabricAuditEventType.CONTROL_OBJECT_DEPRECATED)
        assert len(deprecated) == 1

    def test_link_emits_audit(self):
        audit = FabricAuditHook()
        svc = GraphService(audit_hook=audit)
        a = svc.create_object(TENANT, _create("A"))
        b = svc.create_object(TENANT, _create("B"))
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=a.id, target_id=b.id, link_type=ControlLinkType.DERIVES_FROM
            ),
        )
        link_events = audit.get_events_by_type(FabricAuditEventType.CONTROL_LINK_CREATED)
        assert len(link_events) == 1
        assert link_events[0].link_type == ControlLinkType.DERIVES_FROM

    def test_consistency_check_emits_audit(self):
        audit = FabricAuditHook()
        svc = GraphService(audit_hook=audit)
        svc.create_object(TENANT, _create("A"))
        svc.check_consistency(TENANT)
        checks = audit.get_events_by_type(FabricAuditEventType.GRAPH_CONSISTENCY_CHECKED)
        assert len(checks) == 1

    def test_listener_receives_events(self):
        received: list[Any] = []
        audit = FabricAuditHook()
        audit.add_listener(lambda e: received.append(e))
        svc = GraphService(audit_hook=audit)
        svc.create_object(TENANT, _create("Test"))
        assert len(received) >= 2  # created + activated

    def test_event_count(self):
        audit = FabricAuditHook()
        svc = GraphService(audit_hook=audit)
        svc.create_object(TENANT, _create("A"))
        svc.create_object(TENANT, _create("B"))
        assert audit.count(FabricAuditEventType.CONTROL_OBJECT_CREATED) == 2
        assert audit.count() >= 4  # 2 created + 2 activated

    def test_get_events_for_object(self):
        audit = FabricAuditHook()
        svc = GraphService(audit_hook=audit)
        obj = svc.create_object(TENANT, _create("Track Me"))
        events = audit.get_events_for_object(obj.id)
        assert len(events) >= 1


# ═══════════════════════════════════════════════════════════════
# E. TYPED VALUE OBJECTS
# ═══════════════════════════════════════════════════════════════


class TestTypedValueObjects:
    def test_correlation_keys_round_trip(self):
        keys = ControlObjectCorrelationKeys(
            contract_ref="CTR-001",
            work_order_ref="WO-001",
            custom={"project_id": "PRJ-001"},
        )
        d = keys.as_dict()
        assert d["contract_ref"] == "CTR-001"
        assert d["project_id"] == "PRJ-001"
        restored = ControlObjectCorrelationKeys.from_dict(d)
        assert restored.contract_ref == "CTR-001"
        assert restored.custom["project_id"] == "PRJ-001"

    def test_external_refs_round_trip(self):
        refs = ControlObjectExternalRefs(
            crm_id="CRM-001",
            custom={"legacy_id": "L-001"},
        )
        d = refs.as_dict()
        assert d["crm_id"] == "CRM-001"
        assert d["legacy_id"] == "L-001"
        restored = ControlObjectExternalRefs.from_dict(d)
        assert restored.crm_id == "CRM-001"

    def test_version_info(self):
        info = ControlObjectVersionInfo(version=FabricVersion(2))
        assert info.version == 2
        assert info.is_latest

    def test_lineage(self):
        oid = ControlObjectId(uuid.uuid4())
        lineage = ControlObjectLineage(object_id=oid, depth=0)
        assert lineage.object_id == oid
        assert lineage.depth == 0

    def test_graph_path_empty(self):
        path = GraphPath()
        assert path.is_empty
        assert path.length == 0

    def test_graph_path_with_nodes(self):
        path = GraphPath(
            node_ids=[ControlObjectId(uuid.uuid4()), ControlObjectId(uuid.uuid4())],
            crosses_planes=True,
            planes_traversed=[PlaneType.COMMERCIAL, PlaneType.FIELD],
        )
        assert path.length == 2
        assert path.crosses_planes

    def test_graph_slice_empty(self):
        s = ControlGraphSlice()
        assert s.is_empty

    def test_traversal_policy_defaults(self):
        policy = GraphTraversalPolicy()
        assert policy.max_depth == 5
        assert policy.max_nodes == 1000
        assert policy.follow_bidirectional

    def test_graph_consistency_status_values(self):
        assert GraphConsistencyStatus.CONSISTENT.value == "consistent"
        assert GraphConsistencyStatus.DEGRADED.value == "degraded"
