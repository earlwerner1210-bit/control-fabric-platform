"""Tests for FabricRegistry and domain pack integration."""

from __future__ import annotations

import pytest

from app.core.domain_integration import (
    register_all_domain_packs,
    register_contract_margin,
    register_telco_ops,
    register_utilities_field,
)
from app.core.errors import DuplicateRegistrationError, UnknownObjectKindError
from app.core.registry import (
    ActionPolicySpec,
    FabricRegistry,
    LinkPolicySpec,
    ObjectKindSpec,
    ReconciliationRuleSpec,
)
from app.core.types import ControlLinkType, ControlObjectType, PlaneType


class TestFabricRegistry:
    def test_register_object_kind(self):
        reg = FabricRegistry()
        spec = ObjectKindSpec(
            kind_name="test_kind",
            object_type=ControlObjectType.OBLIGATION,
            allowed_planes=[PlaneType.COMMERCIAL],
            domain="test",
        )
        reg.register_object_kind(spec)
        result = reg.get_object_kind("test_kind")
        assert result.kind_name == "test_kind"

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

    def test_has_object_kind(self):
        reg = FabricRegistry()
        assert not reg.has_object_kind("nope")
        reg.register_object_kind(
            ObjectKindSpec(
                kind_name="present",
                object_type=ControlObjectType.OBLIGATION,
                allowed_planes=[PlaneType.COMMERCIAL],
                domain="test",
            )
        )
        assert reg.has_object_kind("present")

    def test_list_by_domain(self):
        reg = FabricRegistry()
        reg.register_object_kind(
            ObjectKindSpec(
                kind_name="a",
                object_type=ControlObjectType.OBLIGATION,
                allowed_planes=[PlaneType.COMMERCIAL],
                domain="d1",
            )
        )
        reg.register_object_kind(
            ObjectKindSpec(
                kind_name="b",
                object_type=ControlObjectType.WORK_ORDER,
                allowed_planes=[PlaneType.FIELD],
                domain="d2",
            )
        )
        assert len(reg.list_object_kinds("d1")) == 1
        assert len(reg.list_object_kinds("d2")) == 1

    def test_link_policies(self):
        reg = FabricRegistry()
        reg.register_link_policy(
            LinkPolicySpec(
                source_kind="a",
                target_kind="b",
                allowed_link_types=[ControlLinkType.DERIVES_FROM],
            )
        )
        policies = reg.get_link_policies(source_kind="a")
        assert len(policies) == 1

    def test_reconciliation_rules(self):
        reg = FabricRegistry()
        reg.register_reconciliation_rule(
            ReconciliationRuleSpec(rule_name="r1", domain="test", priority=5)
        )
        reg.register_reconciliation_rule(
            ReconciliationRuleSpec(rule_name="r2", domain="test", priority=10)
        )
        rules = reg.get_reconciliation_rules("test")
        assert len(rules) == 2
        assert rules[0].priority >= rules[1].priority  # sorted desc

    def test_action_policies(self):
        reg = FabricRegistry()
        reg.register_action_policy(ActionPolicySpec(action_type="credit_note", domain="test"))
        assert reg.get_action_policy("credit_note") is not None
        assert reg.get_action_policy("nonexistent") is None

    def test_validators(self):
        reg = FabricRegistry()
        reg.register_validator("check_x", lambda x: True)
        assert reg.get_validator("check_x") is not None


class TestDomainPackIntegration:
    def test_contract_margin_registers(self):
        reg = FabricRegistry()
        register_contract_margin(reg)
        assert reg.has_object_kind("extracted_clause")
        assert reg.has_object_kind("rate_card_entry")
        assert reg.has_object_kind("billable_event")
        assert reg.has_object_kind("leakage_trigger")
        kinds = reg.list_object_kinds("contract_margin")
        assert len(kinds) >= 4

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

    def test_all_domain_packs_register(self):
        reg = FabricRegistry()
        register_all_domain_packs(reg)
        all_kinds = reg.list_object_kinds()
        assert len(all_kinds) >= 11

    def test_cross_domain_link_policies(self):
        reg = FabricRegistry()
        register_all_domain_packs(reg)
        # Field to service cross-plane policy
        policies = reg.get_link_policies(source_kind="work_order", target_kind="incident_state")
        assert len(policies) == 1
        assert policies[0].required_cross_plane
