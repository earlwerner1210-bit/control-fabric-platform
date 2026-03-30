from __future__ import annotations

import logging

from app.core.graph.domain_types import ControlObjectType
from app.core.registry.domain_types import SchemaNamespace

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    pass


class SchemaRegistry:
    """
    Central registry of all schema namespaces.

    Patent Claim (Theme 5 — Fabric-Native Extensibility):
    Domain packs register new namespaces at runtime without modifying
    core platform code. The registry validates object attributes against
    the registered schema for their namespace.
    """

    def __init__(self) -> None:
        self._namespaces: dict[str, SchemaNamespace] = {}
        self._type_index: dict[str, list[str]] = {}
        self._seed_core_namespaces()

    def register(self, namespace: SchemaNamespace) -> None:
        key = f"{namespace.name}:{namespace.version}"
        if key in self._namespaces:
            raise SchemaValidationError(f"Namespace {key} already registered.")
        self._namespaces[key] = namespace
        self._type_index.setdefault(namespace.object_type.value, []).append(key)
        logger.info("Registered namespace: %s (domain_pack=%s)", key, namespace.domain_pack)

    def get(self, name: str, version: str) -> SchemaNamespace | None:
        return self._namespaces.get(f"{name}:{version}")

    def get_for_type(self, object_type: ControlObjectType) -> list[SchemaNamespace]:
        keys = self._type_index.get(object_type.value, [])
        return [self._namespaces[k] for k in keys if k in self._namespaces]

    def validate_attributes(
        self, namespace_name: str, namespace_version: str, attributes: dict
    ) -> None:
        """
        Validate object attributes against registered schema.
        Raises SchemaValidationError if required attributes are missing.
        """
        ns = self.get(namespace_name, namespace_version)
        if ns is None:
            raise SchemaValidationError(
                f"Namespace {namespace_name}:{namespace_version} not found."
            )
        missing = [attr for attr in ns.required_attributes if attr not in attributes]
        if missing:
            raise SchemaValidationError(
                f"Missing required attributes for namespace {namespace_name}: {missing}"
            )

    def _seed_core_namespaces(self) -> None:
        """Seed the registry with core platform namespaces."""
        core_namespaces = [
            SchemaNamespace(
                name="core",
                version="1.0.0",
                domain_pack="core",
                object_type=ControlObjectType.RISK_CONTROL,
                required_attributes=["risk_rating"],
                optional_attributes=["owner", "review_date"],
                description="Core risk control schema",
                is_core=True,
            ),
            SchemaNamespace(
                name="core",
                version="1.0.0",
                domain_pack="core",
                object_type=ControlObjectType.COMPLIANCE_REQUIREMENT,
                required_attributes=["regulation_ref"],
                optional_attributes=["article", "clause"],
                description="Core compliance requirement schema",
                is_core=True,
            ),
            SchemaNamespace(
                name="core",
                version="1.0.0",
                domain_pack="core",
                object_type=ControlObjectType.REGULATORY_MANDATE,
                required_attributes=["regulation_name", "jurisdiction"],
                optional_attributes=["effective_date", "enforcement_body"],
                description="Core regulatory mandate schema",
                is_core=True,
            ),
            SchemaNamespace(
                name="core",
                version="1.0.0",
                domain_pack="core",
                object_type=ControlObjectType.TECHNICAL_CONTROL,
                required_attributes=["control_category"],
                optional_attributes=["implementation_status", "owner"],
                description="Core technical control schema",
                is_core=True,
            ),
            SchemaNamespace(
                name="core",
                version="1.0.0",
                domain_pack="core",
                object_type=ControlObjectType.VULNERABILITY,
                required_attributes=["cvss_score"],
                optional_attributes=["cve_id", "affected_systems"],
                description="Core vulnerability schema",
                is_core=True,
            ),
            SchemaNamespace(
                name="core",
                version="1.0.0",
                domain_pack="core",
                object_type=ControlObjectType.SECURITY_CONTROL,
                required_attributes=["control_family"],
                optional_attributes=["nist_mapping", "owner"],
                description="Core security control schema",
                is_core=True,
            ),
        ]
        for ns in core_namespaces:
            key = f"{ns.name}:{ns.version}"
            self._namespaces[key] = ns
            self._type_index.setdefault(ns.object_type.value, []).append(key)

    @property
    def namespace_count(self) -> int:
        return len(self._namespaces)
