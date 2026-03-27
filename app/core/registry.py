"""Object kind registry — domain packs register their specialisations here."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from app.core.errors import DuplicateRegistrationError, UnknownObjectKindError
from app.core.types import ControlLinkType, ControlObjectType, PlaneType


class ObjectKindSpec(BaseModel):
    """Specification for a domain-specific control object kind."""

    kind_name: str
    object_type: ControlObjectType
    allowed_planes: list[PlaneType]
    domain: str
    description: str = ""
    required_payload_fields: list[str] = Field(default_factory=list)
    allowed_link_types: list[ControlLinkType] = Field(default_factory=list)
    schema_version: str = "1.0"
    metadata: dict[str, Any] = Field(default_factory=dict)


class LinkPolicySpec(BaseModel):
    """Policy spec for what links are valid between object kinds."""

    source_kind: str
    target_kind: str
    allowed_link_types: list[ControlLinkType]
    required_same_plane: bool = False
    required_cross_plane: bool = False
    max_links: int | None = None


class ReconciliationRuleSpec(BaseModel):
    """Domain-specific reconciliation rule registration."""

    rule_name: str
    domain: str
    description: str = ""
    source_kind: str | None = None
    target_kind: str | None = None
    planes: list[PlaneType] = Field(default_factory=list)
    priority: int = 0


class ActionPolicySpec(BaseModel):
    """Domain-specific action policy registration."""

    action_type: str
    domain: str
    description: str = ""
    required_object_kinds: list[str] = Field(default_factory=list)
    required_evidence_types: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    auto_release: bool = False


class FabricRegistry:
    """Central registry for domain pack specialisations on top of the fabric."""

    def __init__(self) -> None:
        self._object_kinds: dict[str, ObjectKindSpec] = {}
        self._link_policies: list[LinkPolicySpec] = []
        self._reconciliation_rules: dict[str, ReconciliationRuleSpec] = {}
        self._action_policies: dict[str, ActionPolicySpec] = {}
        self._validators: dict[str, Callable[..., Any]] = {}

    def register_object_kind(self, spec: ObjectKindSpec) -> None:
        if spec.kind_name in self._object_kinds:
            raise DuplicateRegistrationError(f"Object kind '{spec.kind_name}' already registered")
        self._object_kinds[spec.kind_name] = spec

    def get_object_kind(self, kind_name: str) -> ObjectKindSpec:
        if kind_name not in self._object_kinds:
            raise UnknownObjectKindError(f"Unknown object kind: {kind_name}")
        return self._object_kinds[kind_name]

    def has_object_kind(self, kind_name: str) -> bool:
        return kind_name in self._object_kinds

    def list_object_kinds(self, domain: str | None = None) -> list[ObjectKindSpec]:
        specs = list(self._object_kinds.values())
        if domain:
            specs = [s for s in specs if s.domain == domain]
        return specs

    def register_link_policy(self, policy: LinkPolicySpec) -> None:
        self._link_policies.append(policy)

    def get_link_policies(
        self,
        source_kind: str | None = None,
        target_kind: str | None = None,
    ) -> list[LinkPolicySpec]:
        policies = list(self._link_policies)
        if source_kind:
            policies = [p for p in policies if p.source_kind == source_kind]
        if target_kind:
            policies = [p for p in policies if p.target_kind == target_kind]
        return policies

    def register_reconciliation_rule(self, spec: ReconciliationRuleSpec) -> None:
        if spec.rule_name in self._reconciliation_rules:
            raise DuplicateRegistrationError(
                f"Reconciliation rule '{spec.rule_name}' already registered"
            )
        self._reconciliation_rules[spec.rule_name] = spec

    def get_reconciliation_rules(self, domain: str | None = None) -> list[ReconciliationRuleSpec]:
        rules = list(self._reconciliation_rules.values())
        if domain:
            rules = [r for r in rules if r.domain == domain]
        return sorted(rules, key=lambda r: r.priority, reverse=True)

    def register_action_policy(self, spec: ActionPolicySpec) -> None:
        if spec.action_type in self._action_policies:
            raise DuplicateRegistrationError(
                f"Action policy '{spec.action_type}' already registered"
            )
        self._action_policies[spec.action_type] = spec

    def get_action_policy(self, action_type: str) -> ActionPolicySpec | None:
        return self._action_policies.get(action_type)

    def list_action_policies(self, domain: str | None = None) -> list[ActionPolicySpec]:
        policies = list(self._action_policies.values())
        if domain:
            policies = [p for p in policies if p.domain == domain]
        return policies

    def register_validator(self, name: str, validator_fn: Callable[..., Any]) -> None:
        self._validators[name] = validator_fn

    def get_validator(self, name: str) -> Callable[..., Any] | None:
        return self._validators.get(name)
