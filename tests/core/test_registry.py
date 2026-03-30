from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.graph.domain_types import (
    ControlObject,
    ControlObjectProvenance,
    ControlObjectState,
    ControlObjectType,
)
from app.core.registry.domain_types import SchemaNamespace, VersionRecord
from app.core.registry.object_registry import ObjectRegistry, RegistryError
from app.core.registry.schema_registry import SchemaRegistry, SchemaValidationError


def make_provenance(content: str = "test") -> ControlObjectProvenance:
    return ControlObjectProvenance.create(
        source_system="test", source_content=content, ingested_by="test-user"
    )


def make_object(
    name: str,
    object_type: ControlObjectType = ControlObjectType.RISK_CONTROL,
    plane: str = "risk",
    state: ControlObjectState = ControlObjectState.DRAFT,
) -> ControlObject:
    return ControlObject(
        object_type=object_type,
        name=name,
        schema_namespace="core",
        provenance=make_provenance(content=name),
        operational_plane=plane,
        state=state,
    )


class TestSchemaRegistry:
    def test_core_namespaces_seeded_on_init(self) -> None:
        registry = SchemaRegistry()
        assert registry.namespace_count > 0

    def test_register_new_namespace(self) -> None:
        registry = SchemaRegistry()
        ns = SchemaNamespace(
            name="gdpr",
            version="1.0.0",
            domain_pack="gdpr-pack",
            object_type=ControlObjectType.COMPLIANCE_REQUIREMENT,
            required_attributes=["article_number"],
            description="GDPR namespace",
        )
        registry.register(ns)
        retrieved = registry.get("gdpr", "1.0.0")
        assert retrieved is not None
        assert retrieved.name == "gdpr"

    def test_duplicate_namespace_raises(self) -> None:
        registry = SchemaRegistry()
        ns = SchemaNamespace(
            name="test-ns",
            version="1.0.0",
            domain_pack="test",
            object_type=ControlObjectType.ASSET,
            required_attributes=[],
        )
        registry.register(ns)
        with pytest.raises(SchemaValidationError):
            registry.register(ns)

    def test_get_namespaces_for_type(self) -> None:
        registry = SchemaRegistry()
        namespaces = registry.get_for_type(ControlObjectType.RISK_CONTROL)
        assert len(namespaces) > 0

    def test_validate_attributes_missing_required(self) -> None:
        registry = SchemaRegistry()
        ns = SchemaNamespace(
            name="strict",
            version="1.0.0",
            domain_pack="test",
            object_type=ControlObjectType.ASSET,
            required_attributes=["asset_value", "owner"],
        )
        registry.register(ns)
        with pytest.raises(SchemaValidationError, match="Missing required attributes"):
            registry.validate_attributes("strict", "1.0.0", {"asset_value": "high"})

    def test_validate_attributes_passes_with_required(self) -> None:
        registry = SchemaRegistry()
        ns = SchemaNamespace(
            name="strict2",
            version="1.0.0",
            domain_pack="test",
            object_type=ControlObjectType.ASSET,
            required_attributes=["asset_value"],
        )
        registry.register(ns)
        registry.validate_attributes("strict2", "1.0.0", {"asset_value": "high"})


class TestObjectRegistry:
    def test_register_new_object(self) -> None:
        registry = ObjectRegistry()
        obj = make_object("ctrl-001")
        registered = registry.register(obj, registered_by="test-user")
        assert registry.get(registered.object_id) is not None
        assert registry.object_count == 1

    def test_duplicate_registration_raises(self) -> None:
        registry = ObjectRegistry()
        obj = make_object("ctrl-001")
        registry.register(obj, registered_by="test-user")
        with pytest.raises(RegistryError):
            registry.register(obj, registered_by="test-user")

    def test_version_history_recorded_on_register(self) -> None:
        registry = ObjectRegistry()
        obj = make_object("ctrl-001")
        registry.register(obj, registered_by="test-user", reason="initial")
        history = registry.get_version_history(obj.object_id)
        assert len(history) == 1
        assert history[0].version == 1
        assert history[0].changed_by == "test-user"

    def test_update_creates_new_version_record(self) -> None:
        registry = ObjectRegistry()
        obj = make_object("ctrl-001")
        registry.register(obj, registered_by="user-a")
        updated = obj.transition_to(ControlObjectState.ACTIVE)
        registry.update(updated, updated_by="user-b", reason="activation")
        history = registry.get_version_history(obj.object_id)
        assert len(history) == 2
        assert history[1].version == 2
        assert history[1].changed_by == "user-b"

    def test_version_mismatch_raises(self) -> None:
        registry = ObjectRegistry()
        obj = make_object("ctrl-001")
        registry.register(obj, registered_by="user")
        wrong_version = obj.model_copy(update={"version": 5})
        with pytest.raises(RegistryError, match="Version mismatch"):
            registry.update(wrong_version, updated_by="user", reason="test")

    def test_state_transition(self) -> None:
        registry = ObjectRegistry()
        obj = make_object("ctrl-001")
        registry.register(obj, registered_by="user")
        activated = registry.transition_state(
            obj.object_id, ControlObjectState.ACTIVE, transitioned_by="user", reason="ready"
        )
        assert activated.state == ControlObjectState.ACTIVE
        assert registry.get(obj.object_id).state == ControlObjectState.ACTIVE

    def test_history_is_immutable(self) -> None:
        """Patent Claim: Historical states cannot be retroactively altered."""
        registry = ObjectRegistry()
        obj = make_object("ctrl-001")
        registry.register(obj, registered_by="user")
        history = registry.get_version_history(obj.object_id)
        with pytest.raises((ValidationError, AttributeError, TypeError)):
            history[0].version = 999

    def test_history_integrity_verification(self) -> None:
        """Patent Claim: Cryptographic history integrity is verifiable."""
        registry = ObjectRegistry()
        obj = make_object("ctrl-001")
        registry.register(obj, registered_by="user")
        activated = registry.transition_state(
            obj.object_id, ControlObjectState.ACTIVE, transitioned_by="user", reason="test"
        )
        assert registry.verify_history_integrity() is True

    def test_events_recorded_for_all_operations(self) -> None:
        registry = ObjectRegistry()
        obj = make_object("ctrl-001")
        registry.register(obj, registered_by="user")
        registry.transition_state(
            obj.object_id, ControlObjectState.ACTIVE, transitioned_by="user", reason="test"
        )
        assert registry.event_count >= 2

    def test_get_by_plane(self) -> None:
        registry = ObjectRegistry()
        registry.register(make_object("risk-1", plane="risk"), registered_by="user")
        registry.register(make_object("risk-2", plane="risk"), registered_by="user")
        registry.register(
            make_object(
                "compliance-1",
                object_type=ControlObjectType.COMPLIANCE_REQUIREMENT,
                plane="compliance",
            ),
            registered_by="user",
        )
        assert len(registry.get_by_plane("risk")) == 2
        assert len(registry.get_by_plane("compliance")) == 1

    def test_get_active_only(self) -> None:
        registry = ObjectRegistry()
        draft_obj = make_object("draft-ctrl")
        active_obj = make_object("active-ctrl", state=ControlObjectState.DRAFT)
        registry.register(draft_obj, registered_by="user")
        registry.register(active_obj, registered_by="user")
        registry.transition_state(
            active_obj.object_id, ControlObjectState.ACTIVE, transitioned_by="user", reason="test"
        )
        active = registry.get_active()
        assert len(active) == 1
        assert active[0].object_id == active_obj.object_id

    def test_update_unknown_object_raises(self) -> None:
        registry = ObjectRegistry()
        obj = make_object("ghost")
        with pytest.raises(RegistryError):
            registry.update(obj, updated_by="user", reason="test")


class TestPatentClaimsRegistry:
    def test_claim_version_history_append_only(self) -> None:
        """
        UK Patent Theme 1: Linear version control — historical states
        can never be retroactively altered or deleted.
        """
        registry = ObjectRegistry()
        obj = make_object("ctrl")
        registry.register(obj, registered_by="user-a", reason="initial")
        activated = registry.transition_state(
            obj.object_id, ControlObjectState.ACTIVE, transitioned_by="user-b", reason="activate"
        )
        history = registry.get_version_history(obj.object_id)
        assert len(history) == 2
        assert history[0].version == 1
        assert history[0].state == "draft"
        assert history[1].version == 2
        assert history[1].state == "active"

    def test_claim_every_operation_produces_audit_event(self) -> None:
        """
        UK Patent Theme 1: Every operation against a control object
        produces an immutable audit event.
        """
        registry = ObjectRegistry()
        obj = make_object("ctrl")
        registry.register(obj, registered_by="user")
        registry.transition_state(
            obj.object_id, ControlObjectState.ACTIVE, transitioned_by="user", reason="activate"
        )
        events = registry.get_events()
        event_types = [e.event_type for e in events]
        assert "registered" in event_types
        assert "state_changed" in event_types

    def test_claim_domain_pack_extends_schema_without_core_change(self) -> None:
        """
        UK Patent Theme 5: Domain packs inject new namespaces without
        modifying core platform code. The schema registry accepts new
        domain types dynamically.
        """
        registry = SchemaRegistry()
        initial_count = registry.namespace_count
        telco_ns = SchemaNamespace(
            name="telco-ops",
            version="1.0.0",
            domain_pack="telco-ops-pack",
            object_type=ControlObjectType.DOMAIN_PACK_EXTENSION,
            required_attributes=["network_element", "operator_id"],
            description="Telco operations domain pack namespace",
        )
        registry.register(telco_ns)
        assert registry.namespace_count == initial_count + 1
        retrieved = registry.get("telco-ops", "1.0.0")
        assert retrieved is not None
        assert retrieved.domain_pack == "telco-ops-pack"
