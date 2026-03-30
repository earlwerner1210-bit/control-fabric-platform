from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.graph.domain_types import ControlObjectType, RelationshipType
from app.core.reconciliation.cross_plane_engine import (
    ReconciliationCaseSeverity,
    ReconciliationRule,
)
from app.core.registry.domain_types import SchemaNamespace
from app.core.registry.schema_registry import SchemaRegistry

logger = logging.getLogger(__name__)


@dataclass
class DomainPack:
    """
    A pluggable governance domain extension.

    Patent Claim (Theme 5 — Fabric-Native Extensibility):
    Domain packs extend the core platform with new object types,
    relationship types, schema namespaces, and reconciliation rules
    without modifying the core architecture.

    This is the structural proof that the platform is domain-agnostic.
    """

    pack_id: str
    name: str
    version: str
    description: str
    namespaces: list[SchemaNamespace] = field(default_factory=list)
    reconciliation_rules: list[ReconciliationRule] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class DomainPackLoader:
    """
    Loads domain packs into the core platform at runtime.

    Patent Claim (Theme 5): New governance capabilities are layered on
    top as independent domain packs that extend the core type system
    and rules engine without modifying the underlying architecture.
    """

    def __init__(self, schema_registry: SchemaRegistry) -> None:
        self._schema_registry = schema_registry
        self._loaded_packs: dict[str, DomainPack] = {}

    def load(self, pack: DomainPack) -> None:
        """Load a domain pack — registers namespaces and rules."""
        if pack.pack_id in self._loaded_packs:
            logger.warning("Domain pack %s already loaded.", pack.pack_id)
            return

        for ns in pack.namespaces:
            try:
                self._schema_registry.register(ns)
            except Exception as e:
                logger.warning("Namespace registration warning: %s", e)

        self._loaded_packs[pack.pack_id] = pack
        logger.info(
            "Loaded domain pack: %s v%s (%d namespaces, %d rules)",
            pack.name,
            pack.version,
            len(pack.namespaces),
            len(pack.reconciliation_rules),
        )

    def get_all_rules(self) -> list[ReconciliationRule]:
        """Get all reconciliation rules from all loaded packs."""
        rules = []
        for pack in self._loaded_packs.values():
            rules.extend(pack.reconciliation_rules)
        return rules

    def get_loaded_packs(self) -> list[DomainPack]:
        return list(self._loaded_packs.values())

    @property
    def pack_count(self) -> int:
        return len(self._loaded_packs)


def build_telco_ops_pack() -> DomainPack:
    """
    Telecom Operations domain pack.
    Mirrors the telco-ops domain pack already in the repo.
    """
    return DomainPack(
        pack_id="telco-ops-v1",
        name="telco-ops",
        version="1.0.0",
        description="Telecom operations governance domain pack",
        namespaces=[
            SchemaNamespace(
                name="telco-ops",
                version="1.0.0",
                domain_pack="telco-ops",
                object_type=ControlObjectType.DOMAIN_PACK_EXTENSION,
                required_attributes=["network_element", "operator_id"],
                optional_attributes=["region", "technology_generation"],
                description="Telco operations control objects",
            ),
        ],
        reconciliation_rules=[
            ReconciliationRule(
                rule_id="TELCO-001",
                domain_pack="telco-ops",
                rule_name="network_asset_must_have_security_control",
                description="Every network asset must have at least one security control",
                source_plane="operations",
                target_plane="security",
                source_object_type=ControlObjectType.ASSET,
                target_object_type=ControlObjectType.SECURITY_CONTROL,
                required_relationship=RelationshipType.REQUIRES,
                severity=ReconciliationCaseSeverity.HIGH,
            ),
        ],
    )


def build_contract_margin_pack() -> DomainPack:
    """Contract margin domain pack."""
    return DomainPack(
        pack_id="contract-margin-v1",
        name="contract-margin",
        version="1.0.0",
        description="Contract margin governance domain pack",
        namespaces=[
            SchemaNamespace(
                name="contract-margin",
                version="1.0.0",
                domain_pack="contract-margin",
                object_type=ControlObjectType.DOMAIN_PACK_EXTENSION,
                required_attributes=["contract_id", "margin_threshold"],
                optional_attributes=["currency", "review_cycle"],
                description="Contract margin control objects",
            ),
        ],
        reconciliation_rules=[],
    )
